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
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    judge_model_anthropic: str = "claude-haiku-4-5"
    mistral_api_key: str = ""
    mistral_base_url: str = "https://api.mistral.ai/v1"
    judge_model_mistral: str = "mistral-small-latest"
    async_backend: str = "local"
    redis_url: str = "redis://localhost:6379/0"
    redis_queue_name: str = "evalforge:eval_jobs"
    platform_api_key: str = ""
    default_workspace_id: str = "default"
    release_gate_alert_webhook_url: str = ""
    default_user_role: str = "viewer"
    # Role granted to any caller who presents a valid API key.
    # Only honoured when platform_api_key is set; ignored in dev mode.
    platform_user_role: str = "editor"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
