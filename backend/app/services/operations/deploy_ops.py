"""Deploy / rerun operations — run Ansible playbooks via subprocess."""

import asyncio
import logging
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.cluster import Cluster
from app.models.job import Job
from app.services import inventory_generator

logger = logging.getLogger(__name__)

DEFAULT_TAGS = ["install", "config", "replication", "security", "summary"]

MAX_LOG_BYTES = 1_048_576  # 1 MB

# SSE channel registry — keyed by str(job_id)
active_streams: dict[str, asyncio.Queue] = {}


async def _run_ansible_playbook(
    cmd: list[str],
    queue: asyncio.Queue,
    timeout: int,
) -> tuple[int, str]:
    """Spawn ansible-playbook, stream stdout to *queue*, return (exit_code, log)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    log_buffer: list[str] = []
    log_size = 0

    try:
        assert proc.stdout is not None
        while True:
            try:
                line_bytes = await asyncio.wait_for(
                    proc.stdout.readline(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                log_buffer.append("\n[TIMEOUT] Deploy exceeded timeout limit.\n")
                return 1, "".join(log_buffer)

            if not line_bytes:
                break

            line = line_bytes.decode("utf-8", errors="replace")

            if log_size < MAX_LOG_BYTES:
                log_buffer.append(line)
                log_size += len(line_bytes)

            await queue.put(line)

        await proc.wait()
        return proc.returncode or 0, "".join(log_buffer)
    except Exception:
        proc.kill()
        await proc.wait()
        raise


async def deploy(
    db: AsyncSession,
    cluster: Cluster,
    params: dict,
    job_id: uuid.UUID | None = None,
) -> dict:
    """Run a full Ansible deploy for *cluster*."""
    # 1. Check for concurrent deploy/rerun
    if job_id is not None:
        concurrent = await db.execute(
            select(Job).where(
                Job.cluster_id == cluster.id,
                Job.status == "running",
                Job.operation.in_(["deploy", "rerun"]),
                Job.id != job_id,
            )
        )
        if concurrent.scalar_one_or_none() is not None:
            return {"error": "A deploy or rerun is already running for this cluster"}

    # 2. Mark cluster deploying
    cluster.status = "deploying"
    await db.flush()
    await db.commit()

    tags = params.get("tags") or list(DEFAULT_TAGS)
    temp_dir = tempfile.mkdtemp(prefix="deploy_")
    queue: asyncio.Queue = asyncio.Queue()
    stream_key = str(job_id) if job_id else None

    if stream_key:
        active_streams[stream_key] = queue

    start = time.monotonic()
    try:
        # 5. Generate inventory
        await inventory_generator.generate_inventory(db, cluster, job_id or uuid.uuid4(), temp_dir)

        # 6. Build command
        cmd = [
            "ansible-playbook",
            "-i",
            f"{temp_dir}/",
            f"{settings.PLAYBOOK_PATH}/mongodb-playbook.yml",
            "--tags",
            ",".join(tags),
            "-e",
            "ansible_ssh_common_args='-o StrictHostKeyChecking=no'",
        ]

        # 7-8. Run subprocess
        exit_code, log = await _run_ansible_playbook(
            cmd, queue, settings.DEPLOY_TIMEOUT_SECONDS
        )

        duration = round(time.monotonic() - start, 2)

        # 9-10. Update cluster status
        if exit_code == 0:
            cluster.status = "healthy"
            cluster.last_deployed_at = datetime.now(timezone.utc)
            await db.flush()
            await db.commit()
            return {
                "message": "Deploy completed successfully",
                "duration_seconds": duration,
                "tags": tags,
                "log": log,
                "exit_code": exit_code,
            }
        else:
            cluster.status = "failed"
            await db.flush()
            await db.commit()
            return {
                "error": f"Deploy failed with exit code {exit_code}",
                "duration_seconds": duration,
                "tags": tags,
                "log": log,
                "exit_code": exit_code,
            }

    except Exception as exc:
        cluster.status = "failed"
        await db.flush()
        await db.commit()
        duration = round(time.monotonic() - start, 2)
        return {
            "error": f"Deploy exception: {exc}",
            "duration_seconds": duration,
            "tags": tags,
            "log": "",
            "exit_code": -1,
        }
    finally:
        # 11. Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
        if stream_key:
            active_streams.pop(stream_key, None)


async def rerun(
    db: AsyncSession,
    cluster: Cluster,
    params: dict,
    job_id: uuid.UUID | None = None,
) -> dict:
    """Re-run specific Ansible tags against an already-deployed cluster."""
    tags = params.get("tags")
    if not tags:
        return {"error": "rerun requires a non-empty 'tags' list in params"}
    return await deploy(db, cluster, params, job_id=job_id)
