"""Orchestration and durable job state for the synchronous edit workflow."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from fastapi import UploadFile
from pydantic import ValidationError

from app.config import Settings
from app.exceptions.errors import AppError, ErrorCode, error_for
from app.models.job import FailedJobRecord, JobArtifacts, JobError, JobResponse
from app.services.canvas_composer import CanvasComposer
from app.services.canvas_splitter import CanvasSplitter
from app.services.file_service import FileService
from app.services.prompt_service import PromptService


logger = logging.getLogger(__name__)
_JOB_ID_PATTERN = re.compile(r"^job_[0-9a-f]{32}$")


class ImageEditProvider(Protocol):
    async def edit(self, composite_path: Path, prompt: str, output_path: Path):
        """Edit one composite image and persist the decoded result."""


class JobService:
    """Execute all stages of a job inside one HTTP request."""

    def __init__(
        self,
        settings: Settings,
        provider: ImageEditProvider,
        *,
        file_service: FileService | None = None,
        composer: CanvasComposer | None = None,
        prompt_service: PromptService | None = None,
        splitter: CanvasSplitter | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.data_root = Path(settings.DATA_DIR).resolve()
        self.file_service = file_service or FileService(settings)
        self.composer = composer or CanvasComposer(settings)
        self.prompt_service = prompt_service or PromptService()
        self.splitter = splitter or CanvasSplitter(settings)

    async def create_and_execute_job(
        self,
        files: list[UploadFile],
        instruction: str,
    ) -> JobResponse:
        job_id = f"job_{uuid4().hex}"
        directories = self._create_job_directories(job_id)
        clean_instruction = instruction.strip()

        try:
            self._validate_request(files, clean_instruction)
            uploads = await self.file_service.save_uploads(job_id, files)

            composite_path, manifest = self.composer.compose(
                job_id=job_id,
                image_paths=[item.path for item in uploads],
                original_names=[item.original_name for item in uploads],
            )

            manifest_path = directories["jobs"] / "manifest.json"
            self._write_json(
                manifest_path,
                manifest.model_dump(mode="json"),
            )

            prompt = self.prompt_service.build(clean_instruction, len(uploads))
            edited_canvas_path = directories["edited"] / "edited_canvas.png"
            await self.provider.edit(
                composite_path=composite_path,
                prompt=prompt,
                output_path=edited_canvas_path,
            )

            outputs = self.splitter.split(
                edited_canvas_path=edited_canvas_path,
                manifest=manifest,
                output_directory=directories["outputs"],
            )
            if len(outputs) != len(uploads):
                raise error_for(ErrorCode.INTERNAL_ERROR)

            response = JobResponse(
                job_id=job_id,
                instruction=clean_instruction,
                total=len(outputs),
                outputs=outputs,
                artifacts=JobArtifacts(
                    composite_url=f"/files/composite/{job_id}/composite.png",
                    edited_canvas_url=(
                        f"/files/edited/{job_id}/edited_canvas.png"
                    ),
                    manifest_url=f"/files/jobs/{job_id}/manifest.json",
                ),
            )
            self._write_json(
                directories["jobs"] / "job.json",
                response.model_dump(mode="json"),
            )
            return response
        except AppError as exc:
            self._persist_failed_job(
                job_id=job_id,
                jobs_directory=directories["jobs"],
                instruction=clean_instruction or None,
                error=exc,
            )
            raise
        except Exception as exc:
            # Exception values from HTTP clients can contain request bodies or
            # headers, so only log the type here.
            logger.exception(
                "job_failed job_id=%s exception_type=%s",
                job_id,
                type(exc).__name__,
                exc_info=False,
            )
            public_error = error_for(ErrorCode.INTERNAL_ERROR)
            self._persist_failed_job(
                job_id=job_id,
                jobs_directory=directories["jobs"],
                instruction=clean_instruction or None,
                error=public_error,
            )
            raise public_error from exc

    def get_job(self, job_id: str) -> dict:
        """Load a completed or failed job without exposing local paths."""

        if not _JOB_ID_PATTERN.fullmatch(job_id):
            raise error_for(ErrorCode.JOB_NOT_FOUND)
        job_path = self._data_path("jobs", job_id, "job.json")
        if not job_path.is_file():
            raise error_for(ErrorCode.JOB_NOT_FOUND)
        try:
            value = json.loads(job_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise error_for(ErrorCode.INTERNAL_ERROR) from exc
        if not isinstance(value, dict):
            raise error_for(ErrorCode.INTERNAL_ERROR)
        try:
            if value.get("status") == "completed":
                record = JobResponse.model_validate(value)
            elif value.get("status") == "failed":
                record = FailedJobRecord.model_validate(value)
            else:
                raise error_for(ErrorCode.INTERNAL_ERROR)
        except ValidationError as exc:
            raise error_for(ErrorCode.INTERNAL_ERROR) from exc
        return value

    def _validate_request(
        self,
        files: list[UploadFile],
        clean_instruction: str,
    ) -> None:
        count = len(files)
        if count == 0:
            raise error_for(ErrorCode.NO_FILES)
        if count < self.settings.MIN_FILES:
            raise error_for(ErrorCode.TOO_FEW_FILES)
        if count > self.settings.MAX_FILES:
            raise error_for(ErrorCode.TOO_MANY_FILES)
        if not clean_instruction:
            raise error_for(ErrorCode.EMPTY_INSTRUCTION)

    def _create_job_directories(self, job_id: str) -> dict[str, Path]:
        directories = {
            category: self._data_path(category, job_id)
            for category in ("uploads", "composite", "edited", "outputs", "jobs")
        }
        for path in directories.values():
            path.mkdir(parents=True, exist_ok=True)
        return directories

    def _persist_failed_job(
        self,
        *,
        job_id: str,
        jobs_directory: Path,
        instruction: str | None,
        error: AppError,
    ) -> None:
        record: dict = {
            "job_id": job_id,
            "status": "failed",
            "error": JobError(
                code=error.code,
                message=error.message,
                details=error.details,
            ).model_dump(mode="json"),
        }
        if instruction is not None:
            record["instruction"] = instruction
        try:
            self._write_json(jobs_directory / "job.json", record)
        except Exception:
            logger.error(
                "failed_job_record_write_failed job_id=%s",
                job_id,
            )

    def _write_json(self, path: Path, value: dict) -> None:
        safe_path = path.resolve()
        if not safe_path.is_relative_to(self.data_root):
            raise error_for(ErrorCode.INTERNAL_ERROR)
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _data_path(self, *parts: str) -> Path:
        candidate = self.data_root.joinpath(*parts).resolve()
        if not candidate.is_relative_to(self.data_root):
            raise error_for(ErrorCode.INTERNAL_ERROR)
        return candidate
