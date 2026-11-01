"""Application settings, read from environment variables or a `.env` file.

Copy `backend/.env.example` to `backend/.env` and edit the values there.
Never commit the real `.env` file.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The backend/ folder. Used so the default SQLite file always lands in
# backend/slope_monitor.db, no matter which folder you start the server from.
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Secret used to sign login tokens (JWT). MUST be changed for anything
    # other than local development.
    SECRET_KEY: str = "dev-only-insecure-secret-key-change-me-in-env-file"

    # SQLAlchemy connection string. Switching to PostgreSQL later is a
    # one-line change here, e.g. "postgresql+psycopg://user:pw@host/db".
    DATABASE_URL: str = f"sqlite:///{(BACKEND_DIR / 'slope_monitor.db').as_posix()}"

    # Comma-separated list of browser origins allowed to call the API.
    CORS_ORIGINS: str = "http://localhost:5173"

    # How long a login token stays valid, in minutes.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # How often the background task checks for offline nodes, in seconds.
    OFFLINE_CHECK_INTERVAL_S: int = 30

    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
