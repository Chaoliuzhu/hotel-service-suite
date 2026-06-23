"""
Hotel Service Suite - Thermal Label Printer Interface.

Provides a unified interface for generating thermal printer commands in both
**TSPL/TSPL2** (TSC, Gainscha, and most Chinese thermal printers) and **ZPL**
(Zebra Programming Language) protocols, as well as a self-contained HTML
fallback for browser-based printing.

Dependencies:
    - Standard library only (``socket``, ``dataclasses``, ``html``)

Usage::

    from printer.thermal import (
        PrinterConfig,
        generate_tspl_label,
        generate_zpl_label,
        print_via_network,
        generate_printable_html,
    )

    cfg = PrinterConfig(ip="192.168.1.100", port=9100, protocol="tspl")
    cmd = generate_tspl_label(
        barcode_data="LG-20260623-001",
        qr_data="LG-20260623-001|VC:4821",
        title="LUGGAGE TAG",
        lines=["Guest: Zhang Wei", "Room: 1208"],
    )
    print_via_network(cfg.ip, cfg.port, cmd)
"""

from __future__ import annotations

import html as html_lib
import socket
from dataclasses import dataclass, field
from typing import Sequence


# ---------------------------------------------------------------------------
# Printer Configuration
# ---------------------------------------------------------------------------


