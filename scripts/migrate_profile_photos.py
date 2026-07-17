"""Migrate legacy local profile photos to Cloudinary-backed MongoDB records."""

import mimetypes
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.cloudinary_storage import upload_profile_photo  # noqa: E402
from database.mongo_users import load_users, save_users  # noqa: E402


class LocalUpload:
    def __init__(self, path):
        self.path = path
        self.name = path.name
        self.type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        self.size = path.stat().st_size

    def getvalue(self):
        return self.path.read_bytes()


def resolve_local_photo(value):
    path = Path(str(value))
    candidates = [path, ROOT_DIR / path]
    return next((candidate.resolve() for candidate in candidates if candidate.exists()), None)


def main():
    users = load_users()
    migrated = []
    skipped = []
    for username, user in users.items():
        current = str(user.get("profile_photo") or "").strip()
        if not current or current.startswith(("https://", "http://")):
            skipped.append(username)
            continue
        local_photo = resolve_local_photo(current)
        if not local_photo:
            print(f"Skipped {username}: local profile photo was not found.")
            continue
        asset = upload_profile_photo(LocalUpload(local_photo), username)
        user["profile_photo"] = asset["url"]
        user["profile_photo_asset"] = asset
        migrated.append(username)

    if migrated:
        save_users(users)
    print(f"Migrated {len(migrated)} profile photo(s): {', '.join(migrated) or 'none'}")
    print(f"Already cloud-backed or empty: {len(skipped)}")


if __name__ == "__main__":
    main()
