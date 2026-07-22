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
