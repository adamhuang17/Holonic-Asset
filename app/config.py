"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings with a deliberately empty API-token default."""

    QNAIGC_API_TOKEN: str = ""
    QNAIGC_API_HOST: str = "api.qnaigc.com"
    QNAIGC_API_PATH: str = "/v1/images/edits"
    IMAGE_MODEL: str = "openai/gpt-image-2"
    IMAGE_QUALITY: str = "high"

    MIN_FILES: int = 2
    MAX_FILES: int = 6
    MAX_FILE_SIZE_MB: int = 10

    SLOT_SIZE: int = 512
    GUTTER: int = 64
    MARGIN: int = 64

    REQUEST_TIMEOUT_SECONDS: int = 300
    DATA_DIR: Path = Path("data")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def qnaigc_api_url(self) -> str:
        host = self.QNAIGC_API_HOST.strip().rstrip("/")
        if not host.startswith(("http://", "https://")):
            host = f"https://{host}"
        path = self.QNAIGC_API_PATH.strip()
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{host}{path}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

