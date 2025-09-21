"""Health monitoring routes with comprehensive service status."""

from datetime import datetime
import asyncio
from fastapi import APIRouter, Request, HTTPException
from server.app.core.logging import logger
from server.app.core.environment_validator import get_environment_validator
from server.app.services.monitor import get_system_health

health_routes = APIRouter()


@health_routes.get("/health", tags=["Health"])
async def basic_health_check():
    """
    Basic health check endpoint for load balancers and monitoring tools.
    Returns simple status and basic information.
    """
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "tg-portal-api",
            "version": "1.0.0",
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable") from e


@health_routes.get("/health/detailed", tags=["Health"])
async def detailed_health_check(request: Request):
    """
    Comprehensive health check with detailed service status.
    Includes environment validation and all service dependencies.
    """
    try:
        # Get environment validation from app state (cached from startup)
        environment_validation = getattr(
            request.app.state, "environment_validation", None
        )

        # If not available, perform fresh validation (shouldn't happen in normal cases)
        if not environment_validation:
            validator = get_environment_validator()
            environment_validation = await validator.validate_environment()

        # Get system health information
        try:
            system_health = await asyncio.wait_for(get_system_health(), timeout=10.0)
        except asyncio.TimeoutError:
            system_health = {
                "error": "System health check timed out",
                "status": "timeout",
            }
        except Exception as e:
            system_health = {
                "error": f"System health check failed: {str(e)}",
                "status": "error",
            }

        # Build comprehensive health response
        health_response = {
            "timestamp": datetime.now().isoformat(),
            "service": "tg-portal-api",
            "version": "1.0.0",
            "overall_status": environment_validation.get("overall_status", "unknown"),
            "can_serve_requests": True,  # If we're responding, we can serve requests
            "degraded_features": [],
            "environment": {
                "validation_status": environment_validation.get("overall_status"),
                "configuration": {
                    "critical_issues": len(
                        environment_validation.get("configuration", {}).get(
                            "critical_missing", []
                        )
                    ),
                    "important_issues": len(
                        environment_validation.get("configuration", {}).get(
                            "important_missing", []
                        )
                    ),
                    "optional_issues": len(
                        environment_validation.get("configuration", {}).get(
                            "optional_missing", []
                        )
                    ),
                },
            },
            "services": environment_validation.get("services", {}),
            "system": system_health,
            "recommendations": environment_validation.get("recommendations", []),
        }

        # Add degraded features list
        services = environment_validation.get("services", {})
        for service_name, service_health in services.items():
            if not service_health.available or service_health.status in [
                "degraded",
                "unavailable",
            ]:
                feature_impact = {
                    "database": "Core functionality severely limited",
                    "redis": "Performance degraded, no caching",
                    "telegram": "Message monitoring unavailable",
                    "google_ai": "AI features unavailable",
                    "pusher": "Real-time features limited",
                }
                if service_name in feature_impact:
                    health_response["degraded_features"].append(
                        {
                            "service": service_name,
                            "status": service_health.status,
                            "impact": feature_impact[service_name],
                        }
                    )

        # Determine HTTP status code
        overall_status = environment_validation.get("overall_status")
        if overall_status == "unavailable":
            status_code = 503  # Service Unavailable
        elif overall_status == "degraded":
            status_code = 200  # OK but with warnings
        else:
            status_code = 200  # Healthy

        return health_response

    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        return {
            "timestamp": datetime.now().isoformat(),
            "service": "tg-portal-api",
            "overall_status": "error",
            "error": f"Health check failed: {str(e)}",
            "can_serve_requests": True,  # We're still able to respond
        }


@health_routes.get("/health/services", tags=["Health"])
async def services_health_check():
    """
    Service-specific health check for individual service monitoring.
    Returns status of each external dependency.
    """
    try:
        validator = get_environment_validator()

        # Run service checks with timeout
        try:
            services_health = await asyncio.wait_for(
                validator.check_all_services(), timeout=15.0
            )
        except asyncio.TimeoutError:
            return {
                "timestamp": datetime.now().isoformat(),
                "error": "Service health checks timed out",
                "services": {},
                "status": "timeout",
            }

        # Format response for service monitoring
        services_status = {}
        overall_healthy = True

        for service_name, health in services_health.items():
            services_status[service_name] = {
                "status": health.status,
                "available": health.available,
                "response_time_ms": health.response_time_ms,
                "error": health.error,
                "details": health.details,
            }

            # Check if any critical services are down
            if service_name in ["database"] and not health.available:
                overall_healthy = False

        return {
            "timestamp": datetime.now().isoformat(),
            "services": services_status,
            "overall_healthy": overall_healthy,
            "summary": {
                "total_services": len(services_status),
                "healthy": len([s for s in services_status.values() if s["available"]]),
                "unhealthy": len(
                    [s for s in services_status.values() if not s["available"]]
                ),
            },
        }

    except Exception as e:
        logger.error(f"Services health check failed: {e}")
        return {
            "timestamp": datetime.now().isoformat(),
            "error": f"Services health check failed: {str(e)}",
            "services": {},
            "status": "error",
        }


@health_routes.get("/health/readiness", tags=["Health"])
async def readiness_check(request: Request):
    """
    Kubernetes-style readiness probe.
    Returns 200 if the application is ready to serve traffic.
    """
    try:
        # Get cached environment validation
        environment_validation = getattr(
            request.app.state, "environment_validation", None
        )

        if not environment_validation:
            # If no validation available, assume we can serve requests
            # since we're responding to this probe
            return {"ready": True, "timestamp": datetime.now().isoformat()}

        # Application is ready if it can start (not unavailable)
        can_serve = environment_validation.get("can_start", True)
        overall_status = environment_validation.get("overall_status")

        if not can_serve or overall_status == "unavailable":
            raise HTTPException(
                status_code=503,
                detail={
                    "ready": False,
                    "reason": "Critical services unavailable",
                    "timestamp": datetime.now().isoformat(),
                },
            )

        return {
            "ready": True,
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "ready": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
        ) from e


@health_routes.get("/health/liveness", tags=["Health"])
async def liveness_check():
    """
    Kubernetes-style liveness probe.
    Returns 200 if the application process is alive and responding.
    """
    try:
        # Simple check to ensure the application is responding
        # If we can execute this function, the app is alive
        return {
            "alive": True,
            "timestamp": datetime.now().isoformat(),
            "uptime_check": "passed",
        }
    except Exception as e:
        logger.error(f"Liveness check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "alive": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
        ) from e
