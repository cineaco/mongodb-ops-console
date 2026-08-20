from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ConnectionsInfo(BaseModel):
    current: int | None = None
    available: int | None = None


class OpsPerSecond(BaseModel):
    insert: float | None = None
    query: float | None = None
    update: float | None = None
    delete: float | None = None


class MemoryInfo(BaseModel):
    resident_mb: int | None = None
    virtual_mb: int | None = None


class CacheInfo(BaseModel):
    used_bytes: int | None = None
    total_bytes: int | None = None
    dirty_bytes: int | None = None
    hit_ratio: float | None = None


class StorageInfo(BaseModel):
    data_size_bytes: int | None = None
    fs_total_bytes: int | None = None
    fs_used_bytes: int | None = None
    fs_used_percent: float | None = None


class MetricLatestResponse(BaseModel):
    cluster_id: str
    collected_at: datetime
    rs_state: str
    primary_member: str | None = None
    members_up: int
    members_total: int
    max_replication_lag_seconds: float | None = None
    connections: ConnectionsInfo
    ops_per_second: OpsPerSecond
    memory: MemoryInfo
    cache: CacheInfo
    storage: StorageInfo
    status: str


class MetricPointResponse(BaseModel):
    collected_at: datetime
    connections_current: int | None = None
    max_replication_lag_seconds: float | None = None
    memory_resident_mb: int | None = None
    fs_used_percent: float | None = None
    ops_per_second: OpsPerSecond


class MetricRangeResponse(BaseModel):
    cluster_id: str
    range: str
    points: list[MetricPointResponse]
