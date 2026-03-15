"""
Central configuration module.
All settings come from environment variables (loaded via python-dotenv).
Import `settings` anywhere in the project instead of calling os.environ directly.
"""

import os
from functools import lru_cache
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── LLM ──────────────────────────────────────────────────────────────
    openrouter_api_key: Optional[str] = Field(None, env="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        "https://openrouter.ai/api/v1", env="OPENROUTER_BASE_URL"
    )
    llm_model: str = Field("anthropic/claude-3.5-sonnet", env="LLM_MODEL")
    llm_temperature: float = Field(0.2, env="LLM_TEMPERATURE")
    gemini_api_key: Optional[str] = Field(None, env="GEMINI_API_KEY")

    # ── GitHub ────────────────────────────────────────────────────────────
    github_token: str = Field(..., env="GITHUB_TOKEN")
    github_username: str = Field(..., env="GITHUB_USERNAME")

    # ── Agent behaviour ───────────────────────────────────────────────────
    issue_labels: str = Field("good first issue,help wanted", env="ISSUE_LABELS")
    language_filter: str = Field("python,javascript", env="LANGUAGE_FILTER")
    max_issues_to_scan: int = Field(5, env="MAX_ISSUES_TO_SCAN")
    max_feedback_iterations: int = Field(3, env="MAX_FEEDBACK_ITERATIONS")
    target_domains: str = Field("", env="TARGET_DOMAINS")
    auto_approve_timeout_sec: int = Field(120, env="AUTO_APPROVE_TIMEOUT_SEC")
    
    # ── Email Notifications ───────────────────────────────────────────────
    smtp_user: Optional[str] = Field(None, env="SMTP_USER")
    smtp_pass: Optional[str] = Field(None, env="SMTP_PASS")
    notification_email: Optional[str] = Field(None, env="NOTIFICATION_EMAIL")

    # ── Docker sandbox ────────────────────────────────────────────────────
    docker_image: str = Field("python:3.11-slim", env="DOCKER_IMAGE")
    docker_timeout_seconds: int = Field(120, env="DOCKER_TIMEOUT_SECONDS")
    sandbox_memory_limit: str = Field("512m", env="SANDBOX_MEMORY_LIMIT")

    # ── Web UI ────────────────────────────────────────────────────────────
    web_host: str = Field("0.0.0.0", env="WEB_HOST")
    web_port: int = Field(8000, env="WEB_PORT")
    web_secret_key: str = Field("change-me-in-production", env="WEB_SECRET_KEY")

    # ── Scheduler ────────────────────────────────────────────────────────
    schedule_interval_hours: int = Field(6, env="SCHEDULE_INTERVAL_HOURS")
    auto_run: bool = Field(False, env="AUTO_RUN")  # must opt-in to auto-runs

    # ── Logging ───────────────────────────────────────────────────────────
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_file: str = Field("logs/agent.log", env="LOG_FILE")

    # ── Derived helpers (not from env) ────────────────────────────────────
    @property
    def issue_labels_list(self) -> List[str]:
        return [lbl.strip() for lbl in self.issue_labels.split(",") if lbl.strip()]

    @property
    def language_filter_list(self) -> List[str]:
        return [lang.strip() for lang in self.language_filter.split(",") if lang.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Allow extra variables in .env without throwing an error


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton."""
    return Settings()


# Convenience alias — use `from src.config.settings import settings` anywhere
settings = get_settings()
