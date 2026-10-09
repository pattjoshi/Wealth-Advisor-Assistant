from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WA_", env_file=".env", extra="ignore")

    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = "gpt-4o-mini"
    llm_max_output_tokens: int = 400
    llm_temperature: float = 0.0

    db_path: Path = Path("data/wealth_advisor.db")
    clients_dir: Path = Path("data/clients")
    crm_dir: Path = Path("data/crm")
    crm_records_file: Path | None = None

    crm_failure_rate: float = Field(default=0.0, ge=0.0, le=1.0)

    log_level: str = "INFO"
    log_file: Path = Path("logs/run.jsonl")

    @property
    def resolved_crm_records_file(self) -> Path:
        return self.crm_records_file or (self.crm_dir / "crm_records.json")


settings = Settings()
