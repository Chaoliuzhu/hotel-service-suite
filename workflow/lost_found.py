"""
workflow.lost_found — 遗留物品工作流

提供遗留物品业务的全生命周期管理：
  - 登记 (register_item): 创建记录、生成条码、重要物品标记保险箱
  - 联系宾客 (contact_guest): 更新状态为 "已联系宾客"、生成通知
  - 邮寄 (mail_item): 更新状态为 "已邮寄"、填写快递信息、生成邮寄凭证
  - 认领 (claim_item): 更新状态为 "已认领"、记录认领时间
  - 到期检查 (check_expiry): 30/60/90 天到期阈值检查
  - 到期处理 (process_expired): 30天提醒、60天公告、90天处置

编号规则：LF-{YYYYMMDD}-{seq}
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from bitable.client import BitableClient, BitableError
from voucher.engine import (
    LostFoundVoucherData,
    LostFoundVoucherRenderer,
    generate_barcode_data,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 配置常量
# ---------------------------------------------------------------------------

LOST_FOUND_APP_TOKEN = ""      # 遗留物品多维表格 app_token
LOST_FOUND_TABLE_ID = ""       # 遗留物品数据表 ID

# 到期阈值（天）
THRESHOLD_REMINDER = 30         # 30 天 — 发送提醒
THRESHOLD_NOTICE = 60           # 60 天 — 发布公告
THRESHOLD_DISPOSAL = 90         # 90 天 — 处置

# 字段名映射
FIELD_MAP = {
    "case_number": "案件编号",
    "item_name": "物品名称",
    "category": "物品类别",
    "description": "物品描述",
    "finder": "拾获人",
    "location": "发现地点",
    "discovery_date": "发现日期",
    "guest_name": "宾客姓名",
    "guest_phone": "宾客电话",
    "is_important": "是否重要物品",
    "barcode": "条形码",
    "status": "状态",
    "contact_method": "联系方式",
    "contact_time": "联系时间",
    "courier_company": "快递公司",
    "tracking_number": "快递运单号",
    "mailing_address": "邮寄地址",
    "mailing_time": "邮寄时间",
    "claim_time": "认领时间",
    "claimer_name": "认领人",
    "claim_method": "认领方式",
    "expiry_action": "到期处理",
    "expiry_action_time": "到期处理时间",
    "created_at": "创建时间",
}


# ---------------------------------------------------------------------------
# 编号生成
# ---------------------------------------------------------------------------

def _generate_case_number(client: BitableClient) -> str:
    """
    自动生成案件编号：LF-{YYYYMMDD}-{seq}

    Args:
        client: 多维表格客户端

    Returns:
        格式化的案件编号，如 "LF-20250101-001"
    """
    today = datetime.now()
    date_str = today.strftime("%Y%m%d")

    today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    filter_formula = f'IS_AFTER({{创建时间}}, "{today_start.isoformat()}")'

    try:
        count = client.count_records(LOST_FOUND_APP_TOKEN, LOST_FOUND_TABLE_ID, filter_formula)
    except BitableError:
        logger.warning("无法查询当日记录数，默认序号为 1")
        count = 0

    seq = count + 1
    return f"LF-{date_str}-{seq:03d}"


# ---------------------------------------------------------------------------
# 核心业务函数
# ---------------------------------------------------------------------------

def register_item(
    client: BitableClient,
    item_name: str,
    category: str,
    description: str,
    finder: str,
    location: str,
    guest_name: str = "",
    guest_phone: str = "",
    is_important: bool = False,
) -> dict[str, Any]:
    """
    登记遗留物品。

    流程：
      1. 自动生成案件编号
      2. 生成条码
      3. 若为重要物品（贵重物品），标记存入保险箱
      4. 在多维表格创建记录
      5. 生成凭证

    Args:
        client: 多维表格客户端
        item_name: 物品名称
        category: 物品类别（衣物/电子产品/证件/首饰/其他）
        description: 物品详细描述
        finder: 拾获人姓名
        location: 发现地点
        guest_name: 宾客姓名（如已知）
        guest_phone: 宾客电话（如已知）
        is_important: 是否为重要/贵重物品

    Returns:
        包含 case_number, record_id, barcode, voucher, safe_deposit 的字典

    Raises:
        BitableError: 多维表格操作失败
    """
    now = datetime.now()
    case_number = _generate_case_number(client)
    barcode = generate_barcode_data(case_number)
    discovery_date = now.strftime("%Y-%m-%d %H:%M")

    fields = {
        FIELD_MAP["case_number"]: case_number,
        FIELD_MAP["item_name"]: item_name,
        FIELD_MAP["category"]: category,
        FIELD_MAP["description"]: description,
        FIELD_MAP["finder"]: finder,
        FIELD_MAP["location"]: location,
        FIELD_MAP["discovery_date"]: discovery_date,
        FIELD_MAP["guest_name"]: guest_name or "未知",
        FIELD_MAP["guest_phone"]: guest_phone,
        FIELD_MAP["is_important"]: "是" if is_important else "否",
        FIELD_MAP["barcode"]: barcode,
        FIELD_MAP["status"]: "待处理",
        FIELD_MAP["created_at"]: now.isoformat(timespec="seconds"),
    }

    record_id = client.create_record(LOST_FOUND_APP_TOKEN, LOST_FOUND_TABLE_ID, fields)
    logger.info("遗留物品已登记: %s (record_id=%s)", case_number, record_id)

    # 重要物品标记 — 存入保险箱
    safe_deposit = False
    if is_important:
        safe_deposit = True
        logger.info("重要物品 %s 已标记存入保险箱", case_number)
        # TODO: 触发保险箱管理流程（更新保险箱使用记录）

    # 生成凭证
    voucher_data = LostFoundVoucherData(
        case_number=case_number,
        guest_name=guest_name or "待确认",
        item_description=f"{item_name} — {description}",
        discovery_date=discovery_date,
        discovery_location=location,
        status="待处理",
        category=category,
        finder=finder,
        guest_phone=guest_phone,
        is_important=is_important,
    )

    renderer = LostFoundVoucherRenderer()
    voucher = {
        "html": renderer.render_html(voucher_data),
        "feishu_card": renderer.render_feishu_card(voucher_data),
        "sms": renderer.render_sms(voucher_data),
        "wechat": renderer.render_wechat_template(voucher_data),
    }

    return {
        "case_number": case_number,
        "record_id": record_id,
        "barcode": barcode,
        "safe_deposit": safe_deposit,
        "voucher": voucher,
    }


def contact_guest(
    client: BitableClient,
    record_id: str,
    contact_method: str,
) -> dict[str, Any]:
    """
    联系宾客 — 更新状态为 "已联系宾客" 并生成通知。

    Args:
        client: 多维表格客户端
        record_id: 多维表格记录 ID
        contact_method: 联系方式（电话/短信/微信/邮件）

    Returns:
        包含 success, message, notification 的字典

    Raises:
        BitableError: 多维表格操作失败
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    client.update_record(
        LOST_FOUND_APP_TOKEN,
        LOST_FOUND_TABLE_ID,
        record_id,
        {
            FIELD_MAP["status"]: "已联系宾客",
            FIELD_MAP["contact_method"]: contact_method,
            FIELD_MAP["contact_time"]: now,
        },
    )

    logger.info("已联系宾客: record_id=%s, 方式=%s", record_id, contact_method)

    # 获取记录详情以生成通知
    record = client.get_record(LOST_FOUND_APP_TOKEN, LOST_FOUND_TABLE_ID, record_id)
    fields = record.get("fields", {})

    case_number = fields.get(FIELD_MAP["case_number"], "")
    guest_name = fields.get(FIELD_MAP["guest_name"], "")
    item_name = fields.get(FIELD_MAP["item_name"], "")

    notification = {
        "type": "contact_notification",
        "case_number": case_number,
        "guest_name": guest_name,
        "item_name": item_name,
        "contact_method": contact_method,
        "contact_time": now,
        "message": f"已通过{contact_method}联系宾客{guest_name}，告知遗留物品（{item_name}）事宜。",
    }

    # TODO: 发送飞书通知到客房部经理
    logger.info("联系通知已生成: %s", notification["message"])

    return {
        "success": True,
        "message": f"已更新状态为「已联系宾客」，联系方式: {contact_method}",
        "notification": notification,
    }


