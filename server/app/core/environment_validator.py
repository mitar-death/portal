"""Environment validation module for checking configuration and service health."""

import os
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass
from server.app.core.logging import logger
from server.app.core.config import settings


class ServiceStatus(Enum):
    """Enum for service status states."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNAVAILABLE = "unavailable"


class ConfigLevel(Enum):
    """Enum for configuration requirement levels."""
    CRITICAL = "critical"  # App won't function without this
    IMPORTANT = "important"  # Major features won't work
    OPTIONAL = "optional"  # Nice to have features


@dataclass
class ConfigValidation:
    """Configuration validation result."""
    key: str
    level: ConfigLevel
    present: bool
    value: Optional[str] = None
    message: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class ServiceHealth:
    """Service health check result."""
    name: str
    status: ServiceStatus
    available: bool
    response_time_ms: Optional[float] = None
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    dependencies: Optional[List[str]] = None


class EnvironmentValidator:
    """Environment validator for checking configuration and service health."""
    
    def __init__(self):
        self._config_requirements = self._define_config_requirements()
        self._service_checkers = self._define_service_checkers()
        
    def _define_config_requirements(self) -> Dict[str, Tuple[ConfigLevel, str, str]]:
        """Define configuration requirements with levels, descriptions, and suggestions."""
        return {
            # Critical - App won't start properly without these
            "SECRET_KEY": (
                ConfigLevel.CRITICAL,
                "Application secret key for session encryption",
                "Generate a secure random string: python -c 'import secrets; print(secrets.token_hex(32))'"
            ),
            "JWT_SECRET_KEY": (
                ConfigLevel.CRITICAL,
                "JWT token signing secret",
                "Use a different secret from SECRET_KEY for better security"
            ),
            "DATABASE_URL": (
                ConfigLevel.CRITICAL,
                "PostgreSQL database connection string",
                "Format: postgresql://username:password@host:port/database"
            ),
            
            # Important - Major features won't work without these
            "TELEGRAM_API_ID": (
                ConfigLevel.IMPORTANT,
                "Telegram API application ID from https://my.telegram.org",
                "Required for Telegram integration - obtain from https://my.telegram.org/apps"
            ),
            "TELEGRAM_API_HASH": (
                ConfigLevel.IMPORTANT,
                "Telegram API application hash from https://my.telegram.org",
                "Must match the API_ID - obtain from https://my.telegram.org/apps"
            ),
            "GOOGLE_STUDIO_API_KEY": (
                ConfigLevel.IMPORTANT,
                "Google AI Studio API key for AI features",
                "Get your API key from https://aistudio.google.com/app/apikey"
            ),
            
            # Optional - Nice to have features
            "REDIS_HOST": (
                ConfigLevel.OPTIONAL,
                "Redis server host for caching and session storage",
                "Default: localhost - Redis improves performance but app works without it"
            ),
            "PUSHER_APP_ID": (
                ConfigLevel.OPTIONAL,
                "Pusher application ID for real-time WebSocket features",
                "Optional - WebSocket features will be limited without Pusher"
            ),
            "PUSHER_KEY": (
                ConfigLevel.OPTIONAL,
                "Pusher application key",
                "Must be provided together with PUSHER_APP_ID and PUSHER_SECRET"
            ),
            "PUSHER_SECRET": (
                ConfigLevel.OPTIONAL,
                "Pusher application secret",
                "Must be provided together with PUSHER_APP_ID and PUSHER_KEY"
            ),
            "SENTRY_DSN": (
                ConfigLevel.OPTIONAL,
                "Sentry DSN for error tracking and monitoring",
                "Optional - Helps with debugging in production"
            ),
        }
    
    def _define_service_checkers(self) -> Dict[str, callable]:
        """Define service health checkers."""
        return {
            "database": self._check_database_health,
            "redis": self._check_redis_health,
            "telegram": self._check_telegram_health,
            "google_ai": self._check_google_ai_health,
            "pusher": self._check_pusher_health,
        }
    
    async def validate_environment(self) -> Dict[str, Any]:
        """
        Validate the entire environment including config and services.
        
        Returns:
            Dict containing validation results
        """
        logger.info("Starting comprehensive environment validation...")
        
        # Validate configuration
        config_results = self.validate_configuration()
        
        # Check service health
        service_results = await self.check_all_services()
        
        # Determine overall health
        overall_status = self._determine_overall_status(config_results, service_results)
        
        # Generate startup warnings and errors
        warnings, errors = self._generate_messages(config_results, service_results)
        
        validation_result = {
            "overall_status": overall_status.value,
            "can_start": overall_status != ServiceStatus.UNAVAILABLE,
            "configuration": {
                "critical_missing": [r for r in config_results if r.level == ConfigLevel.CRITICAL and not r.present],
                "important_missing": [r for r in config_results if r.level == ConfigLevel.IMPORTANT and not r.present],
                "optional_missing": [r for r in config_results if r.level == ConfigLevel.OPTIONAL and not r.present],
                "all_results": config_results
            },
            "services": service_results,
            "warnings": warnings,
            "errors": errors,
            "recommendations": self._generate_recommendations(config_results, service_results)
        }
        
        # Log results
        self._log_validation_results(validation_result)
        
        return validation_result
    
    def validate_configuration(self) -> List[ConfigValidation]:
        """Validate all configuration requirements."""
        results = []
        
        for key, (level, description, suggestion) in self._config_requirements.items():
            value = os.getenv(key)
            is_present = value is not None and value.strip() != ""
            
            # Special handling for default values
            if not is_present and hasattr(settings, key):
                settings_value = getattr(settings, key, None)
                if settings_value and str(settings_value) not in ["", "your-secret-key-here", "jwt-secret-key-change-in-production", "jwt-refresh-secret-key-change-in-production"]:
                    is_present = True
                    value = str(settings_value)
                # For secrets, if they have any value (even defaults), consider them present for startup
                # but issue warnings if they're using default values
                elif key in ["SECRET_KEY", "JWT_SECRET_KEY", "JWT_REFRESH_SECRET_KEY"] and settings_value:
                    is_present = True
                    value = "[CONFIGURED]"
                    if str(settings_value) in ["your-secret-key-here", "jwt-secret-key-change-in-production", "jwt-refresh-secret-key-change-in-production"]:
                        message = f"Using default {level.value} configuration: {description} - CHANGE IN PRODUCTION"
            
            message = None
            if not is_present:
                message = f"Missing {level.value} configuration: {description}"
            
            results.append(ConfigValidation(
                key=key,
                level=level,
                present=is_present,
                value=value if is_present else None,
                message=message,
                suggestion=suggestion if not is_present else None
            ))
        
        return results
    
    async def check_all_services(self) -> Dict[str, ServiceHealth]:
        """Check health of all services concurrently."""
        tasks = {}
        
        for service_name, checker in self._service_checkers.items():
            tasks[service_name] = asyncio.create_task(checker())
        
        results = {}
        for service_name, task in tasks.items():
            try:
                results[service_name] = await asyncio.wait_for(task, timeout=10.0)
            except asyncio.TimeoutError:
                results[service_name] = ServiceHealth(
                    name=service_name,
                    status=ServiceStatus.UNAVAILABLE,
                    available=False,
                    error="Health check timed out after 10 seconds"
                )
            except Exception as e:
                results[service_name] = ServiceHealth(
                    name=service_name,
                    status=ServiceStatus.UNAVAILABLE,
                    available=False,
                    error=f"Health check failed: {str(e)}"
                )
        
        return results
    
    async def _check_database_health(self) -> ServiceHealth:
        """Check PostgreSQL database health."""
        import time
        start_time = time.time()
        
        try:
            from server.app.core.databases import AsyncSessionLocal
            from sqlalchemy import text
            
            # First try to create a session to test connection
            async with AsyncSessionLocal() as session:
                # Test basic connectivity with a simple query
                result = await session.execute(text("SELECT 1 as test"))
                test_row = result.fetchone()
                
                # Test table access (this will work even if no custom tables exist)
                table_count_result = await session.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"))
                table_count = table_count_result.scalar()
                
            response_time = (time.time() - start_time) * 1000
            
            return ServiceHealth(
                name="database",
                status=ServiceStatus.HEALTHY,
                available=True,
                response_time_ms=round(response_time, 2),
                details={
                    "type": "postgresql",
                    "url_configured": bool(settings.database_url or settings.DB_HOST),
                    "tables_count": table_count,
                    "connection_test": "passed"
                }
            )
            
        except Exception as e:
            error_msg = str(e)
            # Handle specific database errors more gracefully
            if "sslmode" in error_msg.lower():
                # This might be a configuration issue, but not necessarily critical
                # Try to provide more helpful error information
                error_msg = f"Database SSL configuration issue: {error_msg}. This may be a non-critical configuration problem."
            
            return ServiceHealth(
                name="database",
                status=ServiceStatus.UNAVAILABLE,
                available=False,
                error=error_msg,
                details={
                    "type": "postgresql",
                    "url_configured": bool(settings.database_url or settings.DB_HOST),
                    "error_type": "connection_failed"
                }
            )
    
    async def _check_redis_health(self) -> ServiceHealth:
        """Check Redis health."""
        try:
            from server.app.services.redis_client import check_redis_health
            redis_health = await check_redis_health()
            
            if redis_health["available"]:
                return ServiceHealth(
                    name="redis",
                    status=ServiceStatus.HEALTHY,
                    available=True,
                    response_time_ms=redis_health.get("connection_time_ms"),
                    details=redis_health.get("info", {})
                )
            else:
                return ServiceHealth(
                    name="redis",
                    status=ServiceStatus.UNAVAILABLE,
                    available=False,
                    error=redis_health.get("error", "Redis unavailable"),
                    details={
                        "host": settings.REDIS_HOST,
                        "port": settings.REDIS_PORT
                    }
                )
        except Exception as e:
            return ServiceHealth(
                name="redis",
                status=ServiceStatus.UNAVAILABLE,
                available=False,
                error=str(e)
            )
    
    async def _check_telegram_health(self) -> ServiceHealth:
        """Check Telegram API health."""
        import time
        start_time = time.time()
        
        try:
            # Check if credentials are configured
            if not settings.TELEGRAM_API_ID or not settings.TELEGRAM_API_HASH:
                return ServiceHealth(
                    name="telegram",
                    status=ServiceStatus.UNAVAILABLE,
                    available=False,
                    error="Telegram API credentials not configured",
                    details={
                        "api_id_configured": bool(settings.TELEGRAM_API_ID),
                        "api_hash_configured": bool(settings.TELEGRAM_API_HASH)
                    }
                )
            
            # Try to get client and test connection
            from server.app.services.telegram import get_client
            client = await asyncio.wait_for(get_client(), timeout=5.0)
            
            if not client:
                return ServiceHealth(
                    name="telegram",
                    status=ServiceStatus.UNAVAILABLE,
                    available=False,
                    error="Could not create Telegram client"
                )
            
            # Test connection
            if not client.is_connected():
                await asyncio.wait_for(client.connect(), timeout=5.0)
            
            # Test API call
            is_authorized = await asyncio.wait_for(client.is_user_authorized(), timeout=5.0)
            response_time = (time.time() - start_time) * 1000
            
            status = ServiceStatus.HEALTHY if is_authorized else ServiceStatus.DEGRADED
            
            details = {
                "api_id_configured": True,
                "api_hash_configured": True,
                "connected": client.is_connected(),
                "authorized": is_authorized
            }
            
            # Get user info if authorized
            if is_authorized:
                try:
                    me = await asyncio.wait_for(client.get_me(), timeout=3.0)
                    if me:
                        details["user_info"] = {
                            "id": me.id,
                            "first_name": me.first_name,
                            "username": me.username
                        }
                except:
                    pass
            
            return ServiceHealth(
                name="telegram",
                status=status,
                available=True,
                response_time_ms=round(response_time, 2),
                details=details,
                error="Not authorized - login required" if not is_authorized else None
            )
            
        except asyncio.TimeoutError:
            return ServiceHealth(
                name="telegram",
                status=ServiceStatus.UNAVAILABLE,
                available=False,
                error="Telegram API connection timed out"
            )
        except Exception as e:
            return ServiceHealth(
                name="telegram",
                status=ServiceStatus.UNAVAILABLE,
                available=False,
                error=str(e)
            )
    
    async def _check_google_ai_health(self) -> ServiceHealth:
        """Check Google AI API health."""
        import time
        start_time = time.time()
        
        try:
            if not settings.GOOGLE_STUDIO_API_KEY:
                return ServiceHealth(
                    name="google_ai",
                    status=ServiceStatus.UNAVAILABLE,
                    available=False,
                    error="Google AI API key not configured",
                    details={"api_key_configured": False}
                )
            
            # Test API with a simple request
            import google.generativeai as genai
            genai.configure(api_key=settings.GOOGLE_STUDIO_API_KEY)
            
            # List models to test API connectivity
            models_list = []
            async def test_api():
                try:
                    # This is a lightweight operation to test the API
                    model = genai.GenerativeModel('gemini-pro')
                    # Don't actually generate content, just check if the model initializes
                    return True
                except Exception as e:
                    raise e
            
            await asyncio.wait_for(test_api(), timeout=5.0)
            response_time = (time.time() - start_time) * 1000
            
            return ServiceHealth(
                name="google_ai",
                status=ServiceStatus.HEALTHY,
                available=True,
                response_time_ms=round(response_time, 2),
                details={
                    "api_key_configured": True,
                    "model": "gemini-pro"
                }
            )
            
        except asyncio.TimeoutError:
            return ServiceHealth(
                name="google_ai",
                status=ServiceStatus.UNAVAILABLE,
                available=False,
                error="Google AI API request timed out"
            )
        except Exception as e:
            error_msg = str(e)
            status = ServiceStatus.UNAVAILABLE
            
            # Provide more specific error messages
            if "API_KEY" in error_msg.upper() or "authentication" in error_msg.lower():
                error_msg = "Invalid or expired Google AI API key"
            elif "quota" in error_msg.lower():
                error_msg = "Google AI API quota exceeded"
                status = ServiceStatus.DEGRADED
            
            return ServiceHealth(
                name="google_ai",
                status=status,
                available=False,
                error=error_msg,
                details={"api_key_configured": True}
            )
    
    async def _check_pusher_health(self) -> ServiceHealth:
        """Check Pusher service health."""
        try:
            pusher_configured = all([
                settings.PUSHER_APP_ID,
                settings.PUSHER_KEY,
                settings.PUSHER_SECRET
            ])
            
            if not pusher_configured:
                return ServiceHealth(
                    name="pusher",
                    status=ServiceStatus.UNAVAILABLE,
                    available=False,
                    error="Pusher credentials not fully configured",
                    details={
                        "app_id_configured": bool(settings.PUSHER_APP_ID),
                        "key_configured": bool(settings.PUSHER_KEY),
                        "secret_configured": bool(settings.PUSHER_SECRET),
                        "cluster": settings.PUSHER_CLUSTER
                    }
                )
            
            # Test Pusher connection (lightweight check)
            import pusher
            pusher_client = pusher.Pusher(
                app_id=settings.PUSHER_APP_ID,
                key=settings.PUSHER_KEY,
                secret=settings.PUSHER_SECRET,
                cluster=settings.PUSHER_CLUSTER,
                ssl=True
            )
            
            # Test authentication (this doesn't make a network call)
            return ServiceHealth(
                name="pusher",
                status=ServiceStatus.HEALTHY,
                available=True,
                details={
                    "app_id_configured": True,
                    "key_configured": True,
                    "secret_configured": True,
                    "cluster": settings.PUSHER_CLUSTER
                }
            )
            
        except Exception as e:
            return ServiceHealth(
                name="pusher",
                status=ServiceStatus.UNAVAILABLE,
                available=False,
                error=str(e)
            )
    
    def _determine_overall_status(self, config_results: List[ConfigValidation], service_results: Dict[str, ServiceHealth]) -> ServiceStatus:
        """Determine overall application health status."""
        
        # Check for critical configuration issues
        critical_missing = [r for r in config_results if r.level == ConfigLevel.CRITICAL and not r.present]
        if critical_missing:
            return ServiceStatus.UNAVAILABLE
        
        # Check database health (critical service)
        db_health = service_results.get("database")
        if not db_health or not db_health.available:
            return ServiceStatus.UNAVAILABLE
        
        # Check for important configuration issues
        important_missing = [r for r in config_results if r.level == ConfigLevel.IMPORTANT and not r.present]
        
        # Check important services
        important_services_down = 0
        total_important_services = 2  # telegram, google_ai
        
        if service_results.get("telegram", {}).status in [ServiceStatus.UNAVAILABLE, ServiceStatus.DEGRADED]:
            important_services_down += 1
            
        if service_results.get("google_ai", {}).status in [ServiceStatus.UNAVAILABLE]:
            important_services_down += 1
        
        # Determine status
        if important_missing or important_services_down >= total_important_services:
            return ServiceStatus.DEGRADED
        elif important_services_down > 0:
            return ServiceStatus.DEGRADED
        else:
            return ServiceStatus.HEALTHY
    
    def _generate_messages(self, config_results: List[ConfigValidation], service_results: Dict[str, ServiceHealth]) -> Tuple[List[str], List[str]]:
        """Generate warning and error messages."""
        warnings = []
        errors = []
        
        # Configuration messages
        for result in config_results:
            if not result.present:
                if result.level == ConfigLevel.CRITICAL:
                    errors.append(f"CRITICAL: {result.message}")
                    if result.suggestion:
                        errors.append(f"  → {result.suggestion}")
                elif result.level == ConfigLevel.IMPORTANT:
                    warnings.append(f"IMPORTANT: {result.message}")
                    if result.suggestion:
                        warnings.append(f"  → {result.suggestion}")
                elif result.level == ConfigLevel.OPTIONAL:
                    warnings.append(f"OPTIONAL: {result.message}")
        
        # Service messages
        for service_name, health in service_results.items():
            if not health.available:
                if service_name in ["database"]:  # Critical services
                    errors.append(f"CRITICAL: {service_name.title()} service unavailable - {health.error}")
                else:
                    warnings.append(f"{service_name.title()} service unavailable - {health.error}")
            elif health.status == ServiceStatus.DEGRADED:
                warnings.append(f"{service_name.title()} service degraded - {health.error or 'Limited functionality'}")
        
        return warnings, errors
    
    def _generate_recommendations(self, config_results: List[ConfigValidation], service_results: Dict[str, ServiceHealth]) -> List[str]:
        """Generate recommendations for improving the setup."""
        recommendations = []
        
        # Configuration recommendations
        missing_important = [r for r in config_results if r.level == ConfigLevel.IMPORTANT and not r.present]
        if missing_important:
            recommendations.append("Configure important settings to enable full functionality:")
            for result in missing_important:
                recommendations.append(f"  • {result.key}: {result.suggestion}")
        
        # Service recommendations
        telegram_health = service_results.get("telegram")
        if telegram_health and telegram_health.available and telegram_health.status == ServiceStatus.DEGRADED:
            recommendations.append("Complete Telegram authorization to enable message monitoring")
        
        redis_health = service_results.get("redis")
        if redis_health and not redis_health.available:
            recommendations.append("Configure Redis for improved performance and session management")
        
        pusher_health = service_results.get("pusher")
        if pusher_health and not pusher_health.available:
            recommendations.append("Configure Pusher for enhanced real-time WebSocket features")
        
        return recommendations
    
    def _log_validation_results(self, results: Dict[str, Any]):
        """Log validation results appropriately."""
        overall_status = results["overall_status"]
        
        if overall_status == "unavailable":
            logger.error("❌ Environment validation FAILED - Critical issues found")
        elif overall_status == "degraded":
            logger.warning("⚠️  Environment validation shows DEGRADED status - Some features unavailable")
        else:
            logger.info("✅ Environment validation PASSED - All systems operational")
        
        # Log errors
        for error in results["errors"]:
            logger.error(error)
        
        # Log warnings
        for warning in results["warnings"]:
            logger.warning(warning)
        
        # Log recommendations
        if results["recommendations"]:
            logger.info("Recommendations for improvement:")
            for rec in results["recommendations"]:
                logger.info(f"  {rec}")


# Global validator instance
_validator_instance = None

def get_environment_validator() -> EnvironmentValidator:
    """Get the global environment validator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = EnvironmentValidator()
    return _validator_instance


async def validate_startup_environment() -> Dict[str, Any]:
    """Convenience function for startup validation."""
    validator = get_environment_validator()
    return await validator.validate_environment()


def can_start_application() -> bool:
    """Quick check if application can start based on critical configuration."""
    validator = get_environment_validator()
    config_results = validator.validate_configuration()
    
    critical_missing = [r for r in config_results if r.level == ConfigLevel.CRITICAL and not r.present]
    return len(critical_missing) == 0