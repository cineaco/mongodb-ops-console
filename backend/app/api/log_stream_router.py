"""SSE log-stream endpoint for real-time deployment output."""

import asyncio
import json
import uuid
from typing import Annotated, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.user import User
from app.services import job_service
from app.services.operations.deploy_ops import active_streams

router = APIRouter(tags=["logs"])


async def _live_log_generator(queue: asyncio.Queue) -> AsyncGenerator[str, None]:
    """Yield SSE frames from a live asyncio.Queue until sentinel (None)."""
    while True:
        line = await queue.get()
        if line is None:
            yield f"data: {json.dumps({'event': 'done'})}\n\n"
            return
        yield f"data: {line}\n\n"


async def _stored_log_generator(log: str) -> AsyncGenerator[str, None]:
    """Yield stored log lines as an SSE burst, then a done event."""
    for line in log.splitlines():
        yield f"data: {line}\n\n"
    yield f"data: {json.dumps({'event': 'done'})}\n\n"


@router.get("/api/jobs/{job_id}/logs")
async def stream_job_logs(
    job_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("viewer"))],
):
    job = await job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Live stream for running jobs with an active queue
    if job.status == "running" and str(job_id) in active_streams:
        return StreamingResponse(
            _live_log_generator(active_streams[str(job_id)]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    # Stored log burst for completed jobs
    if job.status in ("success", "failed") and job.result and "log" in job.result:
        return StreamingResponse(
            _stored_log_generator(job.result["log"]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    raise HTTPException(status_code=404, detail="No logs available")
