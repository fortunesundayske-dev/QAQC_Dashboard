from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_shared_ui_keeps_depth_scroll_and_accessibility_motion_contract() -> None:
    shared_ui = (ROOT / "utils.py").read_text(encoding="utf-8")

    assert "qaqc-scroll-reveal" in shared_ui
    assert "animation-timeline: view()" in shared_ui
    assert "prefers-reduced-motion: reduce" in shared_ui
    assert ".analytics-metric:hover" in shared_ui
    assert ".cal-metric:hover" in shared_ui
    assert "pointer: coarse" in shared_ui


def test_dashboard_copy_does_not_present_unverified_comparisons_or_dates() -> None:
    executive = (ROOT / "pages" / "Executive_Dashboard.py").read_text(encoding="utf-8")
    calibration = (ROOT / "pages" / "Calibration_Log.py").read_text(encoding="utf-8")

    assert "vs last month" not in executive
    assert "May 1 – Jun 2, 2026" not in calibration


def test_streamlit_surfaces_use_current_responsive_width_api() -> None:
    source_files = [ROOT / "app.py", ROOT / "auth.py", ROOT / "utils.py"]
    source_files.extend((ROOT / "pages").glob("*.py"))

    legacy_calls = sum(
        source.read_text(encoding="utf-8").count("use_container_width=True")
        for source in source_files
    )
    assert legacy_calls == 1  # Compatibility parameter on the shared dataframe wrapper.


def test_every_dashboard_page_uses_the_shared_page_header() -> None:
    page_sources = list((ROOT / "pages").glob("*.py"))

    assert len(page_sources) == 21
    for source in page_sources:
        page = source.read_text(encoding="utf-8")
        assert "render_page_header(" in page, f"{source.name} bypasses the shared page header"


def test_shared_ui_has_professional_action_and_responsive_hierarchy() -> None:
    shared_ui = (ROOT / "utils.py").read_text(encoding="utf-8")

    assert '[data-testid="stBaseButton-primary"]' in shared_ui
    assert '[data-testid="stBaseButton-secondary"]:hover' in shared_ui
    assert '[class*="st-key-"][class*="delete"] button:not(:disabled)' in shared_ui
    assert ':has(> div[data-testid="column"]:nth-child(4))' in shared_ui
    assert ':not(:has(.st-key-page_navigation_popover))' in shared_ui
    assert ".js-plotly-plot:focus-within .modebar" in shared_ui


def test_high_interaction_pages_use_controlled_forms_and_current_pdf_preview() -> None:
    academy = (ROOT / "pages" / "Learning_Academy.py").read_text(encoding="utf-8")
    standards = (ROOT / "pages" / "Standards_Library.py").read_text(encoding="utf-8")

    assert 'st.form("academy_knowledge_check"' in academy
    assert 'st.form("academy_training_record"' in academy
    assert 'type="primary"' in academy
    assert "st.iframe(" in standards
    assert "components.html(" not in standards
