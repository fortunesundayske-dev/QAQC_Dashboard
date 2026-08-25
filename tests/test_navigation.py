from pathlib import Path

import app


def test_section_registry_has_unique_existing_targets():
    section_ids = [section["id"] for section in app.SECTIONS]

    assert len(section_ids) == len(set(section_ids))
    assert "executive-dashboard" in section_ids
    assert all((app.SECTIONS_DIR / section["file"]).is_file() for section in app.SECTIONS)


def test_section_target_map_resolves_every_registered_module():
    targets = app._section_target_map()

    assert targets["app"] == "executive-dashboard"
    assert all(
        targets[Path(section["file"]).stem.lower()] == section["id"]
        for section in app.SECTIONS
    )


def test_every_legacy_page_is_registered_for_single_page_navigation():
    registered_files = {section["file"] for section in app.SECTIONS}
    page_files = {path.name for path in (app.BASE_DIR / "pages").glob("*.py")}

    assert page_files <= registered_files