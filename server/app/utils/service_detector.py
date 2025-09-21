"""Service availability detection utility for graceful degradation."""

import asyncio
from typing import Dict, Optional, Any
from functools import wraps
from server.app.core.logging import logger
from server.app.core.environment_validator import get_environment_validator
import time

# Global cache for service availability status
_service_status_cache: Dict[str, Dict[str, Any]] = {}
_cache_timeout = 30  # Cache results for 30 seconds

class ServiceAvailabilityError(Exception):
    """Exception raised when a required service is unavailable."""
    def __init__(self, service_name: str, message: str = None):
        self.service_name = service_name
        self.message = message or f"Service {service_name} is unavailable"
        super().__init__(self.message)

class ServiceDetector:
    """Service availability detector with caching and graceful degradation."""
    
    def __init__(self):
        self.validator = get_environment_validator()
    
    async def is_service_available(self, service_name: str, force_refresh: bool = False) -> bool:
        """
        Check if a service is available with caching.
        
        Args:
            service_name: Name of the service to check
            force_refresh: If True, bypass cache and check directly
            
        Returns:
            bool: True if service is available, False otherwise
        """
        current_time = time.time()
        
        # Check cache first (unless forcing refresh)
        if not force_refresh and service_name in _service_status_cache:
            cache_entry = _service_status_cache[service_name]
            if current_time - cache_entry.get('timestamp', 0) < _cache_timeout:
                return cache_entry.get('available', False)
        
        # Check service availability
        try:
            services_health = await asyncio.wait_for(
                self.validator.check_all_services(), 
                timeout=5.0
            )
            
            service_health = services_health.get(service_name)
            available = service_health and service_health.available
            
            # Update cache
            _service_status_cache[service_name] = {
                'available': available,
                'timestamp': current_time,
                'health': service_health
            }
            
            return available
            
        except asyncio.TimeoutError:
            logger.warning(f"Service availability check for {service_name} timed out")
            return False
        except Exception as e:
            logger.error(f"Error checking service availability for {service_name}: {e}")
            return False
    
    async def get_service_health(self, service_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed health information for a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Dict with service health information or None if unavailable
        """
        current_time = time.time()
        
        # Check cache first
        if service_name in _service_status_cache:
            cache_entry = _service_status_cache[service_name]
            if current_time - cache_entry.get('timestamp', 0) < _cache_timeout:
                health = cache_entry.get('health')
                if health:
                    return {
                        'name': health.name,
                        'status': health.status.value,
                        'available': health.available,
                        'response_time_ms': health.response_time_ms,
                        'error': health.error,
                        'details': health.details
                    }
        
        # Refresh and return
        await self.is_service_available(service_name, force_refresh=True)
        cache_entry = _service_status_cache.get(service_name, {})
        health = cache_entry.get('health')
        
        if health:
            return {
                'name': health.name,
                'status': health.status.value,
                'available': health.available,
                'response_time_ms': health.response_time_ms,
                'error': health.error,
                'details': health.details
            }
        
        return None
    
    async def get_available_services(self) -> Dict[str, bool]:
        """
        Get availability status for all services.
        
        Returns:
            Dict mapping service names to their availability status
        """
        services = ['database', 'redis', 'telegram', 'google_ai', 'pusher']
        availability = {}
        
        # Check all services concurrently
        tasks = {
            service: asyncio.create_task(self.is_service_available(service))
            for service in services
        }
        
        for service, task in tasks.items():
            try:
                availability[service] = await asyncio.wait_for(task, timeout=10.0)
            except asyncio.TimeoutError:
                availability[service] = False
            except Exception as e:
                logger.error(f"Error checking availability for {service}: {e}")
                availability[service] = False
        
        return availability
    
    def clear_cache(self, service_name: str = None):
        """Clear service status cache."""
        if service_name:
            _service_status_cache.pop(service_name, None)
        else:
            _service_status_cache.clear()

# Global service detector instance
_service_detector = None

def get_service_detector() -> ServiceDetector:
    """Get the global service detector instance."""
    global _service_detector
    if _service_detector is None:
        _service_detector = ServiceDetector()
    return _service_detector

# Decorator for service-dependent functions
def requires_service(service_name: str, fallback_value=None, raise_on_unavailable: bool = False):
    """
    Decorator to check service availability before executing a function.
    
    Args:
        service_name: Name of the required service
        fallback_value: Value to return if service is unavailable (default: None)
        raise_on_unavailable: If True, raise ServiceAvailabilityError when unavailable
        
    Usage:
        @requires_service('redis', fallback_value=[])
        async def get_cached_data():
            # This will return [] if Redis is unavailable
            pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            detector = get_service_detector()
            
            try:
                is_available = await detector.is_service_available(service_name)
                
                if not is_available:
                    if raise_on_unavailable:
                        raise ServiceAvailabilityError(service_name)
                    
                    logger.warning(f"Service {service_name} unavailable, using fallback for {func.__name__}")
                    return fallback_value
                
                return await func(*args, **kwargs)
                
            except ServiceAvailabilityError:
                raise
            except Exception as e:
                logger.error(f"Error in service-dependent function {func.__name__}: {e}")
                if raise_on_unavailable:
                    raise ServiceAvailabilityError(service_name, f"Error checking service: {str(e)}")
                return fallback_value
        
        return wrapper
    return decorator

# Decorator for optional services (logs warning but doesn't fail)
def optional_service(service_name: str, default_value=None):
    """
    Decorator for functions that use optional services.
    
    Args:
        service_name: Name of the optional service
        default_value: Default value to return if service is unavailable
    """
    return requires_service(service_name, fallback_value=default_value, raise_on_unavailable=False)

# Context manager for service-dependent operations
class ServiceContext:
    """Context manager for service-dependent operations."""
    
    def __init__(self, service_name: str, raise_on_unavailable: bool = False):
        self.service_name = service_name
        self.raise_on_unavailable = raise_on_unavailable
        self.detector = get_service_detector()
        self.available = False
    
    async def __aenter__(self):
        self.available = await self.detector.is_service_available(self.service_name)
        
        if not self.available and self.raise_on_unavailable:
            raise ServiceAvailabilityError(self.service_name)
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def is_available(self) -> bool:
        """Check if the service is available."""
        return self.available

# Utility functions for common service checks
async def check_database_available() -> bool:
    """Quick check if database is available."""
    detector = get_service_detector()
    return await detector.is_service_available('database')

async def check_redis_available() -> bool:
    """Quick check if Redis is available."""
    detector = get_service_detector()
    return await detector.is_service_available('redis')

async def check_telegram_available() -> bool:
    """Quick check if Telegram service is available."""
    detector = get_service_detector()
    return await detector.is_service_available('telegram')

async def check_ai_available() -> bool:
    """Quick check if Google AI service is available."""
    detector = get_service_detector()
    return await detector.is_service_available('google_ai')

async def check_pusher_available() -> bool:
    """Quick check if Pusher service is available."""
    detector = get_service_detector()
    return await detector.is_service_available('pusher')

# Service degradation handlers
class ServiceDegradationHandler:
    """Handler for managing service degradation scenarios."""
    
    @staticmethod
    async def handle_redis_unavailable():
        """Handle Redis unavailability by using memory cache."""
        logger.info("Redis unavailable - using in-memory cache fallback")
        return {}
    
    @staticmethod
    async def handle_ai_unavailable():
        """Handle AI service unavailability."""
        logger.info("AI service unavailable - AI features disabled")
        return {"error": "AI features temporarily unavailable"}
    
    @staticmethod
    async def handle_telegram_unavailable():
        """Handle Telegram service unavailability."""
        logger.info("Telegram service unavailable - monitoring features disabled")
        return {"error": "Message monitoring temporarily unavailable"}
    
    @staticmethod
    async def handle_pusher_unavailable():
        """Handle Pusher service unavailability."""
        logger.info("Pusher service unavailable - using polling fallback")
        return {"websocket_available": False, "polling_recommended": True}

def get_degradation_handler() -> ServiceDegradationHandler:
    """Get service degradation handler."""
    return ServiceDegradationHandler()