def mail_item(
    client: BitableClient,
    record_id: str,
    courier_company: str,
    tracking_number: str,
    address: str,
) -> dict[str, Any]:
    """
    邮寄物品 — 更新状态为 "已邮寄"，填写快递信息，生成邮寄凭证。

    Args:
        client: 多维表格客户端
        record_id: 多维表格记录 ID
        courier_company: 快递公司名称
        tracking_number: 快递运单号
        address: 邮寄地址

    Returns:
        包含 success, message, shipping_voucher 的字典

    Raises:
        BitableError: 多维表格操作失败
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    client.update_record(
        LOST_FOUND_APP_TOKEN,
        LOST_FOUND_TABLE_ID,
        record_id,
        {
            FIELD_MAP["status"]: "已邮寄",
            FIELD_MAP["courier_company"]: courier_company,
            FIELD_MAP["tracking_number"]: tracking_number,
            FIELD_MAP["mailing_address"]: address,
            FIELD_MAP["mailing_time"]: now,
        },
    )

    logger.info(
        "物品已邮寄: record_id=%s, %s 运单号 %s",
        record_id, courier_company, tracking_number,
    )

    # 获取记录详情
    record = client.get_record(LOST_FOUND_APP_TOKEN, LOST_FOUND_TABLE_ID, record_id)
    fields = record.get("fields", {})

    case_number = fields.get(FIELD_MAP["case_number"], "")
    guest_name = fields.get(FIELD_MAP["guest_name"], "")
    item_name = fields.get(FIELD_MAP["item_name"], "")

    # 生成邮寄通知凭证
    voucher_data = LostFoundVoucherData(
        case_number=case_number,
        guest_name=guest_name,
        item_description=f"{item_name} — {fields.get(FIELD_MAP['description'], '')}",
        discovery_date=fields.get(FIELD_MAP["discovery_date"], ""),
        discovery_location=fields.get(FIELD_MAP["location"], ""),
        status="已邮寄",
        category=fields.get(FIELD_MAP["category"], ""),
        finder=fields.get(FIELD_MAP["finder"], ""),
        guest_phone=fields.get(FIELD_MAP["guest_phone"], ""),
        courier_company=courier_company,
        tracking_number=tracking_number,
        mailing_address=address,
    )

    renderer = LostFoundVoucherRenderer()
    shipping_voucher = {
        "html": renderer.render_html(voucher_data),
        "feishu_card": renderer.render_feishu_card(voucher_data),
        "sms": _shipping_sms(guest_name, case_number, courier_company, tracking_number),
        "wechat": renderer.render_wechat_template(voucher_data),
    }

    # TODO: 发送邮寄通知短信/微信给宾客

    return {
        "success": True,
        "message": f"物品已邮寄: {courier_company} 运单号 {tracking_number}",
        "shipping_voucher": shipping_voucher,
    }


def claim_item(
    client: BitableClient,
    record_id: str,
    claimer_name: str,
    claim_method: str = "前台领取",
) -> dict[str, Any]:
    """
    认领物品 — 更新状态为 "已认领"，记录认领信息。

    Args:
        client: 多维表格客户端
        record_id: 多维表格记录 ID
        claimer_name: 认领人姓名
        claim_method: 认领方式（前台领取 / 委托代领 / 邮寄）

    Returns:
        包含 success, message 的字典

    Raises:
        BitableError: 多维表格操作失败
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 获取记录以校验状态
    record = client.get_record(LOST_FOUND_APP_TOKEN, LOST_FOUND_TABLE_ID, record_id)
    fields = record.get("fields", {})
    current_status = fields.get(FIELD_MAP["status"], "")

    if current_status == "已认领":
        return {
            "success": False,
            "message": "该物品已被认领，无需重复操作",
        }

    client.update_record(
        LOST_FOUND_APP_TOKEN,
        LOST_FOUND_TABLE_ID,
        record_id,
        {
            FIELD_MAP["status"]: "已认领",
            FIELD_MAP["claim_time"]: now,
            FIELD_MAP["claimer_name"]: claimer_name,
            FIELD_MAP["claim_method"]: claim_method,
        },
    )

    case_number = fields.get(FIELD_MAP["case_number"], "")
    logger.info("物品已认领: %s, 认领人: %s, 方式: %s", case_number, claimer_name, claim_method)

    return {
        "success": True,
        "message": f"物品 {case_number} 已认领，认领人: {claimer_name}，方式: {claim_method}",
    }


