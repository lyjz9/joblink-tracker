from __future__ import annotations

from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parents[1]


def test_gunicorn_uses_one_process_with_bounded_http_threads(monkeypatch):
    monkeypatch.setenv("PORT", "12345")
    monkeypatch.setenv("JOBLINK_HTTP_THREADS", "4")

    config = runpy.run_path(str(ROOT / "gunicorn.conf.py"))

    assert config["bind"] == "0.0.0.0:12345"
    assert config["workers"] == 1
    assert config["worker_class"] == "gthread"
    assert config["threads"] == 4
    assert config["preload_app"] is False


def test_gunicorn_defaults_to_container_port(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)

    config = runpy.run_path(str(ROOT / "gunicorn.conf.py"))

    assert config["bind"] == "0.0.0.0:10000"


def test_dockerfile_installs_chromium_and_runs_unprivileged():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.startswith("FROM python:3.12-bookworm")
    assert "playwright install --with-deps chromium" in dockerfile
    assert 'ENTRYPOINT ["/usr/bin/tini", "--"]' in dockerfile
    assert "useradd --create-home --uid 10001 joblink" in dockerfile
    assert "USER joblink" in dockerfile
    assert "PORT=10000" in dockerfile
    assert "EXPOSE 10000" in dockerfile
    assert "os.environ.get('PORT', '10000')" in dockerfile
    assert '"scraper.app:app"' in dockerfile
    assert "JOBLINK_SECRET_KEY=" not in dockerfile


def test_desktop_workflow_builds_a_portable_windows_artifact():
    workflow = (
        ROOT / ".github" / "workflows" / "build-windows-desktop.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "actions/checkout@v6" in workflow
    assert "actions/setup-python@v6" in workflow
    assert 'python-version: "3.12"' in workflow
    assert 'PLAYWRIGHT_BROWSERS_PATH = "0"' in workflow
    assert "playwright install chromium --only-shell" in workflow
    assert "packaging\\joblink_tracker.spec" in workflow
    assert "actions/upload-artifact@v4" in workflow


def test_desktop_requirements_pin_pyinstaller():
    requirements = (ROOT / "requirements-desktop.txt").read_text(encoding="utf-8")

    assert "-r requirements.txt" in requirements
    assert "pyinstaller==6.21.0" in requirements


def test_production_requirements_include_gunicorn():
    requirements = (ROOT / "requirements-prod.txt").read_text(encoding="utf-8")

    assert "-r requirements.txt" in requirements
    assert "gunicorn==26.0.0" in requirements
