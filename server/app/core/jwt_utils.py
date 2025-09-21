"""
JWT utilities for secure authentication.
"""

import jwt
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Union
from fastapi import HTTPException, status
from server.app.core.config import settings
from server.app.core.logging import logger


class JWTManager:
    """Manager class for JWT token operations."""

    @staticmethod
    def create_access_token(
        user_id: int,
        telegram_id: str,
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a JWT access token.

        Args:
            user_id: User's database ID
            telegram_id: User's Telegram ID
            additional_claims: Additional claims to include in the token

        Returns:
            JWT access token as string
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        jti = str(uuid.uuid4())  # Unique token ID for blacklisting

        payload = {
            "sub": str(user_id),  # Subject - user ID
            "telegram_id": telegram_id,
            "jti": jti,  # JWT ID for blacklisting
            "iat": now,  # Issued at
            "exp": expires_at,  # Expiration time
            "iss": settings.JWT_ISSUER,  # Issuer
            "aud": settings.JWT_AUDIENCE,  # Audience
            "type": "access",
        }

        if additional_claims:
            payload.update(additional_claims)

        try:
            token = jwt.encode(
                payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
            )
            logger.debug(f"Created access token for user {user_id}")
            return token
        except Exception as e:
            logger.error(f"Failed to create access token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create access token",
            )

    @staticmethod
    def create_refresh_token(
        user_id: int,
        telegram_id: str,
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a JWT refresh token.

        Args:
            user_id: User's database ID
            telegram_id: User's Telegram ID
            additional_claims: Additional claims to include in the token

        Returns:
            JWT refresh token as string
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        jti = str(uuid.uuid4())  # Unique token ID for blacklisting

        payload = {
            "sub": str(user_id),  # Subject - user ID
            "telegram_id": telegram_id,
            "jti": jti,  # JWT ID for blacklisting
            "iat": now,  # Issued at
            "exp": expires_at,  # Expiration time
            "iss": settings.JWT_ISSUER,  # Issuer
            "aud": settings.JWT_AUDIENCE,  # Audience
            "type": "refresh",
        }

        if additional_claims:
            payload.update(additional_claims)

        try:
            token = jwt.encode(
                payload,
                settings.JWT_REFRESH_SECRET_KEY,
                algorithm=settings.JWT_ALGORITHM,
            )
            logger.debug(f"Created refresh token for user {user_id}")
            return token
        except Exception as e:
            logger.error(f"Failed to create refresh token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create refresh token",
            )

    @staticmethod
    def verify_token(
        token: str, token_type: str = "access", verify_expiry: bool = True
    ) -> Dict[str, Any]:
        """
        Verify and decode a JWT token.

        Args:
            token: JWT token string
            token_type: Type of token ("access" or "refresh")
            verify_expiry: Whether to verify token expiration

        Returns:
            Decoded token payload

        Raises:
            HTTPException: If token is invalid
        """
        secret_key = (
            settings.JWT_SECRET_KEY
            if token_type == "access"
            else settings.JWT_REFRESH_SECRET_KEY
        )

        try:
            # Decode and verify token
            payload = jwt.decode(
                token,
                secret_key,
                algorithms=[settings.JWT_ALGORITHM],
                issuer=settings.JWT_ISSUER,
                audience=settings.JWT_AUDIENCE,
                options={"verify_exp": verify_expiry},
            )

            # Verify token type
            if payload.get("type") != token_type:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid token type, expected {token_type}",
                )

            logger.debug(f"Verified {token_type} token for user {payload.get('sub')}")
            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )
        except Exception as e:
            logger.error(f"Token verification error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token verification failed",
            )

    @staticmethod
    def extract_user_id_from_token(payload: Dict[str, Any]) -> int:
        """
        Extract user ID from token payload.

        Args:
            payload: Decoded JWT payload

        Returns:
            User ID as integer

        Raises:
            HTTPException: If user ID is not found or invalid
        """
        try:
            user_id_str = payload.get("sub")
            if not user_id_str:
                raise ValueError("User ID not found in token")

            user_id = int(user_id_str)
            return user_id
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid user ID in token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user ID in token",
            )

    @staticmethod
    def extract_telegram_id_from_token(payload: Dict[str, Any]) -> str:
        """
        Extract Telegram ID from token payload.

        Args:
            payload: Decoded JWT payload

        Returns:
            Telegram ID as string

        Raises:
            HTTPException: If Telegram ID is not found
        """
        telegram_id = payload.get("telegram_id")
        if not telegram_id:
            logger.error("Telegram ID not found in token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Telegram ID not found in token",
            )
        return telegram_id

    @staticmethod
    def is_token_expired(payload: Dict[str, Any]) -> bool:
        """
        Check if token is expired.

        Args:
            payload: Decoded JWT payload

        Returns:
            True if token is expired, False otherwise
        """
        exp = payload.get("exp")
        if not exp:
            return True

        exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
        return datetime.now(timezone.utc) > exp_datetime

    @staticmethod
    def get_token_expiry(payload: Dict[str, Any]) -> Optional[datetime]:
        """
        Get token expiry datetime.

        Args:
            payload: Decoded JWT payload

        Returns:
            Token expiry datetime or None if not found
        """
        exp = payload.get("exp")
        if exp:
            return datetime.fromtimestamp(exp, tz=timezone.utc)
        return None

    @staticmethod
    def create_token_pair(
        user_id: int,
        telegram_id: str,
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        Create both access and refresh tokens.

        Args:
            user_id: User's database ID
            telegram_id: User's Telegram ID
            additional_claims: Additional claims to include in tokens

        Returns:
            Dictionary with access_token and refresh_token
        """
        access_token = JWTManager.create_access_token(
            user_id, telegram_id, additional_claims
        )
        refresh_token = JWTManager.create_refresh_token(
            user_id, telegram_id, additional_claims
        )

        return {"access_token": access_token, "refresh_token": refresh_token}


# Convenience functions for easier access
def create_access_token(
    user_id: int, telegram_id: str, additional_claims: Optional[Dict[str, Any]] = None
) -> str:
    """Create a JWT access token."""
    return JWTManager.create_access_token(user_id, telegram_id, additional_claims)


def create_refresh_token(
    user_id: int, telegram_id: str, additional_claims: Optional[Dict[str, Any]] = None
) -> str:
    """Create a JWT refresh token."""
    return JWTManager.create_refresh_token(user_id, telegram_id, additional_claims)


def verify_token(
    token: str, token_type: str = "access", verify_expiry: bool = True
) -> Dict[str, Any]:
    """Verify and decode a JWT token."""
    return JWTManager.verify_token(token, token_type, verify_expiry)


def create_token_pair(
    user_id: int, telegram_id: str, additional_claims: Optional[Dict[str, Any]] = None
) -> Dict[str, str]:
    """Create both access and refresh tokens."""
    return JWTManager.create_token_pair(user_id, telegram_id, additional_claims)
