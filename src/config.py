from decimal import Decimal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "LipariBank AI"
    debug: bool = False

    database_url: str
    openai_api_key: str
    anthropic_api_key: str
    default_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434/v1"
    embedding_model: str = "text-embedding-3-small"
    max_tokens_per_request: int = 2000
    daily_budget_eur: Decimal = Decimal("5.00")  # il tetto di spesa del modello, al giorno
    jwt_secret: str
    soglia_approvazione_eur: Decimal = Decimal("5000")  # sopra, decide una persona
    soglia_doppia_firma_eur: Decimal = Decimal("50000")  # estensione: sopra, firmano in due


settings = Settings()  # raise at import if missing required
