"""Cloudinary file storage with strict validation and private delivery."""

import csv
from io import BytesIO
from io import StringIO
from pathlib import Path
import re
import secrets
import time
import zipfile
import warnings

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import cloudinary.uploader  # noqa: E402
import cloudinary.api  # noqa: E402
import cloudinary.utils  # noqa: E402

from database.settings import get_setting  # noqa: E402


cloudinary_url = str(get_setting("CLOUDINARY_URL", "")).strip()
if cloudinary_url:
    cloudinary.config(cloudinary_url=cloudinary_url)

DEFAULT_MASTER_WORKBOOK_PUBLIC_ID = "qaqc-dashboard/data/QAQC_Master.xlsx"
PAGE_BACKGROUND_FOLDER = "qaqc-dashboard/backgrounds"


MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
ALLOWED_ATTACHMENT_TYPES = ["png", "jpg", "jpeg", "pdf", "docx", "xlsx", "csv", "txt"]
MAX_PROFILE_PHOTO_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
MAX_OFFICE_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_OFFICE_PARTS = 1_000


def _safe_filename(filename):
    name = Path(str(filename or "attachment").replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")
    return (name or "attachment")[:160]


def _validated_bytes(uploaded_file, *, profile=False):
    data = uploaded_file.getvalue()
    declared_size = int(getattr(uploaded_file, "size", len(data)) or 0)
    limit = MAX_PROFILE_PHOTO_BYTES if profile else MAX_ATTACHMENT_BYTES
    if not data or declared_size != len(data):
        raise ValueError("The uploaded file is empty or incomplete.")
    if len(data) > limit:
        raise ValueError(f"The uploaded file is larger than {limit // (1024 * 1024)} MB.")
    return data


def _validate_image(data, suffix):
    try:
        from PIL import Image, ImageOps

        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                image.verify()
                image_format = str(image.format or "").lower()
            with Image.open(BytesIO(data)) as image:
                image = ImageOps.exif_transpose(image)
                image.load()
                if int(image.width) * int(image.height) > MAX_IMAGE_PIXELS:
                    raise ValueError("The image dimensions are too large.")
                output = BytesIO()
                if suffix in {"jpg", "jpeg"}:
                    image.convert("RGB").save(output, format="JPEG", quality=92, optimize=True)
                else:
                    mode = "RGBA" if "A" in image.getbands() else "RGB"
                    image.convert(mode).save(output, format="PNG", optimize=True)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("The upload is not a valid image file.") from exc
    expected = "jpeg" if suffix in {"jpg", "jpeg"} else "png"
    if image_format != expected:
        raise ValueError("The file content does not match its image extension.")
    return output.getvalue()


def _validate_office_document(data, suffix):
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            members = archive.infolist()
            names = {member.filename.replace("\\", "/") for member in members}
            lower_names = {name.lower() for name in names}
            if len(members) > MAX_OFFICE_PARTS:
                raise ValueError("The Office document contains too many internal files.")
            if sum(max(0, member.file_size) for member in members) > MAX_OFFICE_UNCOMPRESSED_BYTES:
                raise ValueError("The Office document expands beyond the safety limit.")
            if any(
                name.startswith("/") or "../" in f"/{name}" or name.endswith("/vbaproject.bin")
                or "/embeddings/" in f"/{name}" or "/activex/" in f"/{name}"
                for name in lower_names
            ):
                raise ValueError("Macros, embedded objects, and unsafe package paths are not accepted.")
            for member in members:
                if member.filename.lower().endswith(".rels"):
                    relationships = archive.read(member, pwd=None)
                    if b'TargetMode="External"' in relationships or b"TargetMode='External'" in relationships:
                        raise ValueError("Office documents with external links are not accepted.")
            required_prefix = "word/" if suffix == "docx" else "xl/"
            if "[Content_Types].xml" not in names or not any(name.startswith(required_prefix) for name in names):
                raise ValueError("The file content does not match its Office extension.")
    except ValueError:
        raise
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError("The upload is not a valid Office document.") from exc


def validate_upload(uploaded_file, allowed_types=None, *, profile=False):
    """Validate size, filename, extension, and content signature before cloud upload."""
    filename = _safe_filename(getattr(uploaded_file, "name", ""))
    suffix = Path(filename).suffix.lower().lstrip(".")
    allowed = set(allowed_types or ALLOWED_ATTACHMENT_TYPES)
    if suffix not in allowed:
        raise ValueError("This attachment type is not supported.")
    data = _validated_bytes(uploaded_file, profile=profile)
    if suffix in {"png", "jpg", "jpeg"}:
        data = _validate_image(data, suffix)
    elif suffix == "pdf":
        if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-4096:]:
            raise ValueError("The upload is not a complete PDF file.")
        if any(marker in data for marker in (b"/JavaScript", b"/JS", b"/Launch", b"/EmbeddedFile")):
            raise ValueError("PDFs containing active or embedded content are not accepted.")
    elif suffix in {"docx", "xlsx"}:
        _validate_office_document(data, suffix)
    elif suffix in {"txt", "csv"}:
        if b"\x00" in data:
            raise ValueError("Text uploads cannot contain binary data.")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Text and CSV uploads must use UTF-8 encoding.") from exc
        if suffix == "csv":
            for row in csv.reader(StringIO(text)):
                if any(cell.lstrip().startswith(("=", "+", "-", "@")) for cell in row):
                    raise ValueError("CSV uploads cannot contain spreadsheet formulas.")
    return filename, suffix, data