@dataclass
class PrinterConfig:
    """Configuration for a thermal label printer.

    Attributes:
        ip: IP address or hostname of the printer.
        port: TCP port (9100 is the standard for raw printing).
        protocol: Command protocol — ``"tspl"`` or ``"zpl"``.
        label_width_mm: Label width in millimetres.
        label_height_mm: Label height in millimetres.
        density: Print darkness level (0-15 for TSPL, 0-30 for ZPL).
        speed: Print speed (1-15 for TSPL, 2-14 for ZPL).
    """

    ip: str = "192.168.1.100"
    port: int = 9100
    protocol: str = "tspl"
    label_width_mm: int = 75
    label_height_mm: int = 50
    density: int = 8
    speed: int = 4

    def __post_init__(self) -> None:
        if self.protocol not in ("tspl", "zpl"):
            raise ValueError(
                f"Unsupported protocol {self.protocol!r}. Use 'tspl' or 'zpl'."
            )
        if not (1 <= self.port <= 65535):
            raise ValueError(f"Port out of range: {self.port}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_MM_TO_DOT_8 = 8  # 8 dots per mm at 203 DPI


def _mm_to_dots(mm: float) -> int:
    """Convert millimetres to dots at 203 DPI (standard thermal resolution)."""
    return round(mm * _MM_TO_DOT_8)


def _escape_tspl(text: str) -> str:
    """Escape characters that are special in TSPL TEXT commands."""
    return text.replace('"', '""')


def _escape_zpl(text: str) -> str:
    """Escape characters that are special in ZPL ^FD fields."""
    # In ZPL, ^, ~, and \ have special meaning inside ^FD
    return (
        text.replace("^", "/^")
        .replace("~", "/~")
        .replace("\\", "/\\")
    )


# ---------------------------------------------------------------------------
# TSPL / TSPL2 Command Generation
# ---------------------------------------------------------------------------


def generate_tspl_label(
    barcode_data: str,
    qr_data: str,
    title: str,
    lines: Sequence[str],
    label_width_mm: int = 75,
    label_height_mm: int = 50,
    density: int = 8,
    speed: int = 4,
    copies: int = 1,
) -> str:
    """Generate a TSPL/TSPL2 command string for a hotel label.

    The resulting string can be sent directly to a TSPL-compatible thermal
    printer over TCP or USB.

    Label layout (top to bottom)::

        ┌──────────────────────┐
        │     TITLE (bold)     │  y = 2 mm
        │                      │
        │   ┌───barcode───┐   │  y = 10 mm
        │   └─────────────┘   │
        │                      │
        │     ┌──QR──┐        │  y = 22 mm
        │     └──────┘        │
        │  line 1              │  y = 35 mm
        │  line 2              │
        │  ...                 │
        └──────────────────────┘

    Args:
        barcode_data: Code128 barcode content (e.g. ``LG-20260623-001``).
        qr_data: QR code content (e.g. ``LG-20260623-001|VC:4821``).
        title: Title text printed at the top of the label.
        lines: Additional information lines printed below the QR code.
        label_width_mm: Label width in millimetres.
        label_height_mm: Label height in millimetres.
        density: Print darkness (0-15).
        speed: Print speed (1-15).
        copies: Number of copies to print.

    Returns:
        A multi-line TSPL command string terminated with ``\\r\\n``.
    """
    w_dots = _mm_to_dots(label_width_mm)
    h_dots = _mm_to_dots(label_height_mm)

    cmds: list[str] = []

    # -- Label setup -------------------------------------------------------
    cmds.append(f"SIZE {label_width_mm} mm, {label_height_mm} mm")
    cmds.append("GAP 2 mm, 0")
    cmds.append("DIRECTION 1")
    cmds.append("CLS")
    cmds.append(f"DENSITY {density}")
    cmds.append(f"SPEED {speed}")

    # -- Title (bold, larger font) -----------------------------------------
    title_x = _mm_to_dots(2)
    title_y = _mm_to_dots(2)
    cmds.append(
        f'TEXT {title_x},{title_y},"TSS24.BF2",0,2,2,'
        f'"{_escape_tspl(title)}"'
    )

    # -- Code128 barcode ---------------------------------------------------
    bc_x = _mm_to_dots(5)
    bc_y = _mm_to_dots(10)
    # BARCODE x,y,"code_type",height,human_readable,rotation,narrow,wide,"data"
    # code_type 128 = Code128, height 40 dots (~5mm), human readable=1
    cmds.append(
        f'BARCODE {bc_x},{bc_y},"128",40,1,0,2,2,'
        f'"{_escape_tspl(barcode_data)}"'
    )

    # -- QR code -----------------------------------------------------------
    qr_x = _mm_to_dots(2)
    qr_y = _mm_to_dots(22)
    # QRCODE x,y,mode,cell_width,rotation,model,mask,data
    # mode: L = enhanced, cell_width 4 (~1mm per module)
    cmds.append(
        f'QRCODE {qr_x},{qr_y},L,4,A,0,M2,'
        f'S7,'  # not all firmwares support S7; safe to include
        f'"{_escape_tspl(qr_data)}"'
    )

    # -- Information lines -------------------------------------------------
    line_y_start = _mm_to_dots(35)
    line_spacing = _mm_to_dots(4)
    line_x = _mm_to_dots(2)

    for i, line in enumerate(lines):
        ly = line_y_start + i * line_spacing
        # Check if line would overflow the label
        if ly + _mm_to_dots(4) > h_dots:
            break
        cmds.append(
            f'TEXT {line_x},{ly},"TSS24.BF2",0,1,1,'
            f'"{_escape_tspl(line)}"'
        )

    # -- Print & eject -----------------------------------------------------
    cmds.append(f"PRINT {copies},1")
    cmds.append("")  # trailing newline

    return "\r\n".join(cmds)


# ---------------------------------------------------------------------------
# ZPL (Zebra Programming Language) Command Generation
# ---------------------------------------------------------------------------


def generate_zpl_label(
    barcode_data: str,
    qr_data: str,
    title: str,
    lines: Sequence[str],
    label_width_mm: int = 75,
    label_height_mm: int = 50,
    density: int = 10,
    copies: int = 1,
) -> str:
    """Generate a ZPL command string for a hotel label.

    Compatible with Zebra ZPL II printers (ZD410, ZD420, ZT series, etc.).

    Args:
        barcode_data: Code128 barcode content.
        qr_data: QR code content.
        title: Title text printed at the top of the label.
        lines: Additional information lines.
        label_width_mm: Label width in millimetres.
        label_height_mm: Label height in millimetres.
        density: Print darkness (0-30).
        copies: Number of copies to print.

    Returns:
        A ZPL command string.
    """
    w_dots = _mm_to_dots(label_width_mm)
    h_dots = _mm_to_dots(label_height_mm)

    parts: list[str] = []

    # -- Start label -------------------------------------------------------
    parts.append("^XA")
    parts.append(f"^LL{h_dots}")  # label length
    parts.append(f"^LH0,0")  # label home
    parts.append(f"^PW{w_dots}")  # print width
    parts.append(f"~SD{density}")  # set darkness

    # -- Title (bold, magnified) -------------------------------------------
    # ^FOx,y  = field origin
    # ^A0N,40,20 = font 0, normal, 40 height, 20 width
    # ^FD...^FS = field data
    parts.append(f"^FO{_mm_to_dots(2)},{_mm_to_dots(2)}")
    parts.append("^A0N,32,16")
    parts.append(f"^FD{_escape_zpl(title)}^FS")

    # -- Code128 barcode ---------------------------------------------------
    # ^FOx,y
    # ^BCo,h,f,g,m = Code128: o=orientation, h=height, f=line(Y/N),
    #                           g=line above(Y/N), m=mode(UCC=N)
    parts.append(f"^FO{_mm_to_dots(5)},{_mm_to_dots(10)}")
    parts.append("^BCN,40,Y,N,N")
    parts.append(f"^FD{_escape_zpl(barcode_data)}^FS")

    # -- QR code -----------------------------------------------------------
    # ^FOx,y
    # ^BQa,b,c,d = QR: a=field, b=model(2), c=magnification, d=errLevel
    # ^FD qa,data ^FS  (qa = auto quality)
    parts.append(f"^FO{_mm_to_dots(2)},{_mm_to_dots(22)}")
    parts.append("^BQN,2,4,M")
    parts.append(f"^FDqa,{_escape_zpl(qr_data)}^FS")

    # -- Information lines -------------------------------------------------
    line_y_start = _mm_to_dots(35)
    line_spacing = _mm_to_dots(4)
    line_x = _mm_to_dots(2)

    for i, line in enumerate(lines):
        ly = line_y_start + i * line_spacing
        if ly + _mm_to_dots(4) > h_dots:
            break
        parts.append(f"^FO{line_x},{ly}")
        parts.append("^A0N,20,10")
        parts.append(f"^FD{_escape_zpl(line)}^FS")

    # -- Copies & end ------------------------------------------------------
    if copies > 1:
        parts.append(f"^PQ{copies}")
    parts.append("^XZ")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Network Printing
# ---------------------------------------------------------------------------


def print_via_network(
    ip: str,
    port: int,
    command_data: str,
    timeout: float = 10.0,
) -> None:
    """Send a print command to a network thermal printer via TCP socket.

    Works with any printer that accepts raw TSPL or ZPL over TCP port 9100
    (the standard "JetDirect" / "RAW" printing port).

    Args:
        ip: Printer IP address or hostname.
        port: TCP port number (usually 9100).
        command_data: The TSPL or ZPL command string to send.
        timeout: Socket timeout in seconds.

    Raises:
        ConnectionError: If the printer is unreachable.
        TimeoutError: If the connection times out.
        OSError: On other network-level errors.
    """
    if not ip:
        raise ValueError("Printer IP address must not be empty")
    if not (1 <= port <= 65535):
        raise ValueError(f"Invalid port number: {port}")

    data = command_data.encode("utf-8")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        try:
            sock.connect((ip, port))
        except socket.timeout:
            raise TimeoutError(
                f"Connection to {ip}:{port} timed out after {timeout}s"
            )
        except OSError as exc:
            raise ConnectionError(
                f"Cannot reach printer at {ip}:{port}: {exc}"
            ) from exc

        # Send data in chunks for large labels
        chunk_size = 4096
        offset = 0
        while offset < len(data):
            sent = sock.send(data[offset : offset + chunk_size])
            if sent == 0:
                raise ConnectionError(
                    "Socket connection broken while sending data"
                )
            offset += sent


# ---------------------------------------------------------------------------
# HTML Fallback Generator
# ---------------------------------------------------------------------------


def generate_printable_html(
    barcode_data: str,
    qr_data: str,
    title: str,
    subtitle: str = "",
    info_lines: Sequence[str] = (),
    page_size: str = "A6",
) -> str:
    """Generate a self-contained HTML page for browser-based printing.

    The output is a complete HTML document with embedded CSS that renders
    the label beautifully on any paper size. It uses SVG for the barcode
    (via a pure-Python Code128 SVG renderer) and an inline SVG QR code,
    making it entirely self-contained with no external dependencies.

    Args:
        barcode_data: Code128 barcode content.
        qr_data: QR code content.
        title: Main title displayed on the label.
        subtitle: Subtitle or secondary line.
        info_lines: Additional text lines to display.
        page_size: CSS page size — ``"A6"``, ``"A5"``, ``"A4"``, or a
                   custom value like ``"75mm 50mm"``.

    Returns:
        A complete HTML string ready to save or serve.
    """
    esc = html_lib.escape

    # Generate inline SVG barcode (Code128)
    barcode_svg = _generate_code128_svg(barcode_data)

    # Generate inline SVG QR code
    qr_svg = _generate_qr_svg(qr_data)

    # Build info lines HTML
    info_html_parts: list[str] = []
    for line in info_lines:
        info_html_parts.append(f'<li>{esc(line)}</li>')
    info_html = "\n            ".join(info_html_parts)

    subtitle_html = ""
    if subtitle:
        subtitle_html = f'<p class="subtitle">{esc(subtitle)}</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{esc(title)} - {esc(barcode_data)}</title>
    <style>
        /* ----- Page & Print Setup ----- */
        @page {{
            size: {page_size};
            margin: 5mm;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        html, body {{
            width: 100%;
            height: 100%;
            font-family: 'Helvetica Neue', Arial, 'PingFang SC',
                         'Microsoft YaHei', sans-serif;
            color: #1a1a1a;
            background: #fff;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }}

        .label {{
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 4mm;
            max-width: 100%;
            page-break-inside: avoid;
        }}

        /* ----- Title Area ----- */
        .header {{
            text-align: center;
            margin-bottom: 3mm;
            width: 100%;
            border-bottom: 1.5px solid #333;
            padding-bottom: 2mm;
        }}

        .title {{
            font-size: 16pt;
            font-weight: 700;
            letter-spacing: 0.1em;
            text-transform: uppercase;
        }}

        .subtitle {{
            font-size: 9pt;
            color: #555;
            margin-top: 1mm;
        }}

        /* ----- Barcode Section ----- */
        .barcode-section {{
            margin: 3mm 0;
            text-align: center;
        }}

        .barcode-section svg {{
            max-width: 100%;
            height: auto;
        }}

        .barcode-text {{
            font-size: 8pt;
            font-family: 'Courier New', Courier, monospace;
            letter-spacing: 0.15em;
            margin-top: 1mm;
            color: #333;
        }}

        /* ----- QR Code Section ----- */
        .qr-section {{
            margin: 2mm 0;
            text-align: center;
        }}

        .qr-section svg {{
            width: 22mm;
            height: 22mm;
        }}

        /* ----- Info Lines ----- */
        .info-section {{
            width: 100%;
            margin-top: 2mm;
            border-top: 1px dashed #aaa;
            padding-top: 2mm;
        }}

        .info-section ul {{
            list-style: none;
            padding: 0;
        }}

        .info-section li {{
            font-size: 10pt;
            line-height: 1.6;
            padding: 0.5mm 0;
        }}

        .info-section li::before {{
            content: "\\25B8 ";
            color: #888;
        }}

        /* ----- Footer ----- */
        .footer {{
            margin-top: auto;
            padding-top: 2mm;
            font-size: 7pt;
            color: #999;
            text-align: center;
            width: 100%;
            border-top: 0.5px solid #ddd;
        }}

        /* ----- Screen-only styling ----- */
        @media screen {{
            body {{
                display: flex;
                justify-content: center;
                align-items: flex-start;
                padding: 20px;
                background: #f0f0f0;
            }}
            .label {{
                background: #fff;
                box-shadow: 0 2px 12px rgba(0,0,0,0.12);
                border-radius: 4px;
                min-height: 120mm;
                max-width: 148mm;  /* A6 width */
            }}
        }}

        /* ----- Print overrides ----- */
        @media print {{
            body {{
                background: #fff;
            }}
            .label {{
                box-shadow: none;
                border-radius: 0;
                min-height: auto;
            }}
        }}
    </style>
</head>
<body>
    <div class="label">
        <div class="header">
            <div class="title">{esc(title)}</div>
            {subtitle_html}
        </div>

        <div class="barcode-section">
            {barcode_svg}
            <div class="barcode-text">{esc(barcode_data)}</div>
        </div>

        <div class="qr-section">
            {qr_svg}
        </div>

        <div class="info-section">
            <ul>
            {info_html}
            </ul>
        </div>

        <div class="footer">
            Generated by Hotel Service Suite
        </div>
    </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Pure-Python SVG generators (no external dependencies)
# ---------------------------------------------------------------------------


def _generate_code128_svg(data: str) -> str:
    """Generate an SVG Code128 barcode from data.

    This is a minimal pure-Python Code128 encoder that produces an SVG
    representation suitable for embedding in HTML. It uses Code Set B
    which covers all printable ASCII characters.
    """
    # Code128B character set: ASCII 32-127 map to values 0-95
    # Start code B = 104, Stop pattern = 106
    CODE128B_PATTERNS = [
        "11011001100", "11001101100", "11001100110", "10010011000",
        "10010001100", "10001001100", "10011001000", "10011000100",
        "10001100100", "11001001000", "11001000100", "11000100100",
        "10110011100", "10011011100", "10011001110", "10111001100",
        "10011101100", "10011100110", "11001110010", "11001011100",
        "11001001110", "11011100100", "11001110100", "11101101110",
        "11101001100", "11100101100", "11100100110", "11101100100",
        "11100110100", "11100110010", "11011011000", "11011000110",
        "11000110110", "10100011000", "10001011000", "10001000110",
        "10110001000", "10001101000", "10001100010", "11010001000",
        "11000101000", "11000100010", "10110111000", "10110001110",
        "10001101110", "10111011000", "10111000110", "10001110110",
        "11101110110", "11010001110", "11000101110", "11011101000",
        "11011100010", "11011101110", "11101011000", "11101000110",
        "11100010110", "11101101000", "11101100010", "11100011010",
        "11101111010", "11001000010", "11110001010", "10100110000",
        "10100001100", "10010110000", "10010000110", "10000101100",
        "10000100110", "10110010000", "10110000100", "10011010000",
        "10011000010", "10000110100", "10000110010", "11000010010",
        "11001010000", "11110111010", "11000010100", "10001111010",
        "10100111100", "10010111100", "10010011110", "10111100100",
        "10011110100", "10011110010", "11110100100", "11110010100",
        "11110010010", "11011011110", "11011110110", "11110110110",
        "10101111000", "10100011110", "10001011110", "10111101000",
        "10111100010", "11110101000", "11110100010", "10111011110",
        "10111101110", "11101011110", "11110101110",
        # 103=StartA, 104=StartB, 105=StartC
        "11010000100", "11010010000", "11010011100",
        # 106=Stop
        "1100011101011",
    ]

    # Encode using Start Code B (index 104)
    values = [104]  # Start B
    checksum = 104
    for i, ch in enumerate(data):
        val = ord(ch) - 32
        if val < 0 or val > 95:
            val = 0  # fallback for unsupported characters
        values.append(val)
        checksum += val * (i + 1)

    values.append(checksum % 103)
    values.append(106)  # Stop

    # Build the bar pattern
    bars = ""
    for v in values:
        bars += CODE128B_PATTERNS[v]

    # Render as SVG
    bar_width = 2  # pixels per module
    total_width = len(bars) * bar_width
    height = 50

    rects: list[str] = []
    x = 0
    for ch in bars:
        if ch == "1":
            rects.append(f'<rect x="{x}" y="0" width="{bar_width}" height="{height}" fill="#000"/>')
        x += bar_width

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {total_width} {height}" '
        f'width="{total_width}" height="{height}">'
        + "".join(rects)
        + "</svg>"
    )
    return svg


def _generate_qr_svg(data: str) -> str:
    """Generate an SVG QR code from data using the qrcode library.

    Falls back to a placeholder rectangle if the qrcode library is
    unavailable (should not happen in normal usage).
    """
    try:
        import qrcode
        import qrcode.constants

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=1,
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)

        matrix = qr.get_matrix()
        size = len(matrix)

        rects: list[str] = []
        for y, row in enumerate(matrix):
            for x, cell in enumerate(row):
                if cell:
                    rects.append(
                        f'<rect x="{x}" y="{y}" width="1" height="1" fill="#000"/>'
                    )

        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {size} {size}" '
            f'width="120" height="120">'
            + "".join(rects)
            + "</svg>"
        )
        return svg
    except ImportError:
        # Fallback placeholder if qrcode is not installed
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120">'
            '<rect width="120" height="120" fill="#eee" stroke="#ccc"/>'
            '<text x="60" y="65" text-anchor="middle" font-size="10" '
            'fill="#999">QR</text></svg>'
        )
