from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "SCRAPER_"}

    # SERP API
    serp_api_key: str = ""
    serp_api_provider: str = "serpapi"  # "serpapi" or "serper"

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/scraper.db"

    # Scraping
    default_delay_min: float = 2.0
    default_delay_max: float = 5.0
    max_concurrent_requests: int = 5
    request_timeout: int = 30
    max_retries: int = 3
    respect_robots_txt: bool = True

    # Email Discovery
    enable_email_pattern_matching: bool = True
    enable_mx_verification: bool = True

    # App
    debug: bool = False


settings = Settings()
