from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=200, repr=False)
    email: str | None = None
    role: str = Field(pattern=r"^(admin|operator|viewer)$")


class UserUpdate(BaseModel):
    role: str | None = Field(default=None, pattern=r"^(admin|operator|viewer)$")
    disabled: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=200, repr=False)


class UserResponse(BaseModel):
    id: str
    username: str
    email: str | None
    role: str
    disabled: bool
    created_at: datetime
    last_login_at: datetime | None
