from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class PostgresSettings(BaseSettings):
    """PostgreSQL connection and pool settings. Load from env with POSTGRES__ prefix."""

    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    user: str = Field(default="postgres", description="Database user")
    password: str = Field(default="", description="Database password")
    db: str = Field(default="postgres", description="Database name")
    create_tables: bool = Field(
        default=True,
        description="If True, run Base.metadata.create_all on engine creation (dev). Set False in prod and use migrations.",
    )
    pool_size: int = Field(default=5, description="Connection pool size")
    max_overflow: int = Field(default=0, description="Max overflow connections")
    pool_timeout: int = Field(default=30, description="Pool timeout seconds")
    pool_recycle: int = Field(
        default=1800, description="Recycle connections after this many seconds"
    )

    model_config = SettingsConfigDict(
        env_prefix="POSTGRES__",
        populate_by_name=True,
        extra="ignore",
    )
