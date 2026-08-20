from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


_ROLE_PATTERN = (
    r"^(primary|secondary|secondary2|arbiter"
    r"|percona_primary|percona_secondary|percona_secondary2|percona_arbiter|percona)$"
)


class HostCreate(BaseModel):
    hostname: str = Field(min_length=1, max_length=200)
    ip_address: str = Field(min_length=7, max_length=45)
    role: str = Field(pattern=_ROLE_PATTERN)
    ssh_user: str = Field(default="ubuntu")
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_key_secret_id: str


class HostUpdate(BaseModel):
    hostname: Optional[str] = Field(default=None, min_length=1, max_length=200)
    ip_address: Optional[str] = Field(default=None, min_length=7, max_length=45)
    role: Optional[str] = Field(default=None, pattern=_ROLE_PATTERN)
    ssh_user: Optional[str] = None
    ssh_port: Optional[int] = Field(default=None, ge=1, le=65535)
    ssh_key_secret_id: Optional[str] = None


class HostResponse(BaseModel):
    id: str
    cluster_id: str
    hostname: str
    ip_address: str
    role: str
    ssh_user: str
    ssh_port: int
    ssh_key_secret_id: str
    created_at: datetime
