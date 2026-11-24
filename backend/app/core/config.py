import os
from functools import lru_cache
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

backend_dir = Path(__file__).resolve().parent.parent.parent
env_file_path = backend_dir / ".env"
if env_file_path.exists():
    load_dotenv(dotenv_path=env_file_path)
else:
    load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(env_file_path) if env_file_path.exists() else ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "DevPilot"
    app_env: str = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    database_url: str = "sqlite+aiosqlite:///./devpilot.db"
    checkpoint_db_path: str = "./devpilot_checkpoints.db"
    default_llm_provider: str = "mock"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096
    llm_max_retries: int = 3
    log_level: str = "INFO"
    workspace_base_path: str = "./workspace"
    docker_sandbox_enabled: bool = False

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
