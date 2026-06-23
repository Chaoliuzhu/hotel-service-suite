"""
Hotel Service Suite - Barcode & QR Code Generator.

Provides standalone generation of Code128 barcodes and QR codes for hotel
luggage tags and lost-and-found labels. All operations are local and require
no external service dependencies.

Dependencies:
    - ``python-barcode`` (Code128 barcode generation)
    - ``qrcode[pil]`` (QR code generation)
    - ``Pillow`` (image manipulation)

Usage::

    from barcode.generator import (
        generate_luggage_code,
        generate_lost_found_code,
        generate_label_data,
    )

    code = generate_luggage_code(seq=1)
    label = generate_label_data(
        code=code,
        title="LUGGAGE TAG",
        subtitle="Grand Hotel",
        info_lines=["Guest: Zhang Wei", "Room: 1208", "Pieces: 2"],
    )
"""

from __future__ import annotations

import base64
import io
import os
import random
import sys
import threading
from datetime import datetime
from typing import Any

# ---------------------------------------------------------------------------
# Third-party imports with naming-collision workaround
# ---------------------------------------------------------------------------
# Our local package is named ``barcode``, which shadows the third-party
# ``python-barcode`` library (also installed as ``barcode``).  We resolve
# this by temporarily removing our local package from ``sys.modules`` and
# the project root from ``sys.path``, importing the real library, then
# restoring everything so that ``from barcode.generator import ...``
# continues to work normally.
# ---------------------------------------------------------------------------

_pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 1. Save and remove our local barcode entries
_saved_local: dict[str, Any] = {}
for _k in list(sys.modules):
    if _k == "barcode" or _k.startswith("barcode."):
        _saved_local[_k] = sys.modules.pop(_k)

# 2. Remove project root from sys.path so Python can't find our local package
_path_backup = sys.path[:]
sys.path = [
    p for p in sys.path
    if os.path.abspath(p or ".") != _pkg_root and p != ""
]

try:
    import barcode as _pybarcode  # type: ignore[no-redef]
    from barcode.writer import ImageWriter  # type: ignore[no-redef]
except ImportError as _exc:
    raise ImportError(
        "The 'python-barcode' library is required but could not be imported. "
        "Install it with:  pip install python-barcode"
    ) from _exc
finally:
    # 3. Clean the real python-barcode out of sys.modules (we keep references)
    for _k in list(sys.modules):
        if _k == "barcode" or _k.startswith("barcode."):
            del sys.modules[_k]
    # 4. Restore sys.path and our local package
    sys.path[:] = _path_backup
    sys.modules.update(_saved_local)

from PIL import Image
import qrcode
from qrcode.constants import ERROR_CORRECT_M


# ---------------------------------------------------------------------------
# Module-level sequence counters (thread-safe)
# ---------------------------------------------------------------------------
_seq_lock = threading.Lock()
_luggage_seq: int = 0
_lost_found_seq: int = 0


def _next_seq(current: int) -> int:
    """Increment and return the next sequence number, wrapping at 999."""
    nxt = current + 1
    if nxt > 999:
        nxt = 1
    return nxt


# ---------------------------------------------------------------------------
# Public API - Code Generators
# ---------------------------------------------------------------------------


def generate_luggage_code(
    seq: int | None = None,
    date: datetime | None = None,
) -> str:
    """Generate a luggage tracking code.

    Format: ``LG-{YYYYMMDD}-{3-digit-seq}``

    Args:
        seq: Explicit sequence number (1-999). When *None*, an internal
             auto-incrementing counter is used.
        date: Override the date portion. Defaults to today.

    Returns:
        A formatted luggage code string, e.g. ``LG-20260623-001``.

    Raises:
        ValueError: If *seq* is outside the 1-999 range.
    """
    global _luggage_seq
    date = date or datetime.now()
    if seq is None:
        with _seq_lock:
            _luggage_seq = _next_seq(_luggage_seq)
            seq = _luggage_seq
    if not (1 <= seq <= 999):
        raise ValueError(f"Luggage sequence must be 1-999, got {seq}")
    return f"LG-{date.strftime('%Y%m%d')}-{seq:03d}"


