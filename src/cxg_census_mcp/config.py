"""Settings from ``CXG_CENSUS_MCP_*`` env vars (pydantic-settings)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from platformdirs import user_cache_dir
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_cache_dir() -> Path:
    # appauthor=False keeps the path flat on Windows; on macOS/Linux this is
    # ~/Library/Caches/cxg-census-mcp / ~/.cache/cxg-census-mcp respectively.
    return Path(user_cache_dir("cxg-census-mcp", appauthor=False))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CXG_CENSUS_MCP_",
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    # --- Census ---
    census_version: str = "stable"
    mock_mode: bool = False

    # --- Cache root ---
    cache_dir: Path = Field(default_factory=_default_cache_dir)

    # --- OLS ---
    ols_base: str = "https://www.ebi.ac.uk/ols4/api"
    ols_cache_ttl: int = 60 * 60 * 24 * 30  # 30 days
    facet_cache_ttl: int = 60 * 60 * 24  # 24 hours
    plan_cache_ttl: int = 60 * 60 * 24 * 7  # 7 days

    # --- Rate / circuit breaker ---
    max_http_per_minute: int = 120
    ols_circuit_breaker_fails: int = 5

    # --- Tier caps ---
    max_tier1_cells: int = 5_000_000
    max_tier1_runtime_ms: int = 15_000
    max_expression_cells: int = 2_000_000
    max_expression_genes: int = 50
    max_expression_groups: int = 100
    max_expansion_terms: int = 256
    max_preview_rows: int = 200
    preview_default_rows: int = 20

    # --- LRU / progress ---
    last_call_lru_size: int = 64
    progress_min_ms: int = 750

    # --- Logging ---
    log_level: str = "WARNING"

    @field_validator("cache_dir", mode="before")
    @classmethod
    def _expand(cls, v):
        if isinstance(v, str):
            v = Path(v).expanduser()
        return v

    @field_validator("log_level")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()

    def ensure_dirs(self) -> None:
        for sub in ("ols", "facets", "plans"):
            (self.cache_dir / sub).mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings


def reset_settings_cache() -> None:
    """Test helper: clear the cached settings instance."""
    get_settings.cache_clear()
