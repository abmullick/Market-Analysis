from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    stoxim_api_key: str = ""
    groq_api_key: str = ""
    app_env: str = "development"
    app_port: int = 20090
    app_debug: bool = True
    mfapi_base_url: str = "https://api.mfapi.in"
    amfi_nav_url: str = "https://www.amfiindia.com/spages/NAVAll.txt"
    cache_ttl_seconds: int = 3600
