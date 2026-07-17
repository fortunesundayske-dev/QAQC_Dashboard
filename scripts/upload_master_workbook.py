"""Upload the local QA/QC master workbook to the dashboard's Cloudinary asset."""

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.cloudinary_storage import (  # noqa: E402
    DEFAULT_MASTER_WORKBOOK_PUBLIC_ID,
    upload_master_workbook,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=ROOT_DIR / "data" / "QAQC_Master.xlsx")
    parser.add_argument("--public-id", default=DEFAULT_MASTER_WORKBOOK_PUBLIC_ID)
    args = parser.parse_args()
    result = upload_master_workbook(args.path, args.public_id)
    print(
        f"Uploaded {args.path.name} to {result['public_id']} "
        f"(version {result['version']}, {result['bytes']} bytes)."
    )


if __name__ == "__main__":
    main()