def generate_lost_found_code(
    seq: int | None = None,
    date: datetime | None = None,
) -> str:
    """Generate a lost-and-found tracking code.

    Format: ``LF-{YYYYMMDD}-{3-digit-seq}``

    Args:
        seq: Explicit sequence number (1-999). When *None*, an internal
             auto-incrementing counter is used.
        date: Override the date portion. Defaults to today.

    Returns:
        A formatted lost-and-found code string, e.g. ``LF-20260623-001``.

    Raises:
        ValueError: If *seq* is outside the 1-999 range.
    """
    global _lost_found_seq
    date = date or datetime.now()
    if seq is None:
        with _seq_lock:
            _lost_found_seq = _next_seq(_lost_found_seq)
            seq = _lost_found_seq
    if not (1 <= seq <= 999):
        raise ValueError(f"Lost & Found sequence must be 1-999, got {seq}")
    return f"LF-{date.strftime('%Y%m%d')}-{seq:03d}"


def generate_verification_code(length: int = 4) -> str:
    """Generate a random numeric verification code for pickup verification.

    Args:
        length: Number of digits (default 4, yielding 0000-9999).

    Returns:
        A zero-padded random numeric string.

    Raises:
        ValueError: If *length* is less than 1.
    """
    if length < 1:
        raise ValueError(f"Verification code length must be >= 1, got {length}")
    upper = 10**length
    code = random.randint(0, upper - 1)
    return f"{code:0{length}d}"


def reset_sequences(luggage: int = 0, lost_found: int = 0) -> None:
    """Reset the internal auto-increment counters.

    Useful at midnight rollover or during testing.

    Args:
        luggage: New luggage sequence base value.
        lost_found: New lost-and-found sequence base value.
    """
    global _luggage_seq, _lost_found_seq
    with _seq_lock:
        _luggage_seq = luggage
        _lost_found_seq = lost_found


# ---------------------------------------------------------------------------
# Public API - Image Generators
# ---------------------------------------------------------------------------


def generate_barcode_image(
    data: str,
    module_width: float = 0.4,
    module_height: float = 12.0,
    font_size: int = 8,
    quiet_zone: float = 3.0,
    format: str = "PNG",
) -> bytes:
    """Generate a Code128 barcode as a PNG byte string.

    Args:
        data: The text data to encode (e.g. ``LG-20260623-001``).
        module_width: Width of the narrowest bar in mm.
        module_height: Height of the bars in mm.
        font_size: Font size for the human-readable text below the barcode.
        quiet_zone: Width of the quiet zone (margins) in mm.
        format: Image format (default ``PNG``).

    Returns:
        Raw image bytes in the specified format.

    Raises:
        ValueError: If *data* is empty or contains unsupported characters.
    """
    if not data:
        raise ValueError("Barcode data must not be empty")

    writer = ImageWriter()
    code128 = _pybarcode.get("code128", data, writer=writer)

    buffer = io.BytesIO()
    code128.write(
        buffer,
        options={
            "module_width": module_width,
            "module_height": module_height,
            "font_size": font_size,
            "quiet_zone": quiet_zone,
            "format": format,
            "write_text": True,
        },
    )
    buffer.seek(0)
    return buffer.read()


