"""Upload the six generated QA/QC page backgrounds to Cloudinary."""

from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.cloudinary_storage import upload_page_background  # noqa: E402


BACKGROUND_DIR = ROOT_DIR / "assets" / "backgrounds"
BACKGROUND_FILES = {
    "quality-ai": "quality-ai.png",
    "quality-wins": "quality-wins.png",
    "quality-growth": "quality-growth.png",
    "quality-assurance": "quality-assurance.png",
    "quality-compliance": "quality-compliance.png",
    "quality-qa": "quality-qa.png",
}


def upload_all_backgrounds():
    return {
        name: upload_page_background(BACKGROUND_DIR / filename, name)
        for name, filename in BACKGROUND_FILES.items()
    }


if __name__ == "__main__":
    uploads = upload_all_backgrounds()
    for name, upload in uploads.items():
        print(
            f"{name}: {upload['public_id']} "
            f"v{upload['version']} {upload['width']}x{upload['height']}"
        )
