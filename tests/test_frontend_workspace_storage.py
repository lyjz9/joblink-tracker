from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_workspace_is_saved_only_for_the_current_browser_tab():
    source = (ROOT / "scraper" / "static" / "app.js").read_text(encoding="utf-8")

    assert "sessionStorage.setItem(STORAGE_KEY" in source
    assert "sessionStorage.getItem(STORAGE_KEY" in source
    assert "sessionStorage.removeItem(STORAGE_KEY" in source
    assert "localStorage.setItem(STORAGE_KEY" not in source
    assert "localStorage.removeItem(STORAGE_KEY)" in source