def generate_qr_image(
    data: str,
    box_size: int = 10,
    border: int = 2,
    error_correction: int = ERROR_CORRECT_M,
    format: str = "PNG",
) -> bytes:
    """Generate a QR code as a PNG byte string.

    Args:
        data: The text data to encode.
        box_size: Size of each box in pixels.
        border: Border size in boxes.
        error_correction: Error correction level
            (``qrcode.constants.ERROR_CORRECT_*``).
        format: Image format (default ``PNG``).

    Returns:
        Raw image bytes in the specified format.

    Raises:
        ValueError: If *data* is empty.
    """
    if not data:
        raise ValueError("QR code data must not be empty")

    qr = qrcode.QRCode(
        version=None,  # auto-determine
        error_correction=error_correction,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img: Image.Image = qr.make_image(fill_color="black", back_color="white")  # type: ignore[assignment]

    buffer = io.BytesIO()
    img.save(buffer, format=format)
    buffer.seek(0)
    return buffer.read()


# ---------------------------------------------------------------------------
# Public API - Base64 Helpers
# ---------------------------------------------------------------------------


def image_to_base64(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """Convert raw image bytes to a base64 data-URI string.

    Args:
        image_bytes: Raw PNG (or other format) bytes.
        mime_type: MIME type prefix for the data URI.

    Returns:
        A string like ``data:image/png;base64,iVBORw...``.
    """
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def generate_barcode_base64(data: str, **kwargs: Any) -> str:
    """Generate a Code128 barcode and return it as a base64 data-URI.

    Accepts the same keyword arguments as :func:`generate_barcode_image`.
    """
    raw = generate_barcode_image(data, **kwargs)
    return image_to_base64(raw)


def generate_qr_base64(data: str, **kwargs: Any) -> str:
    """Generate a QR code and return it as a base64 data-URI.

    Accepts the same keyword arguments as :func:`generate_qr_image`.
    """
    raw = generate_qr_image(data, **kwargs)
    return image_to_base64(raw)


# ---------------------------------------------------------------------------
# Public API - Composite Label Builder
# ---------------------------------------------------------------------------


def generate_label_data(
    code: str,
    title: str,
    subtitle: str = "",
    info_lines: list[str] | None = None,
    verification_code: str | None = None,
) -> dict[str, Any]:
    """Build a complete label data dictionary ready for printing.

    This is the primary high-level function that assembles barcode images,
    QR code images, and all text metadata into a single dictionary that
    downstream modules (thermal printer, HTML renderer) can consume directly.

    Args:
        code: The tracking code to encode (e.g. ``LG-20260623-001``).
        title: Primary label title (e.g. ``"LUGGAGE TAG"``).
        subtitle: Secondary line (e.g. hotel name).
        info_lines: Additional information lines printed on the label.
        verification_code: Optional 4-digit pickup verification code. When
            *None*, one is generated automatically.

    Returns:
        A dictionary with the following keys:

        - ``code`` (str): The tracking code.
        - ``title`` (str): The label title.
        - ``subtitle`` (str): The subtitle.
        - ``info_lines`` (list[str]): The info lines.
        - ``verification_code`` (str): The 4-digit verification code.
        - ``barcode_image`` (bytes): Raw PNG bytes of the Code128 barcode.
        - ``barcode_base64`` (str): Base64 data-URI of the barcode.
        - ``qr_image`` (bytes): Raw PNG bytes of the QR code.
        - ``qr_base64`` (str): Base64 data-URI of the QR code.
        - ``qr_payload`` (str): The data encoded in the QR code.
        - ``created_at`` (str): ISO-8601 timestamp of generation.
    """
    if not code:
        raise ValueError("Label code must not be empty")

    info_lines = list(info_lines) if info_lines else []
    if verification_code is None:
        verification_code = generate_verification_code()

    # QR payload includes the code and verification code for self-service
    qr_payload = f"{code}|VC:{verification_code}"

    barcode_png = generate_barcode_image(code)
    qr_png = generate_qr_image(qr_payload)

    return {
        "code": code,
        "title": title,
        "subtitle": subtitle,
        "info_lines": info_lines,
        "verification_code": verification_code,
        "barcode_image": barcode_png,
        "barcode_base64": image_to_base64(barcode_png),
        "qr_image": qr_png,
        "qr_base64": image_to_base64(qr_png),
        "qr_payload": qr_payload,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
