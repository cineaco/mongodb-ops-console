from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


_TOPOLOGY_PATTERN = r"^(pss|psa|psp|mixed_pss|percona_pss|percona_psa|single_node|standalone)$"
_VERSION_PATTERN = r"^(5\.0|6\.0|7\.0|8\.0)$"


class ClusterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    topology: str = Field(pattern=_TOPOLOGY_PATTERN)
    mongodb_version: str = Field(pattern=_VERSION_PATTERN)
    mongodb_port: int = Field(default=37017, ge=1024, le=65535)
    replicaset_name: str = Field(default="rs0")
    config: dict = Field(default_factory=dict)
    admin_credentials_secret_id: Optional[str] = None


class ClusterUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    topology: Optional[str] = Field(default=None, pattern=_TOPOLOGY_PATTERN)
    mongodb_version: Optional[str] = Field(default=None, pattern=_VERSION_PATTERN)
    mongodb_port: Optional[int] = Field(default=None, ge=1024, le=65535)
    replicaset_name: Optional[str] = None
    config: Optional[dict] = None
    admin_credentials_secret_id: Optional[str] = None


class ClusterResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    topology: str
    mongodb_version: str
    mongodb_port: int
    replicaset_name: str
    config: dict
    status: str
    admin_credentials_secret_id: Optional[str] = None
    last_deployed_at: Optional[datetime] = None
    last_deployed_by: Optional[str] = None
    created_at: datetime
    created_by: str
