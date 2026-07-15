"""Models describing how source images are placed on a composite canvas."""

from pydantic import BaseModel, ConfigDict


class CanvasItemManifest(BaseModel):
    index: int
    original_name: str
    stored_name: str

    original_width: int
    original_height: int

    slot_x: int
    slot_y: int
    slot_width: int
    slot_height: int

    content_x_in_slot: int
    content_y_in_slot: int
    content_width: int
    content_height: int

    original_alpha_path: str
    is_pixel_art: bool = False

    model_config = ConfigDict(extra="forbid")


class CanvasManifest(BaseModel):
    job_id: str

    rows: int
    cols: int

    slot_size: int
    gutter: int
    margin: int

    canvas_width: int
    canvas_height: int

    items: list[CanvasItemManifest]

    model_config = ConfigDict(extra="forbid")