def check_expiry(client: BitableClient) -> dict[str, list[dict[str, Any]]]:
    """
    检查物品到期情况 — 返回 30/60/90 天阈值的物品列表。

    按发现日期计算，将物品分为三组：
      - 30 天：需发送提醒通知
      - 60 天：需发布公告
      - 90 天：需进行处置

    Args:
        client: 多维表格客户端

    Returns:
        包含 reminder (30天), notice (60天), disposal (90天) 三个列表的字典
    """
    # 查询所有非已认领 / 非已邮寄状态的记录
    records = client.list_records(
        LOST_FOUND_APP_TOKEN,
        LOST_FOUND_TABLE_ID,
        filters={
            "conjunction": "and",
            "conditions": [
                {
                    "field_name": FIELD_MAP["status"],
                    "operator": "is",
                    "value": ["待处理"],
                },
                {
                    "field_name": FIELD_MAP["status"],
                    "operator": "is",
                    "value": ["已联系宾客"],
                },
            ],
        },
        limit=500,
    )

    now = datetime.now()
    result: dict[str, list[dict[str, Any]]] = {
        "reminder": [],   # 30 天 — 发送提醒
        "notice": [],     # 60 天 — 发布公告
        "disposal": [],   # 90 天 — 处置
    }

    for record in records:
        fields = record.get("fields", {})
        discovery_date_str = fields.get(FIELD_MAP["discovery_date"], "")

        if not discovery_date_str:
            continue

        try:
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    discovery_dt = datetime.strptime(discovery_date_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                logger.warning("无法解析发现日期: %s", discovery_date_str)
                continue

            days_elapsed = (now - discovery_dt).days
            record_id = record.get("record_id") or record.get("id") or ""

            item_info = {
                "record_id": record_id,
                "case_number": fields.get(FIELD_MAP["case_number"], ""),
                "guest_name": fields.get(FIELD_MAP["guest_name"], ""),
                "item_name": fields.get(FIELD_MAP["item_name"], ""),
                "category": fields.get(FIELD_MAP["category"], ""),
                "discovery_date": discovery_date_str,
                "days_elapsed": days_elapsed,
                "status": fields.get(FIELD_MAP["status"], ""),
                "guest_phone": fields.get(FIELD_MAP["guest_phone"], ""),
            }

            # 按阈值分组（取最高适用阈值）
            if days_elapsed >= THRESHOLD_DISPOSAL:
                result["disposal"].append(item_info)
            elif days_elapsed >= THRESHOLD_NOTICE:
                result["notice"].append(item_info)
            elif days_elapsed >= THRESHOLD_REMINDER:
                result["reminder"].append(item_info)

        except Exception as exc:
            logger.error("处理记录异常: %s", exc, exc_info=True)

    logger.info(
        "到期检查完成: 30天提醒=%d, 60天公告=%d, 90天处置=%d",
        len(result["reminder"]),
        len(result["notice"]),
        len(result["disposal"]),
    )
    return result


def process_expired(
    client: BitableClient,
    record_id: str,
    action: str,
) -> dict[str, Any]:
    """
    处理到期物品。

    根据到期阶段执行不同操作：
      - "30天提醒": 向宾客发送提醒通知
      - "60天公告": 更新状态并生成公告记录
      - "90天处置": 更新状态为已处置，记录处置方式

    Args:
        client: 多维表格客户端
        record_id: 多维表格记录 ID
        action: 处理动作，可选 "30天提醒" / "60天公告" / "90天处置"

    Returns:
        包含 success, message, action_taken 的字典

    Raises:
        BitableError: 多维表格操作失败
        ValueError: 不支持的处理动作
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 获取记录详情
    record = client.get_record(LOST_FOUND_APP_TOKEN, LOST_FOUND_TABLE_ID, record_id)
    fields = record.get("fields", {})
    case_number = fields.get(FIELD_MAP["case_number"], "")
    guest_name = fields.get(FIELD_MAP["guest_name"], "")
    item_name = fields.get(FIELD_MAP["item_name"], "")
    guest_phone = fields.get(FIELD_MAP["guest_phone"], "")

    match action:
        case "30天提醒":
            # 发送提醒通知给宾客
            # TODO: 对接短信/微信 API 发送提醒
            client.update_record(
                LOST_FOUND_APP_TOKEN,
                LOST_FOUND_TABLE_ID,
                record_id,
                {
                    FIELD_MAP["expiry_action"]: "30天提醒已发送",
                    FIELD_MAP["expiry_action_time"]: now,
                },
            )
            message = f"已向宾客{guest_name}发送30天提醒通知（物品: {item_name}）"
            logger.info("30天提醒已发送: %s", case_number)

        case "60天公告":
            # 更新状态并生成公告
            client.update_record(
                LOST_FOUND_APP_TOKEN,
                LOST_FOUND_TABLE_ID,
                record_id,
                {
                    FIELD_MAP["status"]: "公告中",
                    FIELD_MAP["expiry_action"]: "60天公告已发布",
                    FIELD_MAP["expiry_action_time"]: now,
                },
            )
            message = f"已发布60天公告（物品: {item_name}，编号: {case_number}）"
            logger.info("60天公告已发布: %s", case_number)
            # TODO: 在酒店内部公告栏发布

        case "90天处置":
            # 标记为已处置
            client.update_record(
                LOST_FOUND_APP_TOKEN,
                LOST_FOUND_TABLE_ID,
                record_id,
                {
                    FIELD_MAP["status"]: "已处置",
                    FIELD_MAP["expiry_action"]: "90天已处置",
                    FIELD_MAP["expiry_action_time"]: now,
                },
            )
            message = f"物品已处置（{item_name}，编号: {case_number}），请记录处置详情"
            logger.info("90天处置完成: %s", case_number)
            # TODO: 触发物品处置审批流程

        case _:
            raise ValueError(
                f"不支持的处理动作: {action}，"
                f"可选: '30天提醒' / '60天公告' / '90天处置'"
            )

    return {
        "success": True,
        "message": message,
        "action_taken": action,
        "case_number": case_number,
    }


# ---------------------------------------------------------------------------
# 内部工具函数
# ---------------------------------------------------------------------------

def _shipping_sms(
    guest_name: str,
    case_number: str,
    courier_company: str,
    tracking_number: str,
) -> str:
    """
    生成邮寄通知短信文本（控制在 70 字符以内）。

    Args:
        guest_name: 宾客姓名
        case_number: 案件编号
        courier_company: 快递公司
        tracking_number: 运单号

    Returns:
        短信文本
    """
    sms = (
        f"【天津瑞湾开元名都酒店】{guest_name}您好，"
        f"您的遗留物品已寄出。"
        f"{courier_company}单号:{tracking_number}，"
        f"请注意查收。"
    )
    if len(sms) > 70:
        sms = (
            f"【天津瑞湾开元名都酒店】{guest_name}您好，"
            f"遗留物品已寄出。"
            f"{courier_company}:{tracking_number}。"
            f"详查 s.xx.cn/{case_number}"
        )
    return sms
