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
    gemini_api_key: str = Field(default="", description="Chave da API Gemini (AI Studio)")
    gemini_backend: str = Field(default="aistudio", description="Backend: 'aistudio' ou 'vertex'")
    gcp_project_id: str = Field(default="", description="ID do projeto GCP (necessario para Vertex AI)")
    gcp_location: str = Field(default="us-central1", description="Regiao GCP para Vertex AI")
    gcs_bucket: str = Field(default="", description="Bucket GCS para Batch API (ex: leilao-inteligente-batch)")

    # Processamento
    frame_interval_seconds: int = Field(default=5, ge=1, le=60)
    change_threshold: float = Field(default=0.03, ge=0.01, le=0.5)
    overlay_region_top_percent: int = Field(default=62, ge=50, le=90)

    # Banco de dados
    database_url: str = Field(default=f"sqlite:///{DATA_DIR / 'leilao.db'}")

    # Supabase
    supabase_url: str = Field(default="", description="URL do projeto Supabase")
    supabase_service_role_key: str = Field(default="", description="Service role key do Supabase")

    # YouTube
    yt_dlp_cookies_file: str | None = Field(default=None)
    video_proxy_url: str | None = Field(default=None, description="URL do video-proxy local (ex: https://xxx.trycloudflare.com)")

    @property
    def cookies_path(self) -> str | None:
        """Retorna path do cookies. Sempre carrega do banco (fonte de verdade)."""
        import os
        # 1. Configurado via env var (override manual)
        if self.yt_dlp_cookies_file and os.path.exists(self.yt_dlp_cookies_file):
            return self.yt_dlp_cookies_file
        # 2. Carregar do banco (fonte de verdade — sempre atualizado)
        try:
            path = _carregar_cookies_do_banco()
            if path:
                return path
        except Exception:
            pass
        # 3. Fallback: arquivo local existente
        for p in ["/app/cookies.txt", str(DATA_DIR / "cookies.txt")]:
            if os.path.exists(p):
                return p
        return None


def _carregar_cookies_do_banco() -> str | None:
    """Carrega cookies do banco Supabase e salva em arquivo local."""
    import os
    from leilao_inteligente.storage.db import get_session, init_db
    init_db()
    session = get_session()
    try:
        from sqlalchemy import text
        result = session.execute(text("SELECT valor FROM configuracoes WHERE chave = 'youtube_cookies'")).fetchone()
        if result and result[0]:
            path = "/app/cookies.txt" if os.path.exists("/app") else str(DATA_DIR / "cookies.txt")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(result[0])
            return path
    finally:
        session.close()
    return None


def get_settings() -> Settings:
    """Retorna instancia de Settings (cached)."""
    return Settings()  # type: ignore[call-arg]
