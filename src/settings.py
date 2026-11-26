"""Application-level environment settings loaded from `.env`."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Global runtime settings for Newstent Core Engine & FastAPI Backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Primary Cloud AI: DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_primary_model: str = "deepseek-chat"
    deepseek_pro_model: str = "deepseek-reasoner"

    # Secondary Fallback: Qwen via OpenRouter
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "qwen/qwen-2.5-72b-instruct"

    # Fast Fallback: Llama 3.3 70B via Groq
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"

    # Optional Backup: Google Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # AI Engine Tuning
    ai_provider_order: str = "deepseek,openrouter,groq,gemini"
    ai_batch_size: int = 30
    ai_max_concurrency: int = 5
    ai_max_retries: int = 2

    # Local Paths
    sqlite_db_path: Path = Path("data/newstent_state.db")
    data_dir: Path = Path("data")
    clients_dir: Path = Path("clients")

    # Local Web Server
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    next_public_api_url: str = "http://127.0.0.1:8000"

    def get_provider_order(self) -> list[str]:
        """Return validated, deduplicated fallback order for the 4 Cloud AI providers."""
        allowed = ("deepseek", "openrouter", "groq", "gemini")
        parsed: list[str] = []
        for raw in (self.ai_provider_order or "").split(","):
            pid = raw.strip().lower()
            if pid in allowed and pid not in parsed:
                parsed.append(pid)
        for pid in allowed:
            if pid not in parsed:
                parsed.append(pid)
        return parsed


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return cached application settings instance."""
    return AppSettings()
