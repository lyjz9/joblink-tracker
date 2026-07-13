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


def test_gunicorn_defaults_to_hugging_face_port(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)

    config = runpy.run_path(str(ROOT / "gunicorn.conf.py"))

    assert config["bind"] == "0.0.0.0:7860"


def test_dockerfile_installs_chromium_and_runs_unprivileged():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.startswith("FROM python:3.12-bookworm")
    assert "playwright install --with-deps chromium" in dockerfile
    assert 'ENTRYPOINT ["/usr/bin/tini", "--"]' in dockerfile
    assert "useradd --create-home --uid 1000 joblink" in dockerfile
    assert "USER joblink" in dockerfile
    assert "PORT=7860" in dockerfile
    assert "EXPOSE 7860" in dockerfile
    assert "os.environ.get('PORT', '7860')" in dockerfile
    assert "JOBLINK_SCRAPE_WORKERS=1" in dockerfile
    assert "JOBLINK_MAX_PENDING_JOBS=10" in dockerfile
    assert '"scraper.app:app"' in dockerfile
    assert "JOBLINK_SECRET_KEY=" not in dockerfile


def test_hugging_face_workflow_syncs_the_docker_space():
    workflow = (
        ROOT / ".github" / "workflows" / "deploy-huggingface.yml"
    ).read_text(encoding="utf-8")

    assert "branches:" in workflow
    assert "- main" in workflow
    assert "workflow_dispatch:" in workflow
    assert "actions/checkout@v6" in workflow
    assert "huggingface/hub-sync@v0.1.0" in workflow
    assert "huggingface_repo_id: ${{ vars.HF_SPACE_ID }}" in workflow
    assert "hf_token: ${{ secrets.HF_TOKEN }}" in workflow
    assert "space_sdk: docker" in workflow


def test_production_requirements_include_gunicorn():
    requirements = (ROOT / "requirements-prod.txt").read_text(encoding="utf-8")

    assert "-r requirements.txt" in requirements
    assert "gunicorn==26.0.0" in requirements
