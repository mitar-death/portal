from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    BIGINT,
    JSON,
    Text,
)
from sqlalchemy.ext.mutable import MutableList

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from server.app.models.base import BaseModel as Base
from init_db import logger


class User(Base):
    __tablename__ = "users"

    id = Column(BIGINT, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    phone_number = Column(String, unique=True, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now)

    selected_groups = relationship("SelectedGroup", back_populates="user")
    active_sessions = relationship("ActiveSession", back_populates="user")
    keywords = relationship("Keywords", back_populates="user")
    ai_accounts = relationship("AIAccount", back_populates="user")
    groups = relationship("Group", back_populates="user")


class SelectedGroup(Base):
    __tablename__ = "selected_groups"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BIGINT, ForeignKey("users.id"))
    group_id = Column(
        String
    )  # Changed from BIGINT to String to match how it's used in code
    created_at = Column(DateTime(timezone=True), server_default=func.now)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now)

    user = relationship("User", back_populates="selected_groups")


class ActiveSession(Base):
    __tablename__ = "active_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True)
    phone_number = Column(String, index=True)
    user_id = Column(BIGINT, ForeignKey("users.id"))
    code_requested = Column(Boolean, default=False)
    phone_code_hash = Column(String, nullable=True)  # Store phone code hash for login
    verified = Column(Boolean, default=False)

    # JWT session management
    access_token_jti = Column(
        String, nullable=True, index=True
    )  # JWT ID for access token
    refresh_token_jti = Column(
        String, nullable=True, index=True
    )  # JWT ID for refresh token
    access_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    refresh_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)  # Session status
    last_activity = Column(
        DateTime(timezone=True), server_default=func.now
    )  # Last activity timestamp
    device_info = Column(String, nullable=True)  # Optional device/browser info
    ip_address = Column(String, nullable=True)  # Client IP address

    created_at = Column(DateTime(timezone=True), server_default=func.now)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now)
    user = relationship("User", back_populates="active_sessions")


class Keywords(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BIGINT, ForeignKey("users.id"))
    keywords = Column(MutableList.as_mutable(JSON), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now)

    user = relationship("User", back_populates="keywords")

    def add_keyword(self, keyword):
        """Add a keyword to the keywords list if it doesn't exist."""
        if self.keywords is None:
            self.keywords = []

        # Convert keyword to lowercase for case-insensitive comparison
        keyword = keyword.lower().strip()

        logger.info("Adding keyword: %s to user %s", keyword, self.user_id)

        # Only add if not already in the list (case-insensitive comparison)
        lowercase_keywords = [
            k.lower() if isinstance(k, str) else k for k in self.keywords
        ]
        if keyword not in lowercase_keywords:
            self.keywords.append(keyword)
            return True
        return False

    def remove_keyword(self, keyword):
        """Remove a keyword from the keywords list."""
        if not self.keywords:
            return False

        # Convert keyword to lowercase for case-insensitive comparison
        keyword = keyword.lower().strip()

        # Find matching keyword (case-insensitive)
        for i, k in enumerate(self.keywords):
            if isinstance(k, str) and k.lower() == keyword:
                self.keywords.pop(i)
                return True
        return False


class AIAccount(Base):
    __tablename__ = "ai_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BIGINT, ForeignKey("users.id"))
    name = Column(String, nullable=False)  # Name to identify this AI account
    phone_number = Column(String, nullable=False)
    api_id = Column(String, nullable=False)
    api_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    session_string = Column(
        String, nullable=True
    )  # Optional: Store Telethon session string
    phone_code_hash = Column(
        String, nullable=True
    )  # Temporarily store the phone code hash during login
    shareable_link = Column(String, nullable=True)
    ai_response_context = Column(
        Text, nullable=True
    )  # Large text field for AI response context
    created_at = Column(DateTime(timezone=True), server_default=func.now)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now)

    user = relationship("User", back_populates="ai_accounts")
    group_assignments = relationship("GroupAIAccount", back_populates="ai_account")


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BIGINT, ForeignKey("users.id"))
    telegram_id = Column(BIGINT, index=True)  # The actual Telegram group ID
    title = Column(String, nullable=False)
    username = Column(String, nullable=True)
    description = Column(String, nullable=True)
    member_count = Column(Integer, default=0)
    is_channel = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now)
    is_monitored = Column(Boolean, default=False)

    user = relationship("User", back_populates="groups")
    ai_assignments = relationship("GroupAIAccount", back_populates="group")


class GroupAIAccount(Base):
    """Association table to link Groups with AI Accounts for automated responses"""

    __tablename__ = "group_ai_accounts"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(BIGINT, ForeignKey("groups.id"))
    ai_account_id = Column(BIGINT, ForeignKey("ai_accounts.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now)

    group = relationship("Group", back_populates="ai_assignments")
    ai_account = relationship("AIAccount", back_populates="group_assignments")


class BlacklistedToken(Base):
    """Table to track blacklisted JWT tokens for secure logout."""

    __tablename__ = "blacklisted_tokens"

    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String, unique=True, index=True, nullable=False)  # JWT ID
    token_type = Column(String, nullable=False)  # "access" or "refresh"
    user_id = Column(BIGINT, ForeignKey("users.id"), nullable=False)
    expires_at = Column(
        DateTime(timezone=True), nullable=False
    )  # When the token would have expired
    blacklisted_at = Column(
        DateTime(timezone=True), server_default=func.now
    )  # When it was blacklisted
    reason = Column(
        String, nullable=True
    )  # Optional reason for blacklisting (logout, security, etc.)

    user = relationship("User")


class LoginAttempt(Base):
    """Table to track login attempts for rate limiting."""

    __tablename__ = "login_attempts"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, index=True, nullable=False)
    ip_address = Column(String, index=True, nullable=True)
    success = Column(Boolean, default=False)
    attempted_at = Column(DateTime(timezone=True), server_default=func.now)
    user_agent = Column(String, nullable=True)
    failure_reason = Column(String, nullable=True)  # Invalid code, etc.
