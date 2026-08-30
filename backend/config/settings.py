from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    stoxim_api_key: str = ""
    groq_api_key: str = ""
    app_env: str = "development"
    app_port: int = 20090
    app_debug: bool = True
