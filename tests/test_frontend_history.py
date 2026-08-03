from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_history_view_has_local_privacy_and_bulk_controls():
    template = (ROOT / "scraper" / "templates" / "index.html").read_text(encoding="utf-8")

    assert '{% if history_enabled %}' in template
    assert 'id="historyView"' in template
    assert 'id="historySearch"' in template
    assert 'id="restoreHistoryButton"' in template
    assert 'id="deleteHistoryButton"' in template
    assert 'id="clearHistoryButton"' in template
    assert "Saved only on this computer" in template


def test_frontend_saves_and_restores_history_without_changing_session_storage():
    source = (ROOT / "scraper" / "static" / "app.js").read_text(encoding="utf-8")

    assert "fetch('/api/history'" in source
    assert "saveJobsToHistory(changedJobs)" in source
    assert "saveJobsToHistory([retried])" in source
    assert "saveJobsToHistory([job])" in source
    assert "restoreSelectedHistory" in source
    assert "sessionStorage.setItem(STORAGE_KEY" in source
    assert "localStorage.setItem" not in source
