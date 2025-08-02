"""Exception handlers"""

from typing import Union

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from server.app.core.config import settings
from server.app.utils.http import build_error_response


class AppException(Exception):
    """Base application exception."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundException(AppException):
    """Raised when a resource is not found."""


class BadRequestException(AppException):
    """Raised for invalid user input."""


class UnauthorizedAccess(AppException):
    """Raised when access is denied due to lack of credentials."""


class ConflictError(AppException):
    """Raised when a conflicting resource already exists."""


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global handler for unhandled exceptions. Logs the error and returns a generic JSON error.

    Args:
        request (Request): The incoming request object.
        exc (Exception): The exception that was raised.

    Returns:
        JSONResponse: Standardized 500 error response.
    """
    logger.opt(exception=exc).error(
        f"Unhandled exception during request: {request.method} {request.url}"
    )

    status_code = HTTP_500_INTERNAL_SERVER_ERROR
    return JSONResponse(
        status_code=status_code,
        content=build_error_response(
            request,
            type(exc).__name__,
            (
                str(exc)
                if settings.ENV != "production"
                else "Internal server error. Please try again later."
            ),
            status_code,
        ),
    )


async def app_exception_handler(
    request: Request, exc: Union[AppException, HTTPException]
) -> JSONResponse:
    """
    Handles all AppException subclasses.
    """
    logger.warning(f"[Handled] {type(exc).__name__}: {str(exc)}")
    status_map = {
        NotFoundException: HTTP_404_NOT_FOUND,
        HTTPException: HTTP_404_NOT_FOUND,
        BadRequestException: HTTP_400_BAD_REQUEST,
        UnauthorizedAccess: HTTP_401_UNAUTHORIZED,
        ConflictError: HTTP_409_CONFLICT,
    }
    status_code = exc.status_code or status_map.get(
        type(exc), HTTP_500_INTERNAL_SERVER_ERROR
    )

    logger.debug(f"{type(exc)} with status code {status_code}")

    return JSONResponse(
        status_code=status_code,
        content=build_error_response(
            request, type(exc).__name__, str(exc), status_code
        ),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handles FastAPI validation errors (e.g. invalid request body).
    """
    exception = type(exc).__name__
    status_code = (
        exc.status_code if hasattr(exc, "status_code") else HTTP_400_BAD_REQUEST
    )

    errors = [f"{err['msg']}: {err['loc'][1]}" for err in exc.errors()]

    logger.warning(f"[{exception} Error] on {request.url}: {exc.errors()}")
    return JSONResponse(
        status_code=status_code,
        content=build_error_response(request, exception, errors, status_code),
    )
