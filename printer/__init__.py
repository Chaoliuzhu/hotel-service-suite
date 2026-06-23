"""
Hotel Service Suite - Printer Package.

Convenient re-exports for thermal label printing::

    from printer import PrinterConfig, generate_tspl_label, print_via_network

    cfg = PrinterConfig(ip="192.168.1.100", protocol="tspl")
    cmd = generate_tspl_label(
        barcode_data="LG-20260623-001",
        qr_data="LG-20260623-001|VC:4821",
        title="LUGGAGE TAG",
        lines=["Guest: Zhang Wei", "Room: 1208"],
    )
    print_via_network(cfg.ip, cfg.port, cmd)
"""

from printer.thermal import (
    PrinterConfig,
    generate_printable_html,
    generate_tspl_label,
    generate_zpl_label,
    print_via_network,
)

__all__ = [
    "PrinterConfig",
    "generate_printable_html",
    "generate_tspl_label",
    "generate_zpl_label",
    "print_via_network",
]
