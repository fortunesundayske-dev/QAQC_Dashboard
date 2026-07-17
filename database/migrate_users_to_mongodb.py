"""One-time migration of the legacy users.json file into MongoDB."""

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.mongo_users import ensure_user_schema, save_users  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT_DIR / "data" / "users.json")
    parser.add_argument("--force", action="store_true", help="replace records in a non-empty users collection")
    args = parser.parse_args()

    users = json.loads(args.source.read_text(encoding="utf-8"))
    collection = ensure_user_schema()
    existing = collection.count_documents({})
    if existing and not args.force:
        raise SystemExit(
            f"Migration stopped: MongoDB already contains {existing} user(s). "
            "Use --force only if replacing them is intentional."
        )
    save_users(users)
    print(f"Migrated {len(users)} user(s) to MongoDB and verified the users schema/indexes.")


if __name__ == "__main__":
    main()
