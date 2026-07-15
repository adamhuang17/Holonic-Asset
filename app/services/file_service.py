"""Upload validation and safe local persistence."""

from __future__ import annotations

import io
import re
import unicodedata
import warnings
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.config import Settings
from app.exceptions.errors import AppError


_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
_ALLOWED_PIL_FORMATS = {"PNG", "JPEG", "WEBP"}
_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class SavedUpload:
    """A validated, normalized upload persisted for one job."""

    path: Path
    original_name: str
    stored_name: str
    alpha_path: Path
    original_width: int
    original_height: int

    @property
    def original_size(self) -> tuple[int, int]:
        return self.original_width, self.original_height

    @property
    def original_alpha_path(self) -> Path:
        """Manifest-friendly alias for the persisted alpha artifact."""

        return self.alpha_path


def sanitize_filename(filename: str | None) -> str:
    """Return a display-only filename without path or control characters."""

    candidate = unicodedata.normalize("NFKC", filename or "")
    # Browsers normally send a basename, but some clients still send a full
    # Windows path. Normalize both separators before selecting the last part.
    candidate = candidate.replace("\\", "/").rsplit("/", 1)[-1]
    candidate = "".join(char for char in candidate if ord(char) >= 32 and ord(char) != 127)
    candidate = re.sub(r'[<>:"/\\|?*]', "_", candidate).strip().rstrip(". ")
    return candidate or "upload"


class FileService:
    """Validate multipart image uploads and normalize them to RGBA PNG files."""

    def __init__(self, settings: Settings, data_root: Path | None = None) -> None:
        self.settings = settings
        configured_root = data_root if data_root is not None else settings.DATA_DIR
        self.data_root = Path(configured_root).resolve()

    async def save_uploads(
        self,
        job_id: str,
        files: list[UploadFile],
    ) -> list[SavedUpload]:
        """Validate and persist all uploads belonging to ``job_id``.

        Bytes are accumulated in bounded chunks before Pillow verification.
        The verified image is deliberately reopened and decoded into RGBA; a
        Pillow object on which ``verify()`` was called is never reused.
        """

        self._validate_file_count(files)
        upload_directory = self._data_path("uploads", job_id)
        upload_directory.mkdir(parents=True, exist_ok=True)

        saved: list[SavedUpload] = []
        for index, upload in enumerate(files):
            saved.append(await self._save_one(upload, index, upload_directory))
        return saved

    def _validate_file_count(self, files: list[UploadFile]) -> None:
        count = len(files)
        if count == 0:
            raise AppError(
                code="NO_FILES",
                message="请至少上传一张图片。",
                status_code=400,
            )
        if count < self.settings.MIN_FILES:
            raise AppError(
                code="TOO_FEW_FILES",
                message=f"至少需要上传 {self.settings.MIN_FILES} 张图片。",
                status_code=400,
            )
        if count > self.settings.MAX_FILES:
            raise AppError(
                code="TOO_MANY_FILES",
                message=f"最多只能上传 {self.settings.MAX_FILES} 张图片。",
                status_code=400,
            )

    async def _save_one(
        self,
        upload: UploadFile,
        index: int,
        upload_directory: Path,
    ) -> SavedUpload:
        original_name = sanitize_filename(upload.filename)
        extension = Path(original_name).suffix.lower()
        if extension not in _ALLOWED_EXTENSIONS:
            raise AppError(
                code="INVALID_IMAGE_FORMAT",
                message="只支持 PNG、JPG、JPEG 和 WEBP。",
                status_code=400,
                details={"index": index, "filename": original_name},
            )

        image_bytes = await self._read_bounded(upload, index, original_name)
        rgba = self._verify_and_open_rgba(image_bytes, index, original_name)
        try:
            original_width, original_height = rgba.size
            stored_name = f"{uuid4().hex}.png"
            stored_path = self._child_path(upload_directory, stored_name)
            alpha_path = self._child_path(upload_directory, f"{index}_alpha.png")

            rgba.save(stored_path, format="PNG")
            rgba.getchannel("A").save(alpha_path, format="PNG")
            self._verify_saved_image(stored_path)
            self._verify_saved_image(alpha_path)
        finally:
            rgba.close()

        return SavedUpload(
            path=stored_path,
            original_name=original_name,
            stored_name=stored_name,
            alpha_path=alpha_path,
            original_width=original_width,
            original_height=original_height,
        )

    async def _read_bounded(
        self,
        upload: UploadFile,
        index: int,
        original_name: str,
    ) -> bytes:
        limit = int(self.settings.MAX_FILE_SIZE_MB * 1024 * 1024)
        collected = bytearray()
        await upload.seek(0)
        while True:
            chunk = await upload.read(_CHUNK_SIZE)
            if not chunk:
                break
            collected.extend(chunk)
            if len(collected) > limit:
                raise AppError(
                    code="FILE_TOO_LARGE",
                    message=f"单张图片不能超过 {self.settings.MAX_FILE_SIZE_MB}MB。",
                    status_code=413,
                    details={"index": index, "filename": original_name},
                )
        return bytes(collected)

    @staticmethod
    def _verify_and_open_rgba(
        image_bytes: bytes,
        index: int,
        original_name: str,
    ) -> Image.Image:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(image_bytes)) as verifying_image:
                    detected_format = (verifying_image.format or "").upper()
                    verifying_image.verify()
            if detected_format not in _ALLOWED_PIL_FORMATS:
                raise AppError(
                    code="INVALID_IMAGE_FORMAT",
                    message="只支持 PNG、JPG、JPEG 和 WEBP。",
                    status_code=400,
                    details={"index": index, "filename": original_name},
                )

            # Reopen after verify(), force decoding, and detach the returned
            # RGBA image from the BytesIO-backed source object.
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(image_bytes)) as source_image:
                    source_image.load()
                    return source_image.convert("RGBA")
        except AppError:
            raise
        except (
            UnidentifiedImageError,
            OSError,
            SyntaxError,
            ValueError,
            Image.DecompressionBombWarning,
            Image.DecompressionBombError,
        ) as exc:
            raise AppError(
                code="INVALID_IMAGE_CONTENT",
                message="上传文件不是有效的图片。",
                status_code=400,
                details={"index": index, "filename": original_name},
            ) from exc

    @staticmethod
    def _verify_saved_image(path: Path) -> None:
        try:
            with Image.open(path) as image:
                image.verify()
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            raise AppError(
                code="INTERNAL_ERROR",
                message="图片文件保存失败。",
                status_code=500,
            ) from exc

    def _data_path(self, *parts: str) -> Path:
        candidate = self.data_root.joinpath(*parts).resolve()
        if not candidate.is_relative_to(self.data_root):
            raise AppError(
                code="INTERNAL_ERROR",
                message="检测到不安全的文件路径。",
                status_code=500,
            )
        return candidate

    def _child_path(self, parent: Path, filename: str) -> Path:
        candidate = parent.joinpath(filename).resolve()
        if not candidate.is_relative_to(self.data_root):
            raise AppError(
                code="INTERNAL_ERROR",
                message="检测到不安全的文件路径。",
                status_code=500,
            )
        return candidate
