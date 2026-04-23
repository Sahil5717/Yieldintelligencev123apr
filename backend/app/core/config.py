"""Application configuration.

All settings come from environment variables with sensible defaults for local dev.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Paths
    app_dir: Path = Path(__file__).parent.parent
    seed_dir: Path = Path(__file__).parent.parent / "data" / "seed"
    artifacts_dir: Path = Path(__file__).parent.parent / "data" / "artifacts"

    # Database — SQLite by default, Postgres via env var on Railway
    # Use absolute path so scripts work from any cwd
    database_url: str = f"sqlite:///{Path(__file__).parent.parent.parent / 'yield_intelligence.db'}"

    # App behaviour
    environment: str = "local"  # local | staging | production
    seed_on_startup: bool = True  # load Acme + catalog + global signals on first boot

    # CORS — React dev server by default; override on Railway
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

    # MMM
    mmm_use_pretrained: bool = True  # serve from saved posterior; don't fit on request
    mmm_draws: int = 1000
    mmm_tune: int = 1000
    mmm_chains: int = 2

    # Workspace — hardcoded for single-tenant v1
    default_workspace: str = "acme_retail"
    default_dataset: str = "5yr"  # 1yr | 5yr


settings = Settings()
settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
