"""QnAIGC image-edit provider integration."""

from __future__ import annotations

import base64
import binascii
import io
import logging
import re
import warnings
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, UnidentifiedImageError

from app.config import Settings
from app.exceptions.errors import AppError
from app.models.job import ProviderResult


logger = logging.getLogger(__name__)


def image_file_to_data_url(image_path: Path) -> str:
    """Encode a local PNG as a MIME-qualified Base64 Data URL."""

    image_bytes = image_path.read_bytes()
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"


class QnAIGCImageEditProvider:
    """Call the remote edit endpoint exactly once for one composite canvas."""

    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self._transport = transport

    async def edit(
        self,
        composite_path: Path,
        prompt: str,
        output_path: Path,
    ) -> ProviderResult:
        token = self.settings.QNAIGC_API_TOKEN.strip()
        if not token:
            raise AppError(
                code="MISSING_API_TOKEN",
                message="未配置图像编辑服务 API Token。",
                status_code=503,
            )

        composite_data_url = image_file_to_data_url(composite_path)
        payload = {
            "model": self.settings.IMAGE_MODEL,
            "prompt": prompt,
            "image": [composite_data_url],
            "quality": self.settings.IMAGE_QUALITY,
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(float(self.settings.REQUEST_TIMEOUT_SECONDS))
        url = self._endpoint_url()

        try:
            if self._transport is None:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)
            else:
                async with httpx.AsyncClient(
                    timeout=timeout,
                    transport=self._transport,
                ) as client:
                    response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            response_body = self._safe_response_prefix(exc.response.text, token)
            logger.error(
                "QnAIGC request failed: status=%s response_body_prefix=%r",
                exc.response.status_code,
                response_body,
            )
            raise AppError(
                code="PROVIDER_REQUEST_FAILED",
                message="图像编辑服务请求失败。",
                status_code=502,
                details={"provider_status": exc.response.status_code},
            ) from exc
        except httpx.RequestError as exc:
            # Do not log request headers/body: they contain the bearer token and
            # the complete Base64 canvas. The exception class is sufficient for
            # operational categorization without exposing either secret.
            logger.error("QnAIGC transport failure: type=%s", type(exc).__name__)
            raise AppError(
                code="PROVIDER_REQUEST_FAILED",
                message="图像编辑服务请求失败。",
                status_code=502,
            ) from exc

        response_json = self._parse_response_json(response)
        encoded_image = self._extract_base64(response_json)
        raw_image, image_size = self._decode_and_validate_image(encoded_image)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(raw_image)
        self._verify_output_file(output_path)
        return ProviderResult(
            output_path=output_path,
            width=image_size[0],
            height=image_size[1],
        )

    def _endpoint_url(self) -> str:
        host = self.settings.QNAIGC_API_HOST.strip().rstrip("/")
        if not host.startswith(("http://", "https://")):
            host = f"https://{host}"
        path = self.settings.QNAIGC_API_PATH.strip()
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{host}{path}"

    @staticmethod
    def _safe_response_prefix(response_body: str, token: str) -> str:
        """Limit provider diagnostics while redacting echoed credentials/images."""

        prefix = response_body[:2000]
        if token:
            prefix = prefix.replace(token, "<redacted-token>")
        prefix = re.sub(
            r"(data:image/[a-zA-Z0-9.+-]+;base64,)[a-zA-Z0-9+/=]+",
            r"\1<redacted-image>",
            prefix,
        )
        # Also cover providers that echo the array value without its Data URL
        # prefix. Long Base64-like runs are not useful diagnostics.
        return re.sub(
            r"(?<![a-zA-Z0-9+/])[a-zA-Z0-9+/]{80,}={0,2}(?![a-zA-Z0-9+/=])",
            "<redacted-image>",
            prefix,
        )

    @staticmethod
    def _parse_response_json(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except (ValueError, UnicodeError) as exc:
            raise AppError(
                code="INVALID_PROVIDER_RESPONSE",
                message="图像编辑服务返回了无效响应。",
                status_code=502,
            ) from exc
        if not isinstance(payload, dict):
            raise AppError(
                code="INVALID_PROVIDER_RESPONSE",
                message="图像编辑服务返回了无效响应。",
                status_code=502,
            )
        return payload

    @staticmethod
    def _extract_base64(payload: dict[str, Any]) -> str:
        data = payload.get("data")
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise AppError(
                code="INVALID_PROVIDER_RESPONSE",
                message="图像编辑服务响应中缺少图片数据。",
                status_code=502,
            )
        encoded_image = data[0].get("b64_json")
        if not isinstance(encoded_image, str) or not encoded_image.strip():
            raise AppError(
                code="INVALID_PROVIDER_RESPONSE",
                message="图像编辑服务响应中缺少图片数据。",
                status_code=502,
            )
        return encoded_image.strip()

    @staticmethod
    def _decode_and_validate_image(encoded_image: str) -> tuple[bytes, tuple[int, int]]:
        try:
            raw_image = base64.b64decode(encoded_image, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise AppError(
                code="INVALID_PROVIDER_BASE64",
                message="图像编辑服务返回的图片编码无效。",
                status_code=502,
            ) from exc

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw_image)) as verifying_image:
                    verifying_image.verify()
                with Image.open(io.BytesIO(raw_image)) as decoded_image:
                    decoded_image.load()
                    image_size = decoded_image.size
        except (
            UnidentifiedImageError,
            OSError,
            SyntaxError,
            ValueError,
            Image.DecompressionBombWarning,
            Image.DecompressionBombError,
        ) as exc:
            raise AppError(
                code="INVALID_PROVIDER_RESPONSE",
                message="图像编辑服务返回的内容不是有效图片。",
                status_code=502,
            ) from exc
        return raw_image, image_size

    @staticmethod
    def _verify_output_file(output_path: Path) -> None:
        try:
            with Image.open(output_path) as image:
                image.verify()
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            raise AppError(
                code="INVALID_PROVIDER_RESPONSE",
                message="图像编辑服务返回的内容不是有效图片。",
                status_code=502,
            ) from exc
