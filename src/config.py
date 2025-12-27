from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Kalshi Configuration
    kalshi_api_key_id: str = Field(..., validation_alias="KALSHI_API_KEY_ID")
    kalshi_private_key_path: Path = Field(..., validation_alias="KALSHI_PRIVATE_KEY_PATH")
    kalshi_base_url: str = "https://api.elections.kalshi.com/trade-api/v2"

    # Polymarket Configuration
    poly_api_key: str = Field(..., validation_alias="POLY_API_KEY")
    poly_secret: str = Field(..., validation_alias="POLY_SECRET")
    poly_passphrase: str = Field(..., validation_alias="POLY_PASSPHRASE")
    poly_clob_url: str = "https://clob.polymarket.com"
    poly_gamma_url: str = "https://gamma-api.polymarket.com"

    # Bot Settings
    min_profit_threshold: float = Field(
        default=0.02, validation_alias="MIN_PROFIT_THRESHOLD"
    )
    poll_interval_seconds: int = Field(
        default=30, validation_alias="POLL_INTERVAL_SECONDS"
    )
    fuzzy_match_threshold: int = Field(
        default=80, validation_alias="FUZZY_MATCH_THRESHOLD"
    )

    # Rate Limiting
    kalshi_requests_per_second: float = 5.0
    poly_requests_per_second: float = 10.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}
