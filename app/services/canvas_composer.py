"""Compose independently uploaded game assets onto one regular canvas."""

from __future__ import annotations

import math
from pathlib import Path
from PIL import Image, UnidentifiedImageError

from app.config import Settings
from app.exceptions.errors import AppError, ErrorCode, error_for
from app.models.manifest import CanvasItemManifest, CanvasManifest


_CANVAS_BACKGROUND = (240, 240, 240, 255)
_MAX_CONTENT_EDGE = 420


class CanvasComposer:
    """Build the provider input canvas and its reversible placement manifest."""

    def __init__(
        self,
        settings: Settings | None = None,
        data_dir: Path | None = None,
    ) -> None:
        self.settings = settings or Settings()
        configured_root = (
            data_dir if data_dir is not None else self.settings.DATA_DIR
        )
        self.data_root = Path(configured_root).resolve()

    def compose(
        self,
        job_id: str,
        image_paths: list[Path],
        original_names: list[str],
    ) -> tuple[Path, CanvasManifest]:
        """Compose ``image_paths`` and persist the canvas plus source alpha masks."""

        item_count = len(image_paths)
        if item_count != len(original_names):
            raise error_for(ErrorCode.INTERNAL_ERROR)
        if item_count < self.settings.MIN_FILES:
            raise error_for(ErrorCode.TOO_FEW_FILES)
        if item_count > self.settings.MAX_FILES:
            raise error_for(ErrorCode.TOO_MANY_FILES)

        cols = max(2, math.ceil(math.sqrt(item_count)))
        rows = max(2, math.ceil(item_count / cols))
        slot_size = int(self.settings.SLOT_SIZE)
        gutter = int(self.settings.GUTTER)
        margin = int(self.settings.MARGIN)
        canvas_width = margin * 2 + slot_size * cols + gutter * (cols - 1)
        canvas_height = margin * 2 + slot_size * rows + gutter * (rows - 1)

        composite_directory = self._data_path("composite", job_id)
        uploads_directory = self._data_path("uploads", job_id)
        composite_directory.mkdir(parents=True, exist_ok=True)
        uploads_directory.mkdir(parents=True, exist_ok=True)
        composite_path = self._child_path(composite_directory, "composite.png")

        canvas = Image.new(
            "RGBA",
            (canvas_width, canvas_height),
            _CANVAS_BACKGROUND,
        )
        manifest_items: list[CanvasItemManifest] = []

        try:
            for index, (image_path, original_name) in enumerate(
                zip(image_paths, original_names, strict=True)
            ):
                item = self._place_item(
                    canvas=canvas,
                    index=index,
                    image_path=Path(image_path),
                    original_name=original_name,
                    uploads_directory=uploads_directory,
                    slot_size=slot_size,
                    gutter=gutter,
                    margin=margin,
                    cols=cols,
                )
                manifest_items.append(item)

            canvas.save(composite_path, format="PNG")
        except AppError:
            raise
        except (OSError, UnidentifiedImageError, SyntaxError, ValueError) as exc:
            raise AppError(
                ErrorCode.INVALID_IMAGE_CONTENT,
                details={"stage": "canvas_composition"},
            ) from exc
        finally:
            canvas.close()

        self._verify_image(composite_path)
        manifest = CanvasManifest(
            job_id=job_id,
            rows=rows,
            cols=cols,
            slot_size=slot_size,
            gutter=gutter,
            margin=margin,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            items=manifest_items,
        )
        return composite_path, manifest

    def _place_item(
        self,
        *,
        canvas: Image.Image,
        index: int,
        image_path: Path,
        original_name: str,
        uploads_directory: Path,
        slot_size: int,
        gutter: int,
        margin: int,
        cols: int,
    ) -> CanvasItemManifest:
        with Image.open(image_path) as source:
            source.load()
            original_width, original_height = source.size
            if original_width <= 0 or original_height <= 0:
                raise AppError(ErrorCode.INVALID_IMAGE_CONTENT)

            is_pixel_art = self._is_pixel_art(source)
            rgba = source.convert("RGBA")

        try:
            alpha_path = self._child_path(uploads_directory, f"{index}_alpha.png")
            alpha = rgba.getchannel("A")
            try:
                alpha.save(alpha_path, format="PNG")
            finally:
                alpha.close()
            self._verify_image(alpha_path)

            content_width, content_height = self._scaled_size(
                original_width,
                original_height,
                min(_MAX_CONTENT_EDGE, slot_size),
            )
            resampling = self._resampling(is_pixel_art)
            resized = rgba.resize(
                (content_width, content_height),
                resample=resampling,
            )
            try:
                row, col = divmod(index, cols)
                slot_x = margin + col * (slot_size + gutter)
                slot_y = margin + row * (slot_size + gutter)
                content_x = (slot_size - content_width) // 2
                content_y = (slot_size - content_height) // 2
                canvas.alpha_composite(
                    resized,
                    dest=(slot_x + content_x, slot_y + content_y),
                )
            finally:
                resized.close()
        finally:
            rgba.close()

        return CanvasItemManifest(
            index=index,
            original_name=original_name,
            stored_name=image_path.name,
            original_width=original_width,
            original_height=original_height,
            slot_x=slot_x,
            slot_y=slot_y,
            slot_width=slot_size,
            slot_height=slot_size,
            content_x_in_slot=content_x,
            content_y_in_slot=content_y,
            content_width=content_width,
            content_height=content_height,
            original_alpha_path=alpha_path.relative_to(self.data_root).as_posix(),
            is_pixel_art=is_pixel_art,
        )

    @staticmethod
    def _scaled_size(width: int, height: int, maximum_edge: int) -> tuple[int, int]:
        """Scale both up and down so the longest edge is ``maximum_edge``."""

        scale = maximum_edge / max(width, height)
        return (
            max(1, min(maximum_edge, int(round(width * scale)))),
            max(1, min(maximum_edge, int(round(height * scale)))),
        )

    @staticmethod
    def _is_pixel_art(image: Image.Image) -> bool:
        """Conservatively infer pixel art from palette and source resolution.

        Uploads are normalized before reaching this service, so file metadata is
        not a dependable discriminator. Palette images and small, low-colour
        assets are the practical signals available without user-supplied type
        metadata.
        """

        if image.mode in {"1", "P"}:
            return True
        width, height = image.size
        if max(width, height) > 256:
            return False
        # ``getcolors`` returns None as soon as the cap is exceeded and avoids
        # constructing an unbounded colour histogram for adversarial inputs.
        converted = image.convert("RGBA")
        try:
            return converted.getcolors(maxcolors=256) is not None
        finally:
            converted.close()

    @staticmethod
    def _resampling(is_pixel_art: bool) -> int:
        resampling = getattr(Image, "Resampling", Image)
        return resampling.NEAREST if is_pixel_art else resampling.LANCZOS

    @staticmethod
    def _verify_image(path: Path) -> None:
        try:
            with Image.open(path) as image:
                image.verify()
        except (OSError, UnidentifiedImageError, SyntaxError, ValueError) as exc:
            raise AppError(ErrorCode.INTERNAL_ERROR) from exc

    def _data_path(self, *parts: str) -> Path:
        candidate = self.data_root.joinpath(*parts).resolve()
        if not candidate.is_relative_to(self.data_root):
            raise AppError(ErrorCode.INTERNAL_ERROR)
        return candidate

    def _child_path(self, parent: Path, filename: str) -> Path:
        candidate = parent.joinpath(filename).resolve()
        if not candidate.is_relative_to(self.data_root):
            raise AppError(ErrorCode.INTERNAL_ERROR)
        return candidate
