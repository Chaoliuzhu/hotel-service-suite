"""
workflow — 酒店业务工作流包

提供行李寄存和遗留物品两大业务场景的完整工作流实现。

子模块:
    - luggage: 行李寄存工作流（寄存、提取、逾期检查、逾期提醒）
    - lost_found: 遗留物品工作流（登记、联系宾客、邮寄、认领、到期管理）
    - quick_snap: 随手拍 AI 拍照识别模块（照片分析、确认卡片、自动填报）
    - express_mode: 快递站模式（统一存取接口、超期催取、BOT消息处理）
"""

from workflow.luggage import (
    check_overdue,
    claim_luggage,
    deposit_luggage,
    send_overdue_alert,
)
from workflow.lost_found import (
    check_expiry,
    claim_item,
    contact_guest,
    mail_item,
    process_expired,
    register_item,
)
from workflow.quick_snap import (
    AIRecognitionResult,
    QuickSnapProcessor,
    SnapDepositRequest,
    SnapLostFoundRequest,
    create_bitable_fallback_forms,
)
from workflow.express_mode import ExpressModeProcessor

__all__ = [
    # 行李寄存
    "deposit_luggage",
    "claim_luggage",
    "check_overdue",
    "send_overdue_alert",
    # 遗留物品
    "register_item",
    "contact_guest",
    "mail_item",
    "claim_item",
    "check_expiry",
    "process_expired",
    # 随手拍
    "AIRecognitionResult",
    "QuickSnapProcessor",
    "SnapDepositRequest",
    "SnapLostFoundRequest",
    "create_bitable_fallback_forms",
    # 快递站模式
    "ExpressModeProcessor",
]
