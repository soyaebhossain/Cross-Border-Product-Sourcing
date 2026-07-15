from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "Cross Border Catalog Service"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/cross_border"
    jwt_secret: str = "change-me-access"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"
    legacy_sqlite_path: str | None = None
    legacy_media_path: str | None = None
    supply_chain_csv_path: str | None = None
    media_url_path: str = "/media"

    model_config = SettingsConfigDict(
        env_prefix="CATALOG_",
        case_sensitive=False,
    )

    def resolved_legacy_sqlite_path(self) -> Path:
        if self.legacy_sqlite_path:
            return Path(self.legacy_sqlite_path)
        return ROOT_DIR / "backend" / "db.sqlite3"

    def resolved_legacy_media_path(self) -> Path:
        if self.legacy_media_path:
            return Path(self.legacy_media_path)
        return ROOT_DIR / "backend" / "media"

    def resolved_supply_chain_csv_path(self) -> Path:
        if self.supply_chain_csv_path:
            return Path(self.supply_chain_csv_path)
        return ROOT_DIR / "Data" / "supply_chain_data.csv"


@lru_cache
def get_settings() -> Settings:
    return Settings()
