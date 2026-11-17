from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Crypto AI Intelligence"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./crypto_ai.db"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000,http://localhost:8080"
    cvd_collector_enabled: bool = True
    cvd_collector_symbols: str = "BTCUSDT"
    cvd_collector_flush_interval_seconds: float = 2.0
    liquidation_collector_enabled: bool = True
    liquidation_collector_symbols: str = "BTCUSDT"
    liquidation_collector_flush_interval_seconds: float = 2.0
    signal_monitor_enabled: bool = True
    signal_monitor_poll_interval_seconds: float = 30.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def liquidation_collector_symbol_list(self) -> list[str]:
        return [
            symbol.strip().upper()
            for symbol in self.liquidation_collector_symbols.split(",")
            if symbol.strip()
        ]

    @property
    def cvd_collector_symbol_list(self) -> list[str]:
        return [
            symbol.strip().upper()
            for symbol in self.cvd_collector_symbols.split(",")
            if symbol.strip()
        ]

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
