"""Configuracao do sistema via environment variables."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
VIDEOS_DIR = DATA_DIR / "videos"
FRAMES_DIR = DATA_DIR / "frames"


class Settings(BaseSettings):
    """Configuracoes do Leilao Inteligente."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Gemini API
    gemini_api_key: str = Field(description="Chave da API Gemini")

    # Processamento
    frame_interval_seconds: int = Field(default=5, ge=1, le=60)
    change_threshold: float = Field(default=0.03, ge=0.01, le=0.5)
    overlay_region_top_percent: int = Field(default=70, ge=50, le=90)

    # Banco de dados
    database_url: str = Field(default=f"sqlite:///{DATA_DIR / 'leilao.db'}")

    # YouTube
    yt_dlp_cookies_file: str | None = Field(default=None)


def get_settings() -> Settings:
    """Retorna instancia de Settings (cached)."""
    return Settings()  # type: ignore[call-arg]
