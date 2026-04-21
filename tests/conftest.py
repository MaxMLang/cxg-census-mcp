"""Default: mock Census + isolated cache; ``-m live`` for network tests."""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "live: requires live OLS / Census; excluded by default")
    config.addinivalue_line("markers", "integration: full tool envelope (still mock)")
    config.addinivalue_line("markers", "e2e: end-to-end LLM flow against mock backend")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("-m") and "live" in str(config.getoption("-m")):
        return
    skip_live = pytest.mark.skip(reason="live tests skipped (use `pytest -m live`)")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Fresh cache dir, mock on, clear settings + lru singletons."""
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setenv("CXG_CENSUS_MCP_CACHE_DIR", str(cache))
    monkeypatch.setenv("CXG_CENSUS_MCP_MOCK_MODE", "1")
    monkeypatch.setenv("CXG_CENSUS_MCP_LOG_LEVEL", "ERROR")
    monkeypatch.setenv("CXG_CENSUS_MCP_PROGRESS_MIN_MS", "10")

    from cxg_census_mcp import config as _cfg

    _cfg.reset_settings_cache()

    for mod_path, getter in (
        ("cxg_census_mcp.caches.ols_cache", "get_ols_cache"),
        ("cxg_census_mcp.caches.facet_cache", "get_facet_cache"),
        ("cxg_census_mcp.caches.plan_cache", "get_plan_cache"),
        ("cxg_census_mcp.caches.filter_lru", "get_filter_lru"),
        ("cxg_census_mcp.caches.census_handle", "get_handle_pool"),
        ("cxg_census_mcp.clients.census", "get_census_client"),
        ("cxg_census_mcp.clients.http", "get_http_client"),
        ("cxg_census_mcp.clients.ols", "get_ols_client"),
    ):
        fn = getattr(importlib.import_module(mod_path), getter, None)
        if fn is not None and hasattr(fn, "cache_clear"):
            fn.cache_clear()

    yield

    _cfg.reset_settings_cache()


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


def _read_yaml(path: Path):
    import yaml  # type: ignore

    return yaml.safe_load(path.read_text())


@pytest.fixture
def load_yaml():
    return _read_yaml
