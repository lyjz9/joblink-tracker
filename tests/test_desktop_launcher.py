from __future__ import annotations

import io
from pathlib import Path

import desktop_launcher


def test_desktop_environment_uses_local_app_data_and_bundled_browser(tmp_path):
    env = {"LOCALAPPDATA": str(tmp_path)}

    data_dir = desktop_launcher.configure_environment(env, frozen=True)

    assert data_dir == tmp_path / "Linc"
    assert env["JOBLINK_ENV"] == "local"
    assert env["JOBLINK_CAPTURE_ENABLED"] == "true"
    assert env["JOBLINK_VERIFY_BROWSER_ON_STARTUP"] == "true"
    assert env["JOBLINK_LOG_DIR"] == str(data_dir / "logs")
    assert env["PLAYWRIGHT_BROWSERS_PATH"] == "0"


def test_desktop_environment_does_not_replace_explicit_settings(tmp_path):
    env = {
        "LOCALAPPDATA": str(tmp_path),
        "JOBLINK_SCRAPE_WORKERS": "1",
        "PLAYWRIGHT_BROWSERS_PATH": "C:\\shared-browser",
    }

    desktop_launcher.configure_environment(env, frozen=True)

    assert env["JOBLINK_SCRAPE_WORKERS"] == "1"
    assert env["PLAYWRIGHT_BROWSERS_PATH"] == "C:\\shared-browser"


def test_windowed_build_redirects_missing_output_streams(monkeypatch, tmp_path):
    monkeypatch.setattr(desktop_launcher.sys, "stdout", None)
    monkeypatch.setattr(desktop_launcher.sys, "stderr", None)

    stream = desktop_launcher.configure_output_streams(tmp_path)
    try:
        print("desktop log check")
        stream.flush()
        log_text = (tmp_path / "logs" / "desktop.log").read_text(encoding="utf-8")
        assert "desktop log check" in log_text
    finally:
        stream.close()
        monkeypatch.setattr(desktop_launcher.sys, "stdout", io.StringIO())
        monkeypatch.setattr(desktop_launcher.sys, "stderr", io.StringIO())


def test_packaging_spec_includes_web_assets_and_project_modules():
    root = Path(__file__).resolve().parents[1]
    spec = (root / "packaging" / "linc.spec").read_text(encoding="utf-8")

    assert 'collect_all("playwright")' in spec
    assert 'collect_submodules("scraper")' in spec
    assert 'collect_submodules("export")' in spec
    assert '"scraper/templates"' in spec
    assert '"scraper/static"' in spec
    assert 'name="Linc"' in spec
