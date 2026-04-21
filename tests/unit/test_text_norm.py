from cxg_census_mcp.utils.text_norm import normalize_text


def test_lowercase():
    assert normalize_text("CD4 T Cell") == "cd4 t cell"


def test_strips_diacritics():
    assert normalize_text("naïve T cell") == "naive t cell"


def test_collapses_whitespace():
    assert normalize_text("  CD4   T\tcell  ") == "cd4 t cell"


def test_keeps_hyphens():
    assert normalize_text("Smart-seq2") == "smart-seq2"


def test_drops_punctuation():
    # Apostrophe becomes whitespace, then collapses to a single space.
    assert normalize_text("alzheimer's disease") == "alzheimer s disease"


def test_none_safe():
    assert normalize_text(None) == ""  # type: ignore[arg-type]


def test_empty_string_safe():
    assert normalize_text("") == ""
