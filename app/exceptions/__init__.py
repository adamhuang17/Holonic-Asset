"""Structured application exceptions and FastAPI handler registration."""

from app.exceptions.errors import (
    ERROR_DEFINITIONS,
    AppError,
    ErrorCode,
    ErrorDefinition,
    error_for,
)
from app.exceptions.handlers import register_exception_handlers

__all__ = [
    "AppError",
    "ERROR_DEFINITIONS",
    "ErrorCode",
    "ErrorDefinition",
    "error_for",
    "register_exception_handlers",
]
