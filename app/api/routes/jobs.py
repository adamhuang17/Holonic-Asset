"""Job API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status

from app.models.job import JobResponse
from app.services.job_service import JobService


router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def get_job_service(request: Request) -> JobService:
    """Return the application-scoped job service."""

    return request.app.state.job_service


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    files: Annotated[list[UploadFile], File()],
    instruction: Annotated[str, Form()],
    image_mapping: Annotated[str, Form()],
    service: JobService = Depends(get_job_service),
) -> JobResponse:
    """Synchronously create and execute one composite image editing job."""

    return await service.create_and_execute_job(
        files,
        instruction,
        image_mapping,
    )


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    service: JobService = Depends(get_job_service),
) -> dict:
    """Read a previously persisted job record."""

    return service.get_job(job_id)
