"""Application error codes and their safe public representations."""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    NO_FILES = "NO_FILES"
    TOO_FEW_FILES = "TOO_FEW_FILES"
    TOO_MANY_FILES = "TOO_MANY_FILES"
    EMPTY_INSTRUCTION = "EMPTY_INSTRUCTION"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    INVALID_IMAGE_FORMAT = "INVALID_IMAGE_FORMAT"
    INVALID_IMAGE_CONTENT = "INVALID_IMAGE_CONTENT"
    MISSING_API_TOKEN = "MISSING_API_TOKEN"
    PROVIDER_REQUEST_FAILED = "PROVIDER_REQUEST_FAILED"
    INVALID_PROVIDER_RESPONSE = "INVALID_PROVIDER_RESPONSE"
    INVALID_PROVIDER_BASE64 = "INVALID_PROVIDER_BASE64"
    OUTPUT_ASPECT_RATIO_MISMATCH = "OUTPUT_ASPECT_RATIO_MISMATCH"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    HTTP_ERROR = "HTTP_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True, slots=True)
class ErrorDefinition:
    message: str
    status_code: int


ERROR_DEFINITIONS: dict[ErrorCode, ErrorDefinition] = {
    ErrorCode.NO_FILES: ErrorDefinition("请上传图片文件。", 400),
    ErrorCode.TOO_FEW_FILES: ErrorDefinition("至少需要上传 2 张图片。", 400),
    ErrorCode.TOO_MANY_FILES: ErrorDefinition("最多只能上传 6 张图片。", 400),
    ErrorCode.EMPTY_INSTRUCTION: ErrorDefinition("编辑描述不能为空。", 400),
    ErrorCode.FILE_TOO_LARGE: ErrorDefinition("单张图片不能超过 10MB。", 413),
    ErrorCode.INVALID_IMAGE_FORMAT: ErrorDefinition(
        "只支持 PNG、JPG、JPEG 和 WEBP。", 400
    ),
    ErrorCode.INVALID_IMAGE_CONTENT: ErrorDefinition("图片内容无效或已损坏。", 400),
    ErrorCode.MISSING_API_TOKEN: ErrorDefinition("未配置 QnAIGC API Token。", 503),
    ErrorCode.PROVIDER_REQUEST_FAILED: ErrorDefinition(
        "图像编辑服务请求失败。", 502
    ),
    ErrorCode.INVALID_PROVIDER_RESPONSE: ErrorDefinition(
        "图像编辑服务返回了无效响应。", 502
    ),
    ErrorCode.INVALID_PROVIDER_BASE64: ErrorDefinition(
        "图像编辑服务返回了无效的图片数据。", 502
    ),
    ErrorCode.OUTPUT_ASPECT_RATIO_MISMATCH: ErrorDefinition(
        "模型输出画布的宽高比与输入不一致。", 422
    ),
    ErrorCode.JOB_NOT_FOUND: ErrorDefinition("任务不存在。", 404),
    ErrorCode.VALIDATION_ERROR: ErrorDefinition("请求参数校验失败。", 422),
    ErrorCode.HTTP_ERROR: ErrorDefinition("HTTP 请求失败。", 400),
    ErrorCode.INTERNAL_ERROR: ErrorDefinition("服务器内部错误。", 500),
}


class AppError(Exception):
    """A safe, structured exception intended to cross the HTTP boundary.

    ``message`` and ``status_code`` may be supplied explicitly.  When omitted,
    the values registered for ``code`` are used.  Unknown custom codes are also
    accepted when a caller provides its own message/status.
    """

    def __init__(
        self,
        code: ErrorCode | str,
        message: str | None = None,
        status_code: int | None = None,
        details: Any | None = None,
    ) -> None:
        code_value = code.value if isinstance(code, ErrorCode) else str(code)
        try:
            known_code = ErrorCode(code_value)
        except ValueError:
            known_code = None

        definition = ERROR_DEFINITIONS.get(known_code) if known_code else None
        self.code = code_value
        self.message = message or (
            definition.message if definition else "请求处理失败。"
        )
        self.status_code = status_code or (
            definition.status_code if definition else 400
        )
        self.details = details
        super().__init__(self.message)


def error_for(
    code: ErrorCode | str,
    *,
    message: str | None = None,
    status_code: int | None = None,
    details: Any | None = None,
) -> AppError:
    """Create an :class:`AppError` using the registered public defaults."""

    return AppError(code, message, status_code, details)
