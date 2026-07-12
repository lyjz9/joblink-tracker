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


def test_dockerfile_installs_chromium_and_runs_unprivileged():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.startswith("FROM python:3.12-bookworm")
    assert "playwright install --with-deps chromium" in dockerfile
    assert 'ENTRYPOINT ["/usr/bin/tini", "--"]' in dockerfile
    assert "USER joblink" in dockerfile
    assert '"scraper.app:app"' in dockerfile
    assert "JOBLINK_SECRET_KEY=" not in dockerfile


def test_render_blueprint_uses_readiness_and_generated_secret():
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")

    assert "runtime: docker" in blueprint
    assert "plan: standard" in blueprint
    assert "healthCheckPath: /ready" in blueprint
    assert "maxShutdownDelaySeconds: 60" in blueprint
    assert "generateValue: true" in blueprint
    assert "value: replace-me" not in blueprint


def test_production_requirements_include_gunicorn():
    requirements = (ROOT / "requirements-prod.txt").read_text(encoding="utf-8")

    assert "-r requirements.txt" in requirements
    assert "gunicorn==26.0.0" in requirements
