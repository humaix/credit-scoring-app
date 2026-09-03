"""CNIC image validation and storage (Phase 1).

Registration captures the CNIC front and back. The images travel as base64
inside the JSON body, are validated here (format, dimensions, size,
brightness) and are stored under uploads/cnic/applicant_<id>/ with
server-generated filenames — no user-controlled path component ever reaches
the filesystem.
"""

import base64
import binascii
import secrets
from datetime import datetime
from io import BytesIO

from PIL import Image, ImageStat

from . import config
from .errors import ApiError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MIN_WIDTH = 320
MIN_HEIGHT = 240
MAX_BYTES = 8 * 1024 * 1024          # 8 MB decoded
MIN_BRIGHTNESS = 40.0                # 0-255 mean luminance

# honest labelling of what "verified" means in this prototype
CNIC_STATUS_NOTICE = (
    "Prototype identity check: CNIC format validated and front/back images "
    "captured and quality-checked. This prototype performs no NADRA "
    "verification and no OCR comparison — identity remains subject to review "
    "in any real deployment."
)


def _fail(side: str, reason: str) -> None:
    raise ApiError(422, "cnic_image", f"CNIC {side} image: {reason}")


def parse_image(side: str, data: str) -> tuple:
    """Validate one base64 image; return (raw bytes, file extension)."""
    # accept both raw base64 and data URLs from the browser camera component
    if data.startswith("data:"):
        _, _, data = data.partition(",")
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        _fail(side, "could not be decoded — capture or upload the image again")
    if len(raw) > MAX_BYTES:
        _fail(side, f"exceeds the {MAX_BYTES // (1024 * 1024)} MB limit")
    try:
        image = Image.open(BytesIO(raw))
        image.load()
    except Exception:
        _fail(side, "is not a valid image file")
    if image.format not in ALLOWED_FORMATS:
        _fail(side, "must be a JPEG, PNG or WebP image")
    if image.width < MIN_WIDTH or image.height < MIN_HEIGHT:
        _fail(
            side,
            f"is too small ({image.width}x{image.height}); "
            f"minimum {MIN_WIDTH}x{MIN_HEIGHT} pixels")
    brightness = ImageStat.Stat(image.convert("L")).mean[0]
    if brightness < MIN_BRIGHTNESS:
        _fail(side, "appears too dark — retake it in better lighting")
    return raw, image.format.lower().replace("jpeg", "jpg")


def store_image(applicant_id: int, side: str, raw: bytes, extension: str) -> str:
    """Write the validated image under the applicant's upload directory."""
    directory = config.UPLOADS_DIR / "cnic" / f"applicant_{applicant_id}"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{side}_{stamp}_{secrets.token_hex(4)}.{extension}"
    (directory / filename).write_bytes(raw)
    return filename
