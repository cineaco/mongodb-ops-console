from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1, repr=False)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(repr=False)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserMeResponse(BaseModel):
    id: str
    username: str
    email: str | None
    role: str
    disabled: bool
