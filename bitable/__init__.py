"""
bitable — 飞书多维表格客户端封装包

提供 BitableClient 类，通过 lark-cli 命令行工具对飞书多维表格进行 CRUD 操作。
"""

from bitable.client import BitableClient, BitableConfig, BitableError, BitableRetryError

__all__ = [
    "BitableClient",
    "BitableConfig",
    "BitableError",
    "BitableRetryError",
]
