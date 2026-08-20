from datetime import datetime

from pydantic import BaseModel, Field


class SecretCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: str = Field(pattern=r"^(ssh_key|admin_password|keyfile|s3_credential)$")
    plaintext: str = Field(min_length=1, repr=False)


class SecretResponse(BaseModel):
    id: str
    name: str
    type: str
    created_at: datetime
    created_by: str
