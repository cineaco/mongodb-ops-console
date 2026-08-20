"""Generate Ansible inventory files from cluster registry data."""

import os
import uuid

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt
from app.models.cluster import Cluster
from app.models.cluster_host import ClusterHost
from app.models.secret import Secret

# Ordered list of valid roles for deterministic INI output
VALID_ROLES = [
    "primary",
    "secondary",
    "secondary2",
    "arbiter",
    "percona_primary",
    "percona_secondary",
    "percona_secondary2",
    "percona_arbiter",
    "percona",
]


async def generate_inventory(
    db: AsyncSession,
    cluster: Cluster,
    job_id: uuid.UUID,
    temp_dir: str,
) -> str:
    """Generate Ansible inventory directory structure at *temp_dir*.

    Creates:
      - {temp_dir}/keys/{hostname}.pem   (SSH private keys, mode 0o400)
      - {temp_dir}/hosts                  (INI inventory)
      - {temp_dir}/group_vars/all.yml     (merged cluster vars)

    Returns the path to the hosts file.

    Raises ValueError if no hosts are found for the cluster.
    """
    # --- 1. Read cluster hosts ---------------------------------------------------
    result = await db.execute(
        select(ClusterHost).where(ClusterHost.cluster_id == cluster.id)
    )
    hosts = list(result.scalars().all())

    if not hosts:
        raise ValueError(
            f"No hosts found for cluster {cluster.id} ({cluster.name})"
        )

    # --- 2. Create directories ---------------------------------------------------
    keys_dir = os.path.join(temp_dir, "keys")
    group_vars_dir = os.path.join(temp_dir, "group_vars")
    os.makedirs(keys_dir, exist_ok=True)
    os.makedirs(group_vars_dir, exist_ok=True)

    # --- 3. Write SSH keys -------------------------------------------------------
    for host in hosts:
        secret = await _get_secret(db, host.ssh_key_secret_id)
        plaintext = decrypt(secret.ciphertext, secret.nonce, secret.auth_tag)
        key_path = os.path.join(keys_dir, f"{host.hostname}.pem")
        with open(key_path, "wb") as fh:
            fh.write(plaintext)
        os.chmod(key_path, 0o400)

    # --- 4. Write hosts INI file -------------------------------------------------
    hosts_path = os.path.join(temp_dir, "hosts")
    _write_hosts_ini(hosts, keys_dir, hosts_path)

    # --- 5. Write group_vars/all.yml --------------------------------------------
    admin_password = await _decrypt_admin_password(db, cluster)
    _write_group_vars(cluster, admin_password, group_vars_dir)

    return hosts_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_secret(db: AsyncSession, secret_id: uuid.UUID) -> Secret:
    result = await db.execute(select(Secret).where(Secret.id == secret_id))
    secret = result.scalar_one_or_none()
    if secret is None:
        raise ValueError(f"Secret {secret_id} not found")
    return secret


async def _decrypt_admin_password(
    db: AsyncSession, cluster: Cluster
) -> str | None:
    if cluster.admin_credentials_secret_id is None:
        return None
    secret = await _get_secret(db, cluster.admin_credentials_secret_id)
    return decrypt(secret.ciphertext, secret.nonce, secret.auth_tag).decode("utf-8")


def _write_hosts_ini(
    hosts: list[ClusterHost], keys_dir: str, hosts_path: str
) -> None:
    # Group hosts by role
    groups: dict[str, list[ClusterHost]] = {}
    for host in hosts:
        groups.setdefault(host.role, []).append(host)

    lines: list[str] = []
    active_groups: list[str] = []

    for role in VALID_ROLES:
        if role not in groups:
            continue
        active_groups.append(role)
        lines.append(f"[{role}]")
        for host in groups[role]:
            key_path = os.path.join(keys_dir, f"{host.hostname}.pem")
            lines.append(
                f"{host.hostname} "
                f"ansible_host={host.ip_address} "
                f"ansible_port={host.ssh_port} "
                f"ansible_user={host.ssh_user} "
                f"ansible_ssh_private_key_file={key_path}"
            )
        lines.append("")

    # [mongodb:children]
    lines.append("[mongodb:children]")
    for group in active_groups:
        lines.append(group)
    lines.append("")

    # [mongodb:vars]
    lines.append("[mongodb:vars]")
    lines.append("ansible_python_interpreter=/usr/bin/python3")
    lines.append("ansible_become=true")
    lines.append("ansible_become_method=sudo")
    lines.append("")

    with open(hosts_path, "w") as fh:
        fh.write("\n".join(lines))


def _write_group_vars(
    cluster: Cluster, admin_password: str | None, group_vars_dir: str
) -> None:
    vars_dict: dict = {}

    # Merge cluster.config JSONB first (lower priority)
    if cluster.config:
        vars_dict.update(cluster.config)

    # Overlay cluster-level fields
    vars_dict["mongodb_version"] = cluster.mongodb_version
    vars_dict["mongodb_port"] = cluster.mongodb_port
    vars_dict["replicaset_name"] = cluster.replicaset_name

    if admin_password is not None:
        vars_dict["admin_password"] = admin_password

    all_yml_path = os.path.join(group_vars_dir, "all.yml")
    with open(all_yml_path, "w") as fh:
        yaml.dump(vars_dict, fh, default_flow_style=False)
