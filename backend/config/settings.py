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

    # Bond Central credit-ratings index (supplementary source for corporate
    # bonds; refreshed independently of list/detail requests into SQLite).
    bond_central_ratings_db: str = "data/cache/bond_central_ratings.sqlite3"
    bond_central_ratings_ttl_seconds: int = 86400
    bond_central_ratings_page_delay_seconds: float = 0.2
    bond_central_ratings_max_retries: int = 3
    bond_central_ratings_auto_refresh: bool = True
