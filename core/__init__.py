"""
Hotel Service Suite - Core Package.

Re-exports the primary configuration class for convenient access::

    from core import HotelServiceConfig

    config = HotelServiceConfig.from_yaml()
"""

from core.config import (
    BitableConfig,
    BitableTableConfig,
    FeishuBotConfig,
    HotelServiceConfig,
    PrinterSettings,
    SMSGatewayConfig,
    WeChatConfig,
)

__all__ = [
    "BitableConfig",
    "BitableTableConfig",
    "FeishuBotConfig",
    "HotelServiceConfig",
    "PrinterSettings",
    "SMSGatewayConfig",
    "WeChatConfig",
]
