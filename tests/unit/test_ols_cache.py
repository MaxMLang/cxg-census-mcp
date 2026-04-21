from cxg_census_mcp.caches.ols_cache import get_ols_cache


def test_set_and_get_round_trip():
    cache = get_ols_cache()
    cache.set("CL", "search", {"q": "x"}, [{"curie": "CL:1"}])
    out = cache.get("CL", "search", {"q": "x"})
    assert out == [{"curie": "CL:1"}]


def test_miss_returns_none():
    cache = get_ols_cache()
    assert cache.get("CL", "search", {"q": "missing"}) is None


def test_negative_cache_short_circuits_misses():
    cache = get_ols_cache()
    cache.set_negative("MONDO", "search", {"q": "neg"})
    assert cache.is_negative("MONDO", "search", {"q": "neg"})
    assert cache.get("MONDO", "search", {"q": "neg"}) is None


def test_hit_miss_counters_track_calls():
    cache = get_ols_cache()
    base_hits = cache.hits
    base_misses = cache.misses

    cache.set("CL", "search", {"q": "y"}, [])
    cache.get("CL", "search", {"q": "y"})
    cache.get("CL", "search", {"q": "absent"})

    assert cache.hits == base_hits + 1
    assert cache.misses == base_misses + 1
