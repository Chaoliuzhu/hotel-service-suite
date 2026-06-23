"""
workflow.luggage — 行李寄存工作流

提供行李寄存业务的全流程管理：
  - 寄存 (deposit): 创建记录、生成条码/二维码、生成凭证、触发打印、发送电子凭证
  - 提取 (claim): 验证码校验、更新状态、记录提取时间
  - 逾期检查 (check_overdue): 查找超期未取物品
  - 逾期提醒 (send_overdue_alert): 向值班经理发送飞书提醒

编号自动生成规则：LG-{YYYYMMDD}-{seq}
  其中 seq 为当日记录序号（从多维表格计数获取）。
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta
from typing import Any

from bitable.client import BitableClient, BitableError
from voucher.engine import (
    LuggageVoucherData,
    LuggageVoucherRenderer,
    generate_barcode_data,
    generate_qr_data,
    generate_verification_code,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 配置常量
# ---------------------------------------------------------------------------

# 多维表格配置 — 实际部署时应从环境变量或配置中心读取
LUGGAGE_APP_TOKEN = ""       # 行李寄存多维表格 app_token
LUGGAGE_TABLE_ID = ""        # 行李寄存数据表 ID
DUTY_MANAGER_CHAT_ID = ""    # 值班经理飞书群 chat_id

# 字段名映射（多维表格字段名 → 业务字段）
FIELD_MAP = {
    "deposit_number": "寄存编号",
    "guest_name": "宾客姓名",
    "room": "房间号",
    "phone": "联系电话",
    "item_count": "寄存件数",
    "item_desc": "物品描述",
    "storage_type": "寄存类型",
    "storage_location": "寄存位置",
    "deposit_time": "寄存时间",
    "expected_pickup": "预计提取时间",
    "verification_code": "提取验证码",
    "barcode": "条形码",
    "status": "状态",
    "claim_time": "提取时间",
    "claimer_name": "提取人",
    "created_at": "创建时间",
}


# ---------------------------------------------------------------------------
# 编号生成
# ---------------------------------------------------------------------------

def _generate_deposit_number(client: BitableClient) -> str:
    """
    自动生成寄存编号：LG-{YYYYMMDD}-{seq}

    seq 通过查询当日已有记录数 + 1 得到，确保编号连续且不重复。

    Args:
        client: 多维表格客户端

    Returns:
        格式化的寄存编号，如 "LG-20250101-003"
    """
    today = datetime.now()
    date_str = today.strftime("%Y%m%d")

    # 构建筛选公式：查找当天创建的记录
    # 使用 CreatedTime >= 今日零点的条件
    today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    filter_formula = f'IS_AFTER({{创建时间}}, "{today_start.isoformat()}")'

    try:
        count = client.count_records(LUGGAGE_APP_TOKEN, LUGGAGE_TABLE_ID, filter_formula)
    except BitableError:
        logger.warning("无法查询当日记录数，默认序号为 1")
        count = 0

    seq = count + 1
    return f"LG-{date_str}-{seq:03d}"


# ---------------------------------------------------------------------------
# 核心业务函数
# ---------------------------------------------------------------------------

def deposit_luggage(
    client: BitableClient,
    guest_name: str,
    room: str,
    phone: str,
    item_count: int,
    item_desc: str,
    storage_type: str = "短期寄存",
    storage_location: str = "前台行李房",
    expected_pickup: str | None = None,
) -> dict[str, Any]:
    """
    行李寄存 — 创建寄存记录并生成凭证。

    完整流程：
      1. 自动生成寄存编号
      2. 生成 6 位提取验证码
      3. 生成条码和二维码数据
      4. 在多维表格中创建记录
      5. 生成 HTML / 飞书卡片 / 短信 / 微信模板消息
      6. 返回包含所有凭证的结果

    Args:
        client: 多维表格客户端
        guest_name: 宾客姓名
        room: 房间号
        phone: 联系电话
        item_count: 寄存件数
        item_desc: 物品描述
        storage_type: 寄存类型（短期寄存 / 长期寄存）
        storage_location: 寄存位置
        expected_pickup: 预计提取时间（默认 24 小时后）

    Returns:
        包含 deposit_number, verification_code, record_id, vouchers 的字典

    Raises:
        BitableError: 多维表格操作失败
    """
    now = datetime.now()
    deposit_number = _generate_deposit_number(client)
    verification_code = generate_verification_code()
    barcode = generate_barcode_data(deposit_number)
    qr_data = generate_qr_data(deposit_number, verification_code)

    if expected_pickup is None:
        # 默认预计提取时间：24 小时后
        expected_pickup_dt = now + timedelta(hours=24)
        expected_pickup = expected_pickup_dt.strftime("%Y-%m-%d %H:%M")

    deposit_time = now.strftime("%Y-%m-%d %H:%M")

    # 构建多维表格字段
    fields = {
        FIELD_MAP["deposit_number"]: deposit_number,
        FIELD_MAP["guest_name"]: guest_name,
        FIELD_MAP["room"]: room,
        FIELD_MAP["phone"]: phone,
        FIELD_MAP["item_count"]: item_count,
        FIELD_MAP["item_desc"]: item_desc,
        FIELD_MAP["storage_type"]: storage_type,
        FIELD_MAP["storage_location"]: storage_location,
        FIELD_MAP["deposit_time"]: deposit_time,
        FIELD_MAP["expected_pickup"]: expected_pickup,
        FIELD_MAP["verification_code"]: verification_code,
        FIELD_MAP["barcode"]: barcode,
        FIELD_MAP["status"]: "已寄存",
        FIELD_MAP["created_at"]: now.isoformat(timespec="seconds"),
    }

    # 创建多维表格记录
    record_id = client.create_record(LUGGAGE_APP_TOKEN, LUGGAGE_TABLE_ID, fields)
    logger.info("行李寄存记录已创建: %s (record_id=%s)", deposit_number, record_id)

    # 构建凭证数据
    voucher_data = LuggageVoucherData(
        deposit_number=deposit_number,
        guest_name=guest_name,
        room=room,
        item_count=item_count,
        deposit_time=deposit_time,
        expected_pickup=expected_pickup,
        storage_type=storage_type,
        storage_location=storage_location,
        item_desc=item_desc,
        barcode=barcode,
        verification_code=verification_code,
        qr_code_data_uri=qr_data,  # 实际使用时应生成 base64 图片
    )

    # 渲染多渠道凭证
    renderer = LuggageVoucherRenderer()
    vouchers = {
        "html": renderer.render_html(voucher_data),
        "feishu_card": renderer.render_feishu_card(voucher_data),
        "sms": renderer.render_sms(voucher_data),
        "wechat": renderer.render_wechat_template(voucher_data),
    }

    # TODO: 触发打印机打印纸质凭证（对接打印机 API）
    # TODO: 通过飞书 Bot 发送电子凭证给宾客或前台

    return {
        "deposit_number": deposit_number,
        "verification_code": verification_code,
        "record_id": record_id,
        "barcode": barcode,
        "qr_data": qr_data,
        "vouchers": vouchers,
    }


def claim_luggage(
    client: BitableClient,
    deposit_number: str,
    verification_code: str,
    claimer_name: str,
) -> dict[str, Any]:
    """
    行李提取 — 验证码校验并更新状态。

    流程：
      1. 根据寄存编号查找记录
      2. 校验验证码是否匹配
      3. 更新状态为 "已提取"
      4. 记录提取时间和提取人

    Args:
        client: 多维表格客户端
        deposit_number: 寄存编号
        verification_code: 提取验证码
        claimer_name: 提取人姓名

    Returns:
        包含 success, message, record_id 的字典

    Raises:
        BitableError: 多维表格操作失败
    """
    # 查找对应记录
    records = client.list_records(
        LUGGAGE_APP_TOKEN,
        LUGGAGE_TABLE_ID,
        filters={
            "conjunction": "and",
            "conditions": [
                {
                    "field_name": FIELD_MAP["deposit_number"],
                    "operator": "is",
                    "value": [deposit_number],
                },
            ],
        },
        limit=1,
    )

    if not records:
        logger.warning("未找到寄存记录: %s", deposit_number)
        return {"success": False, "message": f"未找到寄存编号 {deposit_number} 的记录", "record_id": None}

    record = records[0]
    record_id = record.get("record_id") or record.get("id") or ""
    fields = record.get("fields", {})

    # 校验验证码
    stored_code = fields.get(FIELD_MAP["verification_code"], "")
    if stored_code != verification_code:
        logger.warning("验证码不匹配: 输入=%s, 存储=%s", verification_code, stored_code)
        return {
            "success": False,
            "message": "验证码不匹配，请核实后重试",
            "record_id": record_id,
        }

    # 检查是否已提取
    current_status = fields.get(FIELD_MAP["status"], "")
    if current_status == "已提取":
        return {
            "success": False,
            "message": "该行李已提取，无需重复操作",
            "record_id": record_id,
        }

    # 更新状态
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    client.update_record(
        LUGGAGE_APP_TOKEN,
        LUGGAGE_TABLE_ID,
        record_id,
        {
            FIELD_MAP["status"]: "已提取",
            FIELD_MAP["claim_time"]: now,
            FIELD_MAP["claimer_name"]: claimer_name,
        },
    )

    logger.info("行李已提取: %s, 提取人: %s", deposit_number, claimer_name)
    return {
        "success": True,
        "message": f"行李 {deposit_number} 提取成功，提取人: {claimer_name}",
        "record_id": record_id,
    }


def check_overdue(
    client: BitableClient,
    hours_threshold: int = 24,
) -> list[dict[str, Any]]:
    """
    检查逾期未提取的行李。

    查找状态为 "已寄存" 且超过预计提取时间的记录。

    Args:
        client: 多维表格客户端
        hours_threshold: 超过预计提取时间的小时数阈值，默认 24 小时

    Returns:
        逾期记录列表，每条包含寄存编号、宾客姓名、房间号、联系电话、
        预计提取时间、超期时长等信息
    """
    # 查询所有状态为 "已寄存" 的记录
    records = client.list_records(
        LUGGAGE_APP_TOKEN,
        LUGGAGE_TABLE_ID,
        filters={
            "conjunction": "and",
            "conditions": [
                {
                    "field_name": FIELD_MAP["status"],
                    "operator": "is",
                    "value": ["已寄存"],
                },
            ],
        },
        limit=500,
    )

    now = datetime.now()
    overdue_items: list[dict[str, Any]] = []

    for record in records:
        fields = record.get("fields", {})
        expected_pickup_str = fields.get(FIELD_MAP["expected_pickup"], "")

        if not expected_pickup_str:
            continue

        try:
            # 尝试多种日期格式解析
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M"):
                try:
                    expected_pickup_dt = datetime.strptime(expected_pickup_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                logger.warning("无法解析预计提取时间: %s", expected_pickup_str)
                continue

            overdue_duration = now - expected_pickup_dt
            overdue_hours = overdue_duration.total_seconds() / 3600

            if overdue_hours >= hours_threshold:
                overdue_items.append({
                    "record_id": record.get("record_id") or record.get("id"),
                    "deposit_number": fields.get(FIELD_MAP["deposit_number"], ""),
                    "guest_name": fields.get(FIELD_MAP["guest_name"], ""),
                    "room": fields.get(FIELD_MAP["room"], ""),
                    "phone": fields.get(FIELD_MAP["phone"], ""),
                    "expected_pickup": expected_pickup_str,
                    "overdue_hours": round(overdue_hours, 1),
                    "item_count": fields.get(FIELD_MAP["item_count"], 0),
                    "storage_location": fields.get(FIELD_MAP["storage_location"], ""),
                })

        except Exception as exc:
            logger.error("处理记录异常: %s", exc, exc_info=True)

    logger.info("逾期行李检查完成: 共 %d 件逾期 (阈值 %d 小时)", len(overdue_items), hours_threshold)
    return overdue_items


def send_overdue_alert(
    client: BitableClient,
    overdue_items: list[dict[str, Any]],
) -> bool:
    """
    向值班经理发送逾期行李提醒（飞书消息卡片）。

    当检测到逾期行李时，生成汇总卡片并通过飞书 Bot 发送到值班经理群。

    Args:
        client: 多维表格客户端（保留接口，实际发送可能需要独立的飞书消息客户端）
        overdue_items: 逾期物品列表（来自 check_overdue 的返回）

    Returns:
        发送是否成功
    """
    if not overdue_items:
        logger.info("无逾期行李，跳过提醒发送")
        return True

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 构造逾期汇总卡片内容
    item_lines: list[str] = []
    for item in overdue_items[:10]:  # 最多显示 10 条
        item_lines.append(
            f"- **{item['deposit_number']}** | "
            f"{item['guest_name']} | "
            f"房间 {item['room']} | "
            f"超期 {item['overdue_hours']}h | "
            f"电话 {item['phone']}"
        )

    if len(overdue_items) > 10:
        item_lines.append(f"\n...及其他 {len(overdue_items) - 10} 条记录")

    card_content = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "⚠️ 行李逾期提醒"},
            "template": "orange",
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**检查时间：** {now}\n"
                        f"**逾期数量：** {len(overdue_items)} 件"
                    ),
                },
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "\n".join(item_lines),
                },
            },
            {"tag": "hr"},
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": "请尽快联系宾客确认提取时间，避免行李积压。",
                    }
                ],
            },
        ],
    }

    # TODO: 调用飞书 Bot API 发送卡片消息到值班经理群
    # 示例: lark-cli im send --chat-id <DUTY_MANAGER_CHAT_ID> --card <card_json>
    logger.info(
        "逾期提醒已生成（共 %d 件），待发送至值班经理群 %s",
        len(overdue_items),
        DUTY_MANAGER_CHAT_ID,
    )

    # 此处仅记录日志，实际部署时需对接飞书消息 API
    import json
    logger.debug("卡片内容:\n%s", json.dumps(card_content, ensure_ascii=False, indent=2))

    return True
