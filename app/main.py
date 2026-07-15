"""FastAPI application factory and default application instance."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes.jobs import router as jobs_router
from app.config import Settings, get_settings
from app.exceptions.handlers import register_exception_handlers
from app.services.job_service import JobService
from app.services.qnaigc_provider import QnAIGCImageEditProvider
from app.services.semantic_plan_service import (
    DeepSeekSemanticPlanner,
    SemanticPlanner,
)


def _create_data_directories(data_dir: Path) -> None:
    for name in ("uploads", "composite", "edited", "outputs", "jobs"):
        (data_dir / name).mkdir(parents=True, exist_ok=True)


def create_app(
    settings: Settings | None = None,
    provider: QnAIGCImageEditProvider | None = None,
    semantic_planner: SemanticPlanner | None = None,
) -> FastAPI:
    """Build an application; injectable arguments keep tests fully offline."""

    app_settings = settings or get_settings()
    data_dir = Path(app_settings.DATA_DIR)
    _create_data_directories(data_dir)

    application = FastAPI(
        title="Batch Image Edit API",
        version="1.0.0",
    )
    register_exception_handlers(application)

    image_provider = provider or QnAIGCImageEditProvider(app_settings)
    planner = semantic_planner or DeepSeekSemanticPlanner(app_settings)
    application.state.settings = app_settings
    application.state.job_service = JobService(
        settings=app_settings,
        provider=image_provider,
        semantic_planner=planner,
    )

    @application.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    application.include_router(jobs_router)
    application.mount(
        "/files",
        StaticFiles(directory=str(data_dir)),
        name="files",
    )
    return application


app = create_app()
