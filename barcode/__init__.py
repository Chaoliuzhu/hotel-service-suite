"""
Hotel Service Suite - Barcode Package.

Convenient re-exports for barcode and QR code generation::

    from barcode import generate_luggage_code, generate_label_data

    code = generate_luggage_code(seq=1)
    label = generate_label_data(code=code, title="LUGGAGE TAG")
"""

from barcode.generator import (
    generate_barcode_base64,
    generate_barcode_image,
    generate_label_data,
    generate_lost_found_code,
    generate_luggage_code,
    generate_qr_base64,
    generate_qr_image,
    generate_verification_code,
    image_to_base64,
    reset_sequences,
)

__all__ = [
    "generate_barcode_base64",
    "generate_barcode_image",
    "generate_label_data",
    "generate_lost_found_code",
    "generate_luggage_code",
    "generate_qr_base64",
    "generate_qr_image",
    "generate_verification_code",
    "image_to_base64",
    "reset_sequences",
]
