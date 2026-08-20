from datetime import datetime
from pydantic import BaseModel


class AlertResponse(BaseModel):
    id: str
    cluster_id: str
    metric: str
    severity: str
    message: str
    threshold_value: float
    actual_value: float
    status: str
    first_triggered_at: datetime
    last_triggered_at: datetime
    resolved_at: datetime | None
    notified_at: datetime | None
    created_by: str


class AlertCountResponse(BaseModel):
    active_count: int
