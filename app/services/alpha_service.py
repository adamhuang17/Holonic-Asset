"""Restore stable transparent silhouettes after model editing."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


class AlphaService:
    """Apply the source image's alpha channel to an edited image."""

    def restore_original_alpha(
        self,
        edited_image: Image.Image,
        alpha_path: Path,
        original_size: tuple[int, int],
    ) -> Image.Image:
        width, height = original_size
        if width <= 0 or height <= 0:
            raise ValueError("original_size must contain positive dimensions")

        resampling = getattr(Image, "Resampling", Image)
        restored = edited_image.convert("RGBA")
        if restored.size != original_size:
            resized = restored.resize(original_size, resample=resampling.LANCZOS)
            restored.close()
            restored = resized

        with Image.open(alpha_path) as alpha_source:
            alpha_source.load()
            original_alpha = alpha_source.convert("L")
        try:
            if original_alpha.size != original_size:
                resized_alpha = original_alpha.resize(
                    original_size,
                    resample=resampling.LANCZOS,
                )
                original_alpha.close()
                original_alpha = resized_alpha
            restored.putalpha(original_alpha)
        finally:
            original_alpha.close()
        return restored
