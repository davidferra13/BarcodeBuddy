"""Barcode and QR code generation using the zxing-cpp 3.0 writer API.

This module provides functions to generate barcode and QR code images from
text values.  It leverages the same zxing-cpp library already used for reading,
using the non-deprecated ``create_barcode`` + ``write_barcode_to_image`` path.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image
import zxingcpp


def generate_barcode_image(
    text: str,
    format: str = "Code128",
    scale: int = 3,
) -> Image.Image:
    """Generate a barcode as a PIL Image.

    *format* must match a ``zxingcpp.BarcodeFormat`` attribute name
    (e.g. ``"Code128"``, ``"QRCode"``, ``"EAN13"``).
    """
    barcode_format = getattr(
        zxingcpp.BarcodeFormat, format, zxingcpp.BarcodeFormat.Code128
    )
    barcode = zxingcpp.create_barcode(text, barcode_format)
    raw_image = zxingcpp.write_barcode_to_image(
        barcode, scale=scale, add_quiet_zones=True
    )
    return Image.fromarray(np.array(raw_image))


def generate_barcode_bytes(
    text: str,
    format: str = "Code128",
    scale: int = 3,
    image_format: str = "PNG",
) -> bytes:
    """Generate a barcode and return the image as bytes."""
    image = generate_barcode_image(text, format=format, scale=scale)
    buffer = BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


def save_barcode(
    text: str,
    destination: Path,
    format: str = "Code128",
    scale: int = 3,
) -> Path:
    """Generate a barcode and save it to *destination*."""
    image = generate_barcode_image(text, format=format, scale=scale)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(destination))
    return destination


def generate_qr_code(
    text: str,
    scale: int = 10,
) -> Image.Image:
    """Generate a QR code as a PIL Image."""
    return generate_barcode_image(text, format="QRCode", scale=scale)


def generate_code128(
    text: str,
    scale: int = 3,
) -> Image.Image:
    """Generate a Code 128 barcode as a PIL Image."""
    return generate_barcode_image(text, format="Code128", scale=scale)


def list_supported_formats() -> list[str]:
    """Return the names of all barcode formats supported for writing."""
    return [
        name
        for name in dir(zxingcpp.BarcodeFormat)
        if not name.startswith("_") and name != "INVALID"
    ]
