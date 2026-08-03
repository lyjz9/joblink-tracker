from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _opening_tag(template: str, element_id: str) -> str:
    marker = f'id="{element_id}"'
    marker_index = template.index(marker)
    start = template.rfind("<", 0, marker_index)
    end = template.index(">", marker_index) + 1
    return template[start:end]


def test_secondary_add_methods_use_one_disclosure():
    template = (ROOT / "scraper" / "templates" / "index.html").read_text(encoding="utf-8")

    assert 'id="otherAddMenu"' in template
    assert "Other ways to add" in template
    assert 'id="manualAddButton"' in template
    assert 'id="loadCapturesButton"' in template
    assert 'class="capture-panel"' not in template
    assert template.index('id="manualPanel"') < template.index('class="results-band"')


def test_result_and_tracker_controls_start_hidden():
    template = (ROOT / "scraper" / "templates" / "index.html").read_text(encoding="utf-8")

    for element_id in (
        "resultsSummary",
        "resultFilters",
        "salaryControls",
        "resultsCommandRow",
        "selectionActions",
        "trackerBar",
    ):
        assert f'id="{element_id}"' in template
        assert "hidden" in _opening_tag(template, element_id)

    assert 'id="trackerSettings"' in template
    assert 'id="duplicateMode"' in template


def test_render_progressively_reveals_workspace_controls():
    source = (ROOT / "scraper" / "static" / "app.js").read_text(encoding="utf-8")

    assert "elements.resultsSummary.hidden = !hasJobs" in source
    assert "elements.resultFilters.hidden = !hasJobs" in source
    assert "elements.salaryControls.hidden = !hasJobs" in source
    assert "elements.resultsCommandRow.hidden = !hasJobs" in source
    assert "elements.selectionActions.hidden = !someSelected" in source
    assert "elements.trackerBar.hidden = !hasJobs" in source
    assert "elements.retryAll.hidden = !hasFlaggedJobs" in source
