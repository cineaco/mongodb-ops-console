from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class JobResponse(BaseModel):
    id: str
    cluster_id: str
    operation: str
    status: str
    params: dict
    result: Optional[dict] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    created_by: str


class JobCreatedResponse(BaseModel):
    job_id: str
    operation: str
    status: str
    created_at: datetime


class RestartNodeRequest(BaseModel):
    host_id: str


class RotatePasswordRequest(BaseModel):
    new_password_secret_id: str


class CreateUserRequest(BaseModel):
    database: str = Field(min_length=1)
    username: str = Field(min_length=1)
    password_secret_id: str
    roles: list[str] = Field(default=["readWrite"])


class DeleteUserRequest(BaseModel):
    database: str = Field(min_length=1)
    username: str = Field(min_length=1)


class PbmRestoreRequest(BaseModel):
    timestamp: str


class MongodumpS3Request(BaseModel):
    s3_bucket: str = Field(min_length=1)
    s3_prefix: str = "backups"
    s3_region: str = "us-east-1"
    s3_auth_method: str = Field(default="iam_role", pattern=r"^(iam_role|secret)$")
    s3_credential_secret_id: Optional[str] = None
