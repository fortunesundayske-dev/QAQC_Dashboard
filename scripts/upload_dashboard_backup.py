"""Create and upload a safe QA/QC Dashboard source backup to Cloudinary."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import zipfile

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from database.cloudinary_storage import cloudinary  # noqa: E402


EXCLUDED_DIRECTORIES = {
    ".git",
    ".pytest_cache",
    ".streamlit",
    ".venv",
    "__pycache__",
    "data/profile_photos",
    "outputs",
    "tmp",
    # Licensed/reference standard PDFs are deliberately excluded from cloud backups.
    "assets/standards",
}
EXCLUDED_FILES = {
    ".env",
    "data/qaqc_dashboard.db",
    "data/smtp_config.json",
    # Account records contain personal data and password hashes; MongoDB remains authoritative.
    "data/users.json",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def _relative(path):
    return path.relative_to(BASE_DIR).as_posix()


def should_include(path):
    relative = _relative(path)
    if relative.lower() in EXCLUDED_FILES:
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    return not any(relative == folder or relative.startswith(folder + "/") for folder in EXCLUDED_DIRECTORIES)


def build_backup(destination):
    included = []
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(BASE_DIR.rglob("*")):
            if path.is_file() and should_include(path):
                relative = _relative(path)
                archive.write(path, relative)
                included.append(relative)
    return included


def upload_backup(public_id=None):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    public_id = public_id or f"qaqc-dashboard/backups/qaqc-dashboard-{timestamp}.zip"
    with tempfile.TemporaryDirectory(prefix="qaqc-dashboard-backup-") as temp_dir:
        archive_path = Path(temp_dir) / "qaqc-dashboard.zip"
        included = build_backup(archive_path)
        result = cloudinary.uploader.upload(
            str(archive_path),
            resource_type="raw",
            type="authenticated",
            public_id=public_id,
            overwrite=False,
        )
    return result, included


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Build the archive without uploading it.")
    args = parser.parse_args()
    if args.dry_run:
        with tempfile.TemporaryDirectory(prefix="qaqc-dashboard-backup-") as temp_dir:
            archive_path = Path(temp_dir) / "qaqc-dashboard.zip"
            included = build_backup(archive_path)
            print(f"Backup validated: {len(included)} files, {archive_path.stat().st_size} bytes")
    else:
        result, included = upload_backup()
        print(f"Uploaded {len(included)} files to {result['public_id']}")


if __name__ == "__main__":
    main()
