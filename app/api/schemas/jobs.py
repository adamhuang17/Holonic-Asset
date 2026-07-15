"""Schemas exposed by the jobs API."""

from typing import Any, TypeAlias

from pydantic import BaseModel, ConfigDict

from app.models.job import (
    FailedJobRecord,
    JobArtifacts,
    JobResponse,
    OutputItem,
)


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any | None = None

    model_config = ConfigDict(extra="forbid")


class ErrorResponse(BaseModel):
    error: ErrorBody

    model_config = ConfigDict(extra="forbid")


JobLookupResponse: TypeAlias = JobResponse | FailedJobRecord

__all__ = [
    "ErrorBody",
    "ErrorResponse",
    "FailedJobRecord",
    "JobArtifacts",
    "JobLookupResponse",
    "JobResponse",
    "OutputItem",
]
