import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    display_name: str | None
    avatar_url: str | None
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserUpdateRequest(BaseModel):
    display_name: str | None = None
    avatar_url: str | None = None


class PublicUserResponse(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str | None
    avatar_url: str | None

    model_config = ConfigDict(from_attributes=True)
