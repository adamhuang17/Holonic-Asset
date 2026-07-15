"""Models persisted for completed and failed editing jobs."""

from pathlib import Path
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict


class OutputItem(BaseModel):
    index: int
    original_name: str
    result_url: str

    model_config = ConfigDict(extra="forbid")


class JobArtifacts(BaseModel):
    composite_url: str
    edited_canvas_url: str
    manifest_url: str

    model_config = ConfigDict(extra="forbid")


class JobResponse(BaseModel):
    job_id: str
    status: Literal["completed"] = "completed"
    instruction: str
    total: int
    outputs: list[OutputItem]
    artifacts: JobArtifacts

    model_config = ConfigDict(extra="forbid")


class JobError(BaseModel):
    code: str
    message: str
    details: Any | None = None

    model_config = ConfigDict(extra="forbid")


class FailedJobRecord(BaseModel):
    """The minimal durable representation written when any job stage fails."""

    job_id: str
    status: Literal["failed"] = "failed"
    error: JobError
    instruction: str | None = None

    model_config = ConfigDict(extra="forbid")


JobRecord: TypeAlias = JobResponse | FailedJobRecord


class ProviderResult(BaseModel):
    """Validated image artifact returned by the external provider adapter."""

    output_path: Path
    width: int
    height: int

    model_config = ConfigDict(extra="forbid")
