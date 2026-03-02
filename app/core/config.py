from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "EvalForge"
    app_env: str = "dev"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./evalforge.db"
    auto_create_tables: bool = True
    database_echo: bool = False
    judge_provider: str = "mock"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    judge_model: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
