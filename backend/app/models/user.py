from typing import Optional

from sqlalchemy import Boolean, Index, String, Text, text

from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_cognito", "cognito_sub"),
        Index("idx_users_username", "username"),
    )

    cognito_sub: Mapped[str] = mapped_column(String(128), unique=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(80))
    avatar_url: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    is_admin: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
