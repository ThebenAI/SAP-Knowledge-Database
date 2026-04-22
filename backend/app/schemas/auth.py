from datetime import datetime

from pydantic import BaseModel, Field

from app.models.user import UserRole


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class UserRead(BaseModel):
    id: int
    username: str
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=8, max_length=72)
    role: UserRole = UserRole.reviewer
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


class UserPasswordResetRequest(BaseModel):
    password: str = Field(min_length=8, max_length=72)