def private_asset_url(asset, expires_in=600):
    """Create a short-lived signed download URL without persisting credentials."""
    if not asset or not asset.get("public_id"):
        return ""
    return cloudinary.utils.private_download_url(
        asset["public_id"],
        asset.get("format"),
        resource_type=asset.get("resource_type", "raw"),
        type=asset.get("delivery_type", "authenticated"),
        attachment=asset.get("name") or False,
        expires_at=int(time.time()) + max(60, min(int(expires_in), 3600)),
    )


def upload_support_attachment(uploaded_file):
    """Upload a Streamlit UploadedFile-compatible object to Cloudinary."""
    filename, suffix, data = validate_upload(uploaded_file)
    result = cloudinary.uploader.upload(
        data,
        resource_type="auto",
        type="authenticated",
        folder="qaqc-dashboard/support",
        public_id=secrets.token_urlsafe(24),
        use_filename=False,
        unique_filename=False,
    )
    return {
        "name": filename,
        "content_type": getattr(uploaded_file, "type", None) or "application/octet-stream",
        "bytes": int(result.get("bytes") or len(data)),
        "public_id": result["public_id"],
        "resource_type": result.get("resource_type", "raw"),
        "delivery_type": "authenticated",
        "format": result.get("format") or suffix,
    }


def delete_attachment(attachment):
    if not attachment or not attachment.get("public_id"):
        return False
    result = cloudinary.uploader.destroy(
        attachment["public_id"],
        resource_type=attachment.get("resource_type", "image"),
        type=attachment.get("delivery_type", "authenticated"),
        invalidate=True,
    )
    return result.get("result") in {"ok", "not found"}


def upload_profile_photo(uploaded_file, username):
    _filename, suffix, data = validate_upload(
        uploaded_file, {"png", "jpg", "jpeg"}, profile=True,
    )
    result = cloudinary.uploader.upload(
        data,
        resource_type="image",
        type="authenticated",
        folder="qaqc-dashboard/profiles",
        public_id=f"{username}-{secrets.token_urlsafe(12)}",
        overwrite=True,
        invalidate=True,
        transformation=[{"width": 512, "height": 512, "crop": "fill", "gravity": "face"}],
    )
    return {
        "public_id": result["public_id"],
        "resource_type": "image",
        "delivery_type": "authenticated",
        "format": result.get("format") or suffix,
        "bytes": int(result.get("bytes") or len(data)),
        "updated_at": result.get("created_at"),
    }


def upload_master_workbook(path, public_id=DEFAULT_MASTER_WORKBOOK_PUBLIC_ID):
    path = Path(path)
    if not path.exists() or path.suffix.lower() != ".xlsx":
        raise ValueError("A valid .xlsx master workbook is required.")
    result = cloudinary.uploader.upload(
        str(path),
        resource_type="raw",
        public_id=public_id,
        overwrite=True,
        invalidate=True,
    )
    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
        "version": int(result["version"]),
        "bytes": int(result.get("bytes") or path.stat().st_size),
        "updated_at": result.get("created_at"),
    }


def upload_page_background(path, asset_name):
    """Upload one public dashboard background with a stable Cloudinary asset ID."""
    path = Path(path)
    asset_name = str(asset_name or "").strip().lower()
    if not path.exists() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("A valid PNG, JPEG, or WebP background image is required.")
    if not asset_name or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for character in asset_name):
        raise ValueError("Background asset names may contain lowercase letters, numbers, hyphens, and underscores.")
    result = cloudinary.uploader.upload(
        str(path),
        resource_type="image",
        type="upload",
        public_id=f"{PAGE_BACKGROUND_FOLDER}/{asset_name}",
        overwrite=True,
        invalidate=True,
    )
    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
        "version": int(result["version"]),
        "bytes": int(result.get("bytes") or path.stat().st_size),
        "width": int(result.get("width") or 0),
        "height": int(result.get("height") or 0),
        "format": result.get("format") or path.suffix.lower().lstrip("."),
    }


def get_master_workbook_reference(public_id=DEFAULT_MASTER_WORKBOOK_PUBLIC_ID):
    result = cloudinary.api.resource(public_id, resource_type="raw")
    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
        "version": int(result["version"]),
        "bytes": int(result.get("bytes") or 0),
        "updated_at": result.get("updated_at") or result.get("created_at"),
    }
