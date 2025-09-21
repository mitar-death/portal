"""
Simple in-memory rate limiter for login attempts.
For production environments, consider using Redis or a dedicated service.
"""

import time
from typing import Dict, Optional
from datetime import datetime, timedelta
from loguru import logger
from server.app.core.config import settings


class LoginRateLimiter:
    """Simple in-memory rate limiter for login attempts."""
    
    def __init__(self):
        # Store attempts: {identifier: {"attempts": count, "window_start": timestamp, "locked_until": timestamp}}
        self._attempts: Dict[str, Dict] = {}
    
    def _clean_expired_entries(self):
        """Clean up expired entries to prevent memory bloat."""
        current_time = time.time()
        expired_keys = []
        
        for key, data in self._attempts.items():
            # Remove entries older than lockout period
            if (current_time - data.get("window_start", 0)) > (settings.LOGIN_RATE_LIMIT_LOCKOUT_MINUTES * 60):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._attempts[key]
    
    def is_rate_limited(self, identifier: str) -> tuple[bool, Optional[str]]:
        """
        Check if an identifier is rate limited.
        
        Args:
            identifier: Usually phone number or IP address
            
        Returns:
            tuple: (is_limited, reason_message)
        """
        self._clean_expired_entries()
        
        current_time = time.time()
        window_seconds = settings.LOGIN_RATE_LIMIT_WINDOW_MINUTES * 60
        lockout_seconds = settings.LOGIN_RATE_LIMIT_LOCKOUT_MINUTES * 60
        
        if identifier not in self._attempts:
            return False, None
        
        data = self._attempts[identifier]
        
        # Check if currently locked out
        locked_until = data.get("locked_until", 0)
        if locked_until > current_time:
            remaining_lockout = int((locked_until - current_time) / 60)
            return True, f"Too many login attempts. Try again in {remaining_lockout} minutes."
        
        # Check if window has expired
        window_start = data.get("window_start", 0)
        if (current_time - window_start) > window_seconds:
            # Window expired, reset attempts
            data["attempts"] = 0
            data["window_start"] = current_time
            data["locked_until"] = 0
            return False, None
        
        # Check if max attempts reached in current window
        if data["attempts"] >= settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS:
            # Lock the identifier
            data["locked_until"] = current_time + lockout_seconds
            return True, f"Too many login attempts. Account locked for {settings.LOGIN_RATE_LIMIT_LOCKOUT_MINUTES} minutes."
        
        return False, None
    
    def record_attempt(self, identifier: str, success: bool = False):
        """
        Record a login attempt.
        
        Args:
            identifier: Usually phone number or IP address
            success: Whether the attempt was successful
        """
        self._clean_expired_entries()
        
        current_time = time.time()
        
        if identifier not in self._attempts:
            self._attempts[identifier] = {
                "attempts": 0,
                "window_start": current_time,
                "locked_until": 0
            }
        
        data = self._attempts[identifier]
        
        if success:
            # Reset on successful login
            logger.info(f"Successful login for {identifier[:4]}****, resetting rate limit")
            data["attempts"] = 0
            data["window_start"] = current_time
            data["locked_until"] = 0
        else:
            # Increment failed attempts
            window_seconds = settings.LOGIN_RATE_LIMIT_WINDOW_MINUTES * 60
            
            # Check if we need to start a new window
            if (current_time - data.get("window_start", 0)) > window_seconds:
                data["attempts"] = 1
                data["window_start"] = current_time
                data["locked_until"] = 0
            else:
                data["attempts"] += 1
            
            logger.warning(f"Failed login attempt for {identifier[:4]}****, attempt {data['attempts']}/{settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS}")
    
    def get_remaining_attempts(self, identifier: str) -> int:
        """Get remaining attempts before rate limiting kicks in."""
        if identifier not in self._attempts:
            return settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS
        
        data = self._attempts[identifier]
        current_time = time.time()
        window_seconds = settings.LOGIN_RATE_LIMIT_WINDOW_MINUTES * 60
        
        # Check if window has expired
        window_start = data.get("window_start", 0)
        if (current_time - window_start) > window_seconds:
            return settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS
        
        return max(0, settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS - data.get("attempts", 0))


# Global rate limiter instance
login_rate_limiter = LoginRateLimiter()