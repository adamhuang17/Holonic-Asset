"""Structured editing intent produced by the semantic model."""

from pydantic import BaseModel, ConfigDict, Field


class ItemEdit(BaseModel):
    """One image reference and the edit that applies only to that image."""

    image: str = Field(min_length=1, pattern=r"^image[1-9][0-9]*$")
    edit: str

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EditPlan(BaseModel):
    """Shared visual intent plus one optional edit for every input image."""

    shared_style: str
    shared_edit: str
    items: list[ItemEdit] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
