"""Split an edited composite canvas back into independent PNG assets."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.config import Settings
from app.exceptions.errors import AppError, ErrorCode
from app.models.job import OutputItem
from app.models.manifest import CanvasItemManifest, CanvasManifest
from app.services.alpha_service import AlphaService


class CanvasSplitter:
    """Map manifest coordinates onto provider output and restore each asset."""

    def __init__(
        self,
        settings: Settings,
        alpha_service: AlphaService | None = None,
    ) -> None:
        self.settings = settings
        self.data_root = Path(settings.DATA_DIR).resolve()
        self.alpha_service = alpha_service or AlphaService()

    def split(
        self,
        edited_canvas_path: Path,
        manifest: CanvasManifest,
        output_directory: Path,
    ) -> list[OutputItem]:
        safe_output_directory = Path(output_directory).resolve()
        if not safe_output_directory.is_relative_to(self.data_root):
            raise AppError(ErrorCode.INTERNAL_ERROR)
        safe_output_directory.mkdir(parents=True, exist_ok=True)

        try:
            with Image.open(edited_canvas_path) as source:
                source.load()
                edited_canvas = source.convert("RGBA")
        except (OSError, UnidentifiedImageError, SyntaxError, ValueError) as exc:
            raise AppError(ErrorCode.INVALID_PROVIDER_RESPONSE) from exc

        try:
            output_width, output_height = edited_canvas.size
            self._validate_aspect_ratio(
                input_size=(manifest.canvas_width, manifest.canvas_height),
                output_size=(output_width, output_height),
            )
            scale_x = output_width / manifest.canvas_width
            scale_y = output_height / manifest.canvas_height

            outputs: list[OutputItem] = []
            for item in sorted(manifest.items, key=lambda value: value.index):
                outputs.append(
                    self._split_item(
                        edited_canvas=edited_canvas,
                        item=item,
                        scale_x=scale_x,
                        scale_y=scale_y,
                        output_directory=safe_output_directory,
                        job_id=manifest.job_id,
                    )
                )
            return outputs
        finally:
            edited_canvas.close()

    def _split_item(
        self,
        *,
        edited_canvas: Image.Image,
        item: CanvasItemManifest,
        scale_x: float,
        scale_y: float,
        output_directory: Path,
        job_id: str,
    ) -> OutputItem:
        slot_box = self._scaled_box(
            x=item.slot_x,
            y=item.slot_y,
            width=item.slot_width,
            height=item.slot_height,
            scale_x=scale_x,
            scale_y=scale_y,
            bounds=edited_canvas.size,
        )
        self._require_nonempty_box(slot_box)
        slot = edited_canvas.crop(slot_box)
        try:
            content_box = self._scaled_box(
                x=item.content_x_in_slot,
                y=item.content_y_in_slot,
                width=item.content_width,
                height=item.content_height,
                scale_x=scale_x,
                scale_y=scale_y,
                bounds=slot.size,
            )
            self._require_nonempty_box(content_box)
            content = slot.crop(content_box)
        finally:
            slot.close()

        try:
            resampling = getattr(Image, "Resampling", Image)
            method = resampling.NEAREST if item.is_pixel_art else resampling.LANCZOS
            resized = content.resize(
                (item.original_width, item.original_height),
                resample=method,
            )
        finally:
            content.close()

        try:
            alpha_path = self._resolve_data_path(item.original_alpha_path)
            restored = self.alpha_service.restore_original_alpha(
                edited_image=resized,
                alpha_path=alpha_path,
                original_size=(item.original_width, item.original_height),
            )
        finally:
            resized.close()

        output_name = f"item_{item.index}.png"
        output_path = output_directory.joinpath(output_name).resolve()
        if not output_path.is_relative_to(self.data_root):
            restored.close()
            raise AppError(ErrorCode.INTERNAL_ERROR)
        try:
            restored.save(output_path, format="PNG")
        finally:
            restored.close()
        self._verify_rgba_png(output_path)

        return OutputItem(
            index=item.index,
            original_name=item.original_name,
            result_url=f"/files/outputs/{job_id}/{output_name}",
        )

    @staticmethod
    def _validate_aspect_ratio(
        *,
        input_size: tuple[int, int],
        output_size: tuple[int, int],
    ) -> None:
        input_width, input_height = input_size
        output_width, output_height = output_size
        if min(input_width, input_height, output_width, output_height) <= 0:
            raise AppError(ErrorCode.INVALID_PROVIDER_RESPONSE)
        input_ratio = input_width / input_height
        output_ratio = output_width / output_height
        relative_difference = abs(output_ratio - input_ratio) / input_ratio
        if relative_difference > 0.02:
            raise AppError(ErrorCode.OUTPUT_ASPECT_RATIO_MISMATCH)

    @staticmethod
    def _scaled_box(
        *,
        x: int,
        y: int,
        width: int,
        height: int,
        scale_x: float,
        scale_y: float,
        bounds: tuple[int, int],
    ) -> tuple[int, int, int, int]:
        bound_width, bound_height = bounds
        left = max(0, min(bound_width, int(round(x * scale_x))))
        top = max(0, min(bound_height, int(round(y * scale_y))))
        right = max(
            left,
            min(bound_width, int(round((x + width) * scale_x))),
        )
        bottom = max(
            top,
            min(bound_height, int(round((y + height) * scale_y))),
        )
        return left, top, right, bottom

    @staticmethod
    def _require_nonempty_box(box: tuple[int, int, int, int]) -> None:
        left, top, right, bottom = box
        if right <= left or bottom <= top:
            raise AppError(ErrorCode.INVALID_PROVIDER_RESPONSE)

    def _resolve_data_path(self, recorded_path: str) -> Path:
        value = Path(recorded_path)
        if value.is_absolute():
            candidate = value.resolve()
        else:
            parts = value.parts
            # Also accept manifests that explicitly prefix paths with the data
            # directory name (for example ``data/uploads/...``).
            if parts and parts[0].lower() == self.data_root.name.lower():
                value = Path(*parts[1:])
            candidate = self.data_root.joinpath(value).resolve()
        if not candidate.is_relative_to(self.data_root):
            raise AppError(ErrorCode.INTERNAL_ERROR)
        return candidate

    @staticmethod
    def _verify_rgba_png(path: Path) -> None:
        try:
            with Image.open(path) as image:
                if image.format != "PNG" or image.mode != "RGBA":
                    raise ValueError("expected an RGBA PNG")
                image.verify()
        except (OSError, UnidentifiedImageError, SyntaxError, ValueError) as exc:
            raise AppError(ErrorCode.INTERNAL_ERROR) from exc
