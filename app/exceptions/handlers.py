"""FastAPI exception handlers returning the project's error envelope."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions.errors import AppError, ErrorCode, error_for

logger = logging.getLogger(__name__)


def _error_response(error: AppError) -> JSONResponse:
    content: dict[str, Any] = {
        "error": {
            "code": error.code,
            "message": error.message,
            "details": error.details,
        }
    }
    return JSONResponse(
        status_code=error.status_code,
        content=jsonable_encoder(content),
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    # Log only metadata known not to contain the token or image Data URL.
    logger.warning(
        "request_failed path=%s code=%s status=%s",
        request.url.path,
        exc.code,
        exc.status_code,
    )
    return _error_response(exc)


async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = exc.errors()
    missing_fields = {
        str(error.get("loc", ("",))[-1])
        for error in errors
        if error.get("type") == "missing"
    }

    if "files" in missing_fields:
        public_error = error_for(ErrorCode.NO_FILES)
    elif "instruction" in missing_fields:
        public_error = error_for(ErrorCode.EMPTY_INSTRUCTION)
    elif "image_mapping" in missing_fields:
        public_error = error_for(ErrorCode.MISSING_IMAGE_MAPPING)
    else:
        safe_errors = [
            {
                "type": str(error.get("type", "validation_error")),
                "loc": [str(part) for part in error.get("loc", ())],
                "message": str(error.get("msg", "Invalid value")),
            }
            for error in errors
        ]
        public_error = error_for(
            ErrorCode.VALIDATION_ERROR,
            details={"errors": safe_errors},
        )

    logger.warning(
        "request_validation_failed path=%s code=%s",
        request.url.path,
        public_error.code,
    )
    return _error_response(public_error)


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    messages = {
        404: "请求的资源不存在。",
        405: "请求方法不允许。",
    }
    public_error = AppError(
        ErrorCode.HTTP_ERROR,
        message=messages.get(exc.status_code, "HTTP 请求失败。"),
        status_code=exc.status_code,
    )
    logger.warning(
        "http_error path=%s status=%s",
        request.url.path,
        exc.status_code,
    )
    return _error_response(public_error)


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    # Do not interpolate the exception itself: third-party exceptions can embed
    # request headers or the (very large) Base64 request body in their message.
    logger.error(
        "unhandled_exception path=%s exception_type=%s",
        request.url.path,
        type(exc).__name__,
    )
    return _error_response(error_for(ErrorCode.INTERNAL_ERROR))


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
