from cxg_census_mcp.utils.stable_hash import canonical_json, stable_hash


def test_canonical_json_is_key_order_independent():
    a = {"b": 2, "a": 1}
    b = {"a": 1, "b": 2}
    assert canonical_json(a) == canonical_json(b)


def test_stable_hash_deterministic_across_dict_orders():
    a = {"x": [1, 2], "y": "z"}
    b = {"y": "z", "x": [1, 2]}
    assert stable_hash(a) == stable_hash(b)


def test_stable_hash_differs_for_different_inputs():
    assert stable_hash({"x": 1}) != stable_hash({"x": 2})


def test_stable_hash_combines_multiple_parts():
    one = stable_hash("a", "b")
    two = stable_hash("ab")
    assert one != two  # null separator must matter


def test_stable_hash_length_param():
    h = stable_hash("payload", length=12)
    assert len(h) == 12
