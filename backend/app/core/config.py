from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SAP Knowledge Tool API"
    database_url: str = "sqlite:///./sap_knowledge.db"
    auth_secret_key: str = "change-me-in-production"
    auth_algorithm: str = "HS256"
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = "admin123"

    # LLM enhancement (optional hybrid step after rule-based extraction)
    use_llm_enhancement: bool = False
    anthropic_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
