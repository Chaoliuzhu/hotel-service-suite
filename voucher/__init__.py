"""
voucher — 酒店电子凭证包

提供行李寄存凭证和遗留物品凭证的多渠道渲染能力。

主要导出:
    - LuggageVoucherData: 行李寄存凭证数据模型
    - LostFoundVoucherData: 遗留物品凭证数据模型
    - LuggageVoucherRenderer: 行李寄存凭证渲染器
    - LostFoundVoucherRenderer: 遗留物品凭证渲染器
    - render_luggage_voucher(): 一站式行李凭证渲染函数
    - render_lost_found_voucher(): 一站式遗留物品凭证渲染函数
"""

from voucher.engine import (
    LostFoundVoucherData,
    LostFoundVoucherRenderer,
    LuggageVoucherData,
    LuggageVoucherRenderer,
    generate_barcode_data,
    generate_qr_data,
    generate_verification_code,
    render_lost_found_voucher,
    render_luggage_voucher,
)

__all__ = [
    "LuggageVoucherData",
    "LuggageVoucherRenderer",
    "LostFoundVoucherData",
    "LostFoundVoucherRenderer",
    "render_luggage_voucher",
    "render_lost_found_voucher",
    "generate_barcode_data",
    "generate_qr_data",
    "generate_verification_code",
]
