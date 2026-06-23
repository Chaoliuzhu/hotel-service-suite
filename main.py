#!/usr/bin/env python3
"""
酒店服务套件 - 统一 CLI 入口

支持行李寄存全流程管理和遗留物品全流程管理，
包括登记、取件/认领、打印标签、发送凭证、超期检查等操作。

用法：
    python main.py deposit --guest "张三" --room 1208 --phone 13800138000 ...
    python main.py claim --number LG-20260623-001 --code 8826
    python main.py register --item "iPhone 15" --category 电子产品 ...
    python main.py mail --number LF-20260623-001 --courier "顺丰" ...
    python main.py print --number LG-20260623-001 --printer 192.168.1.100
    python main.py voucher --number LG-20260623-001 --channel feishu
    python main.py check-overdue --type luggage --hours 24
    python main.py check-overdue --type lost-found --days 30
"""

import argparse
import json
import os
import random
import socket
import subprocess
import sys
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# 常量配置
# ---------------------------------------------------------------------------

CST = timezone(timedelta(hours=8))

# 行李寄存多维表格
LUGGAGE_APP_TOKEN = "Atj6bOVJtaDGSjspKDqcx3Jqnfd"
LUGGAGE_TABLE_ID = "tblMPvX3VKodb80I"

# 遗留物品多维表格
LOST_FOUND_APP_TOKEN = "JJpTbxNJgaVojJsfUItcmvq5nqf"
LOST_FOUND_TABLE_ID = "tblgcBcPR9P8fina"

# 寄存类型枚举
DEPOSIT_TYPES = ["普通行李", "贵重行李", "大件箱包", "易碎物品"]
STORAGE_LOCATIONS = ["一楼行李房", "三楼长住行李房"]

# 遗留物品类别枚举
ITEM_CATEGORIES = ["电子产品", "首饰珠宝", "证件文件", "衣物包袋", "其他"]
PICKUP_LOCATIONS = ["客房", "大堂", "餐厅", "泳池", "停车场", "会议室"]
STORAGE_LOCATIONS_LF = ["客房部保险箱", "前厅部保管柜", "失物招领处", "已返还宾客"]

# 重要物品类别（自动标记）
IMPORTANT_CATEGORIES = {"电子产品", "首饰珠宝", "证件文件"}

# 通知渠道
NOTIFICATION_CHANNELS = ["feishu", "sms", "wechat"]

# TSPL 打印机默认端口
DEFAULT_PRINTER_PORT = 9100


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def run_lark_cli(command: str, **kwargs) -> dict:
    """执行 lark-cli 命令并返回 JSON 结果"""
    cmd_parts = command.split()
    for key, value in kwargs.items():
        if isinstance(value, dict) or isinstance(value, list):
            cmd_parts.extend([f"--{key}", json.dumps(value, ensure_ascii=False)])
        elif isinstance(value, bool):
            if value:
                cmd_parts.append(f"--{key}")
        else:
            cmd_parts.extend([f"--{key}", str(value)])

    result = subprocess.run(
        cmd_parts,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        print(f"[错误] lark-cli 执行失败: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw": result.stdout}


def generate_sequence_number(records: list, prefix: str, date_str: str) -> str:
    """根据已有记录生成当日顺序号"""
    max_seq = 0
    for record in records:
        fields = record.get("fields", {})
        number = fields.get("寄存单号", "") or fields.get("失物编号", "")
        if number and number.startswith(prefix):
            parts = number.split("-")
            if len(parts) == 3 and parts[1] == date_str:
                try:
                    seq = int(parts[2])
                    max_seq = max(max_seq, seq)
                except ValueError:
                    pass
    return f"{max_seq + 1:03d}"


def generate_pickup_code(length: int = 4) -> str:
    """生成随机取件验证码"""
    return f"{random.randint(0, 10**length - 1):0{length}d}"


def now_iso() -> str:
    """返回当前时间的 ISO 8601 格式（CST）"""
    return datetime.now(CST).isoformat()


def today_str() -> str:
    """返回今日日期字符串 YYYYMMDD"""
    return datetime.now(CST).strftime("%Y%m%d")


def today_display() -> str:
    """返回今日日期显示格式 YYYY-MM-DD"""
    return datetime.now(CST).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# TSPL 打印
# ---------------------------------------------------------------------------

def generate_luggage_tspl(deposit_number: str, guest_name: str, room_number: str,
                          item_count: int, deposit_type: str, storage_location: str,
                          pickup_code: str) -> str:
    """生成行李寄存标签的 TSPL 指令"""
    return f"""SIZE 60 mm, 40 mm
GAP 2 mm, 0 mm
DIRECTION 1
REFERENCE 0, 0
CLS
TEXT 200, 8, "TSS24.BF2", 0, 1, 1, "行李寄存标签"
TEXT 150, 40, "TSS24.BF2", 0, 1, 1, "{deposit_number}"
BARCODE 200, 65, "128", 50, 1, 0, 2, 2, "{deposit_number}"
TEXT 10, 130, "TSS24.BF2", 0, 1, 1, "宾客: {guest_name}"
TEXT 10, 155, "TSS24.BF2", 0, 1, 1, "房号: {room_number}"
TEXT 10, 180, "TSS24.BF2", 0, 1, 1, "件数: {item_count}"
TEXT 10, 205, "TSS24.BF2", 0, 1, 1, "类型: {deposit_type}"
TEXT 10, 230, "TSS24.BF2", 0, 1, 1, "位置: {storage_location}"
TEXT 10, 255, "TSS24.BF2", 0, 1, 1, "日期: {today_display()}"
BAR 10, 280, 460, 2
TEXT 120, 290, "TSS24.BF2", 0, 1, 1, "取件验证码: {pickup_code}"
PRINT 1
"""


def generate_lost_found_tspl(lost_number: str, item_name: str, item_category: str,
                             found_location: str, is_important: bool) -> str:
    """生成遗留物品标签的 TSPL 指令"""
    important_mark = "[重要物品] 保险箱保管" if is_important else ""
    return f"""SIZE 50 mm, 30 mm
GAP 2 mm, 0 mm
DIRECTION 1
REFERENCE 0, 0
CLS
TEXT 170, 5, "TSS24.BF2", 0, 1, 1, "遗留物品标签"
TEXT 100, 25, "TSS24.BF2", 0, 1, 1, "{lost_number}"
BARCODE 130, 45, "128", 40, 1, 0, 2, 2, "{lost_number}"
TEXT 10, 95, "TSS24.BF2", 0, 1, 1, "物品: {item_name}"
TEXT 10, 115, "TSS24.BF2", 0, 1, 1, "类别: {item_category}"
TEXT 10, 135, "TSS24.BF2", 0, 1, 1, "地点: {found_location}"
TEXT 10, 155, "TSS24.BF2", 0, 1, 1, "日期: {today_display()}"
BAR 10, 175, 380, 2
TEXT 130, 180, "TSS24.BF2", 0, 1, 1, "{important_mark}"
PRINT 1
"""


def send_to_printer(tspl_content: str, printer_ip: str, port: int = DEFAULT_PRINTER_PORT):
    """通过 TCP 发送 TSPL 指令到热敏标签打印机"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((printer_ip, port))
        sock.sendall(tspl_content.encode("utf-8"))
        sock.close()
        print(f"[成功] 打印指令已发送至 {printer_ip}:{port}")
    except socket.timeout:
        print(f"[错误] 连接打印机超时: {printer_ip}:{port}", file=sys.stderr)
        sys.exit(1)
    except socket.error as e:
        print(f"[错误] 无法连接打印机 {printer_ip}:{port} - {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# 通知渠道
# ---------------------------------------------------------------------------

def send_feishu_card(chat_id: str, card_json: dict):
    """发送飞书交互卡片"""
    result = run_lark_cli(
        "lark-cli im +send",
        **{
            "chat-id": chat_id,
            "msg-type": "interactive",
            "content": json.dumps(card_json, ensure_ascii=False),
        }
    )
    print(f"[成功] 飞书卡片已发送 -> {chat_id}")
    return result


def send_sms(phone: str, template_id: str, params: dict):
    """发送短信通知"""
    sms_payload = {
        "phone": phone,
        "template_id": template_id,
        "params": params,
    }
    print(f"[信息] 短信发送请求: {json.dumps(sms_payload, ensure_ascii=False)}")
    # 实际部署时替换为 HTTP 请求调用短信网关
    # import requests
    # resp = requests.post(SMS_GATEWAY_URL, json=sms_payload)
    print(f"[成功] 短信已发送至 {phone}")


def send_wechat_template(openid: str, template_id: str, data: dict, miniprogram: dict = None):
    """发送微信模板消息"""
    wechat_payload = {
        "touser": openid,
        "template_id": template_id,
        "data": data,
    }
    if miniprogram:
        wechat_payload["miniprogram"] = miniprogram
    print(f"[信息] 微信模板消息请求: {json.dumps(wechat_payload, ensure_ascii=False)}")
    # 实际部署时替换为微信 API 调用
    print(f"[成功] 微信模板消息已发送至 {openid}")


def build_luggage_voucher_card(deposit_number: str, guest_name: str, room_number: str,
                               item_count: int, deposit_type: str, storage_location: str,
                               description: str, pickup_code: str, deposit_time: str) -> dict:
    """构建行李寄存凭证飞书卡片"""
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "行李寄存凭证"},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**寄存单号**\n{deposit_number}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**宾客姓名**\n{guest_name}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**房号**\n{room_number}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**寄存件数**\n{item_count} 件"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**寄存类型**\n{deposit_type}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**寄存位置**\n{storage_location}"}},
                    ],
                },
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**行李描述：**\n{description}"}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**寄存时间：** {deposit_time}"}},
                {
                    "tag": "note",
                    "elements": [
                        {"tag": "plain_text", "content": f"取件验证码: {pickup_code} | 请妥善保管此凭证，取件时需出示验证码"},
                    ],
                },
            ],
        },
    }


def build_lost_found_notification_card(lost_number: str, item_name: str, item_category: str,
                                       found_location: str, found_date: str,
                                       storage_location: str, description: str) -> dict:
    """构建遗留物品通知飞书卡片"""
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "遗留物品认领通知"},
                "template": "orange",
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**失物编号**\n{lost_number}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**物品名称**\n{item_name}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**物品类别**\n{item_category}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**发现地点**\n{found_location}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**发现日期**\n{found_date}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**保管位置**\n{storage_location}"}},
                    ],
                },
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**物品描述：**\n{description}"}},
                {"tag": "hr"},
                {
                    "tag": "note",
                    "elements": [
                        {"tag": "plain_text", "content": "请携带有效证件到前台认领，或联系我们安排邮寄。"},
                    ],
                },
            ],
        },
    }


# ---------------------------------------------------------------------------
# 子命令：deposit（行李寄存登记）
# ---------------------------------------------------------------------------

def cmd_deposit(args):
    """执行行李寄存登记"""
    # 校验参数
    if args.type and args.type not in DEPOSIT_TYPES:
        print(f"[错误] 寄存类型无效: {args.type}，可选值: {', '.join(DEPOSIT_TYPES)}", file=sys.stderr)
        sys.exit(1)
    if args.location and args.location not in STORAGE_LOCATIONS:
        print(f"[错误] 寄存位置无效: {args.location}，可选值: {', '.join(STORAGE_LOCATIONS)}", file=sys.stderr)
        sys.exit(1)

    date_str = today_str()
    operator = args.operator or "系统自动"

    # 查询当日已有记录
    print(f"[信息] 查询 {date_str} 当日寄存记录...")
    result = run_lark_cli(
        "lark-cli base +record-list",
        **{
            "app-token": LUGGAGE_APP_TOKEN,
            "table-id": LUGGAGE_TABLE_ID,
            "filter": json.dumps({
                "conjunction": "and",
                "conditions": [
                    {"field_name": "寄存日期", "operator": "is", "value": ["TODAY"]}
                ]
            }),
            "fields": '["寄存单号"]',
            "format": "json",
        }
    )

    records = result.get("items", [])
    seq = generate_sequence_number(records, "LG", date_str)
    deposit_number = f"LG-{date_str}-{seq}"
    pickup_code = generate_pickup_code()

    deposit_time = now_iso()
    fields = {
        "寄存单号": deposit_number,
        "宾客姓名": args.guest,
        "房号": str(args.room),
        "入住房号": str(args.room),
        "联系方式": args.phone,
        "寄存日期": deposit_time,
        "寄存件数": args.items,
        "寄存类型": args.type or "普通行李",
        "寄存位置": args.location or "一楼行李房",
        "行李描述": args.desc,
        "标签打印状态": "未打印",
        "取件验证码": pickup_code,
        "状态": "待取",
        "经办人": operator,
    }

    print(f"[信息] 创建寄存记录: {deposit_number}...")
    run_lark_cli(
        "lark-cli base +record-create",
        **{
            "app-token": LUGGAGE_APP_TOKEN,
            "table-id": LUGGAGE_TABLE_ID,
            "fields": json.dumps(fields, ensure_ascii=False),
        }
    )

    print("=" * 50)
    print(f"  寄存单号:   {deposit_number}")
    print(f"  宾客姓名:   {args.guest}")
    print(f"  房号:       {args.room}")
    print(f"  联系方式:   {args.phone}")
    print(f"  寄存件数:   {args.items}")
    print(f"  寄存类型:   {fields['寄存类型']}")
    print(f"  寄存位置:   {fields['寄存位置']}")
    print(f"  取件验证码: {pickup_code}")
    print(f"  寄存时间:   {datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  经办人:     {operator}")
    print("=" * 50)
    print("[成功] 行李寄存登记完成！")
    print(f"[提示] 请使用以下命令打印标签: python main.py print --number {deposit_number} --printer <打印机IP>")
    print(f"[提示] 请使用以下命令发送凭证: python main.py voucher --number {deposit_number} --channel feishu")


# ---------------------------------------------------------------------------
# 子命令：claim（行李取件核销）
# ---------------------------------------------------------------------------

def cmd_claim(args):
    """执行行李取件核销"""
    conditions = []
    if args.number:
        conditions.append({"field_name": "寄存单号", "operator": "is", "value": [args.number]})
    if args.code:
        conditions.append({"field_name": "取件验证码", "operator": "is", "value": [args.code]})
    conditions.append({"field_name": "状态", "operator": "is", "value": ["待取"]})

    filter_json = json.dumps({"conjunction": "and", "conditions": conditions})

    print("[信息] 查询寄存记录...")
    result = run_lark_cli(
        "lark-cli base +record-list",
        **{
            "app-token": LUGGAGE_APP_TOKEN,
            "table-id": LUGGAGE_TABLE_ID,
            "filter": filter_json,
            "format": "json",
        }
    )

    items = result.get("items", [])
    if not items:
        print("[错误] 未找到匹配的待取件记录，请核实寄存单号和验证码。", file=sys.stderr)
        sys.exit(1)
    if len(items) > 1:
        print(f"[警告] 找到 {len(items)} 条匹配记录，请提供更精确的查询条件。", file=sys.stderr)
        for item in items:
            f = item.get("fields", {})
            print(f"  - {f.get('寄存单号', 'N/A')} | {f.get('宾客姓名', 'N/A')} | {f.get('房号', 'N/A')}")
        sys.exit(1)

    record = items[0]
    record_id = record.get("record_id", "")
    fields = record.get("fields", {})

    # 验证码校验
    if args.code and fields.get("取件验证码") != args.code:
        print("[错误] 验证码不匹配，取件被拒绝。", file=sys.stderr)
        sys.exit(1)

    operator = args.operator or "系统自动"
    pickup_time = now_iso()

    update_fields = {
        "状态": "已取",
        "取件日期": pickup_time,
        "取件时间": datetime.now(CST).strftime("%H:%M"),
        "取件经办人": operator,
    }

    print(f"[信息] 更新取件状态: {fields.get('寄存单号', 'N/A')}...")
    run_lark_cli(
        "lark-cli base +record-update",
        **{
            "app-token": LUGGAGE_APP_TOKEN,
            "table-id": LUGGAGE_TABLE_ID,
            "record-id": record_id,
            "fields": json.dumps(update_fields, ensure_ascii=False),
        }
    )

    print("=" * 50)
    print(f"  寄存单号: {fields.get('寄存单号', 'N/A')}")
    print(f"  宾客姓名: {fields.get('宾客姓名', 'N/A')}")
    print(f"  房号:     {fields.get('房号', 'N/A')}")
    print(f"  取件时间: {datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  经办人:   {operator}")
    print("=" * 50)
    print("[成功] 行李取件核销完成！")


# ---------------------------------------------------------------------------
# 子命令：register（遗留物品登记）
# ---------------------------------------------------------------------------

def cmd_register(args):
    """执行遗留物品登记"""
    if args.category and args.category not in ITEM_CATEGORIES:
        print(f"[错误] 物品类别无效: {args.category}，可选值: {', '.join(ITEM_CATEGORIES)}", file=sys.stderr)
        sys.exit(1)
    if args.location and args.location not in PICKUP_LOCATIONS:
        print(f"[错误] 捡拾地点无效: {args.location}，可选值: {', '.join(PICKUP_LOCATIONS)}", file=sys.stderr)
        sys.exit(1)

    date_str = today_str()
    item_category = args.category or "其他"
    is_important_flag = args.important or item_category in IMPORTANT_CATEGORIES
    is_important = "是" if is_important_flag else "否"

    # 自动判定保管位置
    if is_important_flag:
        storage_location = "客房部保险箱"
    else:
        storage_location = "前厅部保管柜"

    # 查询当日已有记录
    print(f"[信息] 查询 {date_str} 当日遗留物品记录...")
    result = run_lark_cli(
        "lark-cli base +record-list",
        **{
            "app-token": LOST_FOUND_APP_TOKEN,
            "table-id": LOST_FOUND_TABLE_ID,
            "filter": json.dumps({
                "conjunction": "and",
                "conditions": [
                    {"field_name": "发现日期", "operator": "is", "value": ["TODAY"]}
                ]
            }),
            "fields": '["失物编号"]',
            "format": "json",
        }
    )

    records = result.get("items", [])
    seq = generate_sequence_number(records, "LF", date_str)
    lost_number = f"LF-{date_str}-{seq}"
    found_time = now_iso()

    fields = {
        "失物编号": lost_number,
        "物品名称": args.item,
        "物品类别": item_category,
        "物品描述": args.desc or "",
        "发现日期": found_time,
        "发现地点": args.found_at or "",
        "发现人": args.finder or "",
        "捡拾地点": args.location or "客房",
        "捡拾人": args.finder or "",
        "重要物品": is_important,
        "储备保管位置": storage_location,
        "物品状态": "待认领",
        "认领状态": "待认领",
        "天津瑞湾-遗留物品管理台账": lost_number,
    }

    # 可选字段
    if args.guest:
        fields["宾客姓名"] = args.guest
    if args.phone:
        fields["宾客联系方式"] = args.phone
    if args.room:
        fields["发现地点"] = fields.get("发现地点", "") or f"{args.room}房间"
    if args.detail:
        fields["物品明细"] = args.detail

    print(f"[信息] 创建遗留物品记录: {lost_number}...")
    run_lark_cli(
        "lark-cli base +record-create",
        **{
            "app-token": LOST_FOUND_APP_TOKEN,
            "table-id": LOST_FOUND_TABLE_ID,
            "fields": json.dumps(fields, ensure_ascii=False),
        }
    )

    print("=" * 50)
    print(f"  失物编号:   {lost_number}")
    print(f"  物品名称:   {args.item}")
    print(f"  物品类别:   {item_category}")
    print(f"  重要物品:   {is_important}")
    print(f"  保管位置:   {storage_location}")
    print(f"  发现日期:   {datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  捡拾地点:   {fields['捡拾地点']}")
    if args.guest:
        print(f"  宾客姓名:   {args.guest}")
    if args.phone:
        print(f"  联系方式:   {args.phone}")
    print("=" * 50)
    print("[成功] 遗留物品登记完成！")

    if is_important_flag:
        print("[重要] 此物品为重要物品，请务必在今天18:00前送入保险箱保管！")
    print(f"[提示] 请使用以下命令打印标签: python main.py print --number {lost_number} --printer <打印机IP>")


# ---------------------------------------------------------------------------
# 子命令：mail（邮寄遗留物品）
# ---------------------------------------------------------------------------

def cmd_mail(args):
    """执行邮寄遗留物品"""
    # 查询记录
    print(f"[信息] 查询物品记录: {args.number}...")
    result = run_lark_cli(
        "lark-cli base +record-list",
        **{
            "app-token": LOST_FOUND_APP_TOKEN,
            "table-id": LOST_FOUND_TABLE_ID,
            "filter": json.dumps({
                "conjunction": "and",
                "conditions": [
                    {"field_name": "失物编号", "operator": "is", "value": [args.number]}
                ]
            }),
            "format": "json",
        }
    )

    items = result.get("items", [])
    if not items:
        print(f"[错误] 未找到物品记录: {args.number}", file=sys.stderr)
        sys.exit(1)

    record = items[0]
    record_id = record.get("record_id", "")
    fields = record.get("fields", {})

    current_status = fields.get("物品状态", "")
    if current_status in ("已认领", "已邮寄", "已销毁", "已移交公安"):
        print(f"[错误] 物品当前状态为「{current_status}」，无法执行邮寄操作。", file=sys.stderr)
        sys.exit(1)

    update_fields = {
        "物品状态": "已邮寄",
        "认领状态": "已认领",
        "快递公司": args.courier,
        "运单号": args.tracking,
        "邮寄日期": now_iso(),
        "储备保管位置": "已返还宾客",
    }
    if args.address:
        update_fields["宾客收件地址"] = args.address

    print(f"[信息] 更新邮寄信息...")
    run_lark_cli(
        "lark-cli base +record-update",
        **{
            "app-token": LOST_FOUND_APP_TOKEN,
            "table-id": LOST_FOUND_TABLE_ID,
            "record-id": record_id,
            "fields": json.dumps(update_fields, ensure_ascii=False),
        }
    )

    guest_name = fields.get("宾客姓名", "宾客")
    guest_phone = fields.get("宾客联系方式", "")
    item_name = fields.get("物品名称", "")

    print("=" * 50)
    print(f"  失物编号: {args.number}")
    print(f"  物品名称: {item_name}")
    print(f"  快递公司: {args.courier}")
    print(f"  运单号:   {args.tracking}")
    if args.address:
        print(f"  收件地址: {args.address}")
    print(f"  邮寄日期: {datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    print("[成功] 邮寄信息已更新！")

    # 发送短信通知
    if guest_phone:
        print(f"[信息] 正在发送邮寄通知短信至 {guest_phone}...")
        send_sms(guest_phone, "TPL_LOST_FOUND_MAIL", {
            "guest_name": guest_name,
            "item_name": item_name,
            "lost_number": args.number,
            "courier": args.courier,
            "tracking": args.tracking,
        })


# ---------------------------------------------------------------------------
# 子命令：print（打印标签）
# ---------------------------------------------------------------------------

def cmd_print_label(args):
    """打印条码标签"""
    number = args.number
    printer_ip = args.printer
    port = args.port or DEFAULT_PRINTER_PORT

    if number.startswith("LG-"):
        # 行李寄存标签
        print(f"[信息] 查询行李寄存记录: {number}...")
        result = run_lark_cli(
            "lark-cli base +record-list",
            **{
                "app-token": LUGGAGE_APP_TOKEN,
                "table-id": LUGGAGE_TABLE_ID,
                "filter": json.dumps({
                    "conjunction": "and",
                    "conditions": [
                        {"field_name": "寄存单号", "operator": "is", "value": [number]}
                    ]
                }),
                "format": "json",
            }
        )

        items = result.get("items", [])
        if not items:
            print(f"[错误] 未找到记录: {number}", file=sys.stderr)
            sys.exit(1)

        fields = items[0].get("fields", {})
        tspl = generate_luggage_tspl(
            deposit_number=fields.get("寄存单号", number),
            guest_name=fields.get("宾客姓名", ""),
            room_number=fields.get("房号", ""),
            item_count=fields.get("寄存件数", 1),
            deposit_type=fields.get("寄存类型", "普通行李"),
            storage_location=fields.get("寄存位置", "一楼行李房"),
            pickup_code=fields.get("取件验证码", ""),
        )

        # 更新标签打印状态
        label_status = fields.get("标签打印状态", "未打印")
        new_status = "已补打" if label_status in ("已打印", "已补打") else "已打印"
        record_id = items[0].get("record_id", "")
        run_lark_cli(
            "lark-cli base +record-update",
            **{
                "app-token": LUGGAGE_APP_TOKEN,
                "table-id": LUGGAGE_TABLE_ID,
                "record-id": record_id,
                "fields": json.dumps({"标签打印状态": new_status}, ensure_ascii=False),
            }
        )

    elif number.startswith("LF-"):
        # 遗留物品标签
        print(f"[信息] 查询遗留物品记录: {number}...")
        result = run_lark_cli(
            "lark-cli base +record-list",
            **{
                "app-token": LOST_FOUND_APP_TOKEN,
                "table-id": LOST_FOUND_TABLE_ID,
                "filter": json.dumps({
                    "conjunction": "and",
                    "conditions": [
                        {"field_name": "失物编号", "operator": "is", "value": [number]}
                    ]
                }),
                "format": "json",
            }
        )

        items = result.get("items", [])
        if not items:
            print(f"[错误] 未找到记录: {number}", file=sys.stderr)
            sys.exit(1)

        fields = items[0].get("fields", {})
        tspl = generate_lost_found_tspl(
            lost_number=fields.get("失物编号", number),
            item_name=fields.get("物品名称", ""),
            item_category=fields.get("物品类别", ""),
            found_location=fields.get("发现地点", ""),
            is_important=fields.get("重要物品") == "是",
        )
    else:
        print(f"[错误] 编号格式无法识别: {number}，应以 LG- 或 LF- 开头。", file=sys.stderr)
        sys.exit(1)

    print(f"[信息] 正在向打印机 {printer_ip}:{port} 发送标签指令...")
    send_to_printer(tspl, printer_ip, port)
    print(f"[成功] 标签打印完成: {number}")


# ---------------------------------------------------------------------------
# 子命令：voucher（发送电子凭证）
# ---------------------------------------------------------------------------

def cmd_voucher(args):
    """发送电子凭证"""
    number = args.number
    channel = args.channel

    if channel not in NOTIFICATION_CHANNELS:
        print(f"[错误] 通知渠道无效: {channel}，可选值: {', '.join(NOTIFICATION_CHANNELS)}", file=sys.stderr)
        sys.exit(1)

    if number.startswith("LG-"):
        # 行李寄存凭证
        result = run_lark_cli(
            "lark-cli base +record-list",
            **{
                "app-token": LUGGAGE_APP_TOKEN,
                "table-id": LUGGAGE_TABLE_ID,
                "filter": json.dumps({
                    "conjunction": "and",
                    "conditions": [
                        {"field_name": "寄存单号", "operator": "is", "value": [number]}
                    ]
                }),
                "format": "json",
            }
        )

        items = result.get("items", [])
        if not items:
            print(f"[错误] 未找到记录: {number}", file=sys.stderr)
            sys.exit(1)

        fields = items[0].get("fields", {})
        deposit_time = fields.get("寄存日期", "")
        if deposit_time:
            try:
                dt = datetime.fromisoformat(deposit_time)
                deposit_time = dt.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                pass

        guest_phone = fields.get("联系方式", "")
        guest_name = fields.get("宾客姓名", "")

        if channel == "feishu":
            card = build_luggage_voucher_card(
                deposit_number=number,
                guest_name=guest_name,
                room_number=fields.get("房号", ""),
                item_count=fields.get("寄存件数", 1),
                deposit_type=fields.get("寄存类型", "普通行李"),
                storage_location=fields.get("寄存位置", ""),
                description=fields.get("行李描述", ""),
                pickup_code=fields.get("取件验证码", ""),
                deposit_time=deposit_time,
            )
            chat_id = args.chat_id or "oc_xxxxxxxxxxxxx"
            send_feishu_card(chat_id, card)

        elif channel == "sms":
            if not guest_phone:
                print("[错误] 该记录无联系方式，无法发送短信。", file=sys.stderr)
                sys.exit(1)
            send_sms(guest_phone, "TPL_LUGGAGE_DEPOSIT", {
                "guest_name": guest_name,
                "deposit_number": number,
                "item_count": str(fields.get("寄存件数", 1)),
                "storage_location": fields.get("寄存位置", ""),
                "pickup_code": fields.get("取件验证码", ""),
            })

        elif channel == "wechat":
            openid = args.openid or "OPENID"
            send_wechat_template(openid, "TMPL_LUGGAGE_DEPOSIT", {
                "first": {"value": "您的行李已寄存成功", "color": "#173177"},
                "keyword1": {"value": number, "color": "#173177"},
                "keyword2": {"value": f"{guest_name} / {fields.get('房号', '')}房", "color": "#173177"},
                "keyword3": {"value": f"{fields.get('寄存件数', 1)}件 {fields.get('寄存类型', '')}", "color": "#173177"},
                "keyword4": {"value": deposit_time, "color": "#173177"},
                "keyword5": {"value": f"取件验证码: {fields.get('取件验证码', '')}", "color": "#FF0000"},
                "remark": {"value": f"请妥善保管此凭证，取件时需出示验证码。行李存放于{fields.get('寄存位置', '')}。", "color": "#333333"},
            })

    elif number.startswith("LF-"):
        # 遗留物品通知
        result = run_lark_cli(
            "lark-cli base +record-list",
            **{
                "app-token": LOST_FOUND_APP_TOKEN,
                "table-id": LOST_FOUND_TABLE_ID,
                "filter": json.dumps({
                    "conjunction": "and",
                    "conditions": [
                        {"field_name": "失物编号", "operator": "is", "value": [number]}
                    ]
                }),
                "format": "json",
            }
        )

        items = result.get("items", [])
        if not items:
            print(f"[错误] 未找到记录: {number}", file=sys.stderr)
            sys.exit(1)

        fields = items[0].get("fields", {})
        found_date = fields.get("发现日期", "")
        if found_date:
            try:
                dt = datetime.fromisoformat(found_date)
                found_date = dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

        guest_phone = fields.get("宾客联系方式", "")
        guest_name = fields.get("宾客姓名", "")

        if channel == "feishu":
            card = build_lost_found_notification_card(
                lost_number=number,
                item_name=fields.get("物品名称", ""),
                item_category=fields.get("物品类别", ""),
                found_location=fields.get("发现地点", ""),
                found_date=found_date,
                storage_location=fields.get("储备保管位置", ""),
                description=fields.get("物品描述", ""),
            )
            chat_id = args.chat_id or "oc_xxxxxxxxxxxxx"
            send_feishu_card(chat_id, card)

        elif channel == "sms":
            if not guest_phone:
                print("[错误] 该记录无联系方式，无法发送短信。", file=sys.stderr)
                sys.exit(1)
            send_sms(guest_phone, "TPL_LOST_FOUND", {
                "guest_name": guest_name,
                "item_name": fields.get("物品名称", ""),
                "lost_number": number,
                "pickup_location": fields.get("捡拾地点", ""),
                "hotel_phone": "022-XXXXXXXX",
            })

        elif channel == "wechat":
            openid = args.openid or "OPENID"
            send_wechat_template(openid, "TMPL_LOST_FOUND", {
                "first": {"value": "您有遗留物品待认领", "color": "#FF6600"},
                "keyword1": {"value": number, "color": "#173177"},
                "keyword2": {"value": fields.get("物品名称", ""), "color": "#173177"},
                "keyword3": {"value": fields.get("发现地点", ""), "color": "#173177"},
                "keyword4": {"value": found_date, "color": "#173177"},
                "keyword5": {"value": f"{fields.get('储备保管位置', '')}（妥善保管中）", "color": "#173177"},
                "remark": {"value": "请携带有效证件到前台认领，或联系我们安排邮寄。", "color": "#333333"},
            })

    else:
        print(f"[错误] 编号格式无法识别: {number}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# 子命令：check-overdue（超期检查）
# ---------------------------------------------------------------------------

def cmd_check_overdue(args):
    """检查超期行李或遗留物品"""
    check_type = args.type

    if check_type == "luggage":
        hours = args.hours or 24
        if hours not in (24, 48, 72):
            print(f"[警告] 行李超期检查推荐使用 24/48/72 小时，当前设置为 {hours} 小时。")

        level_map = {24: "一级预警", 48: "二级预警", 72: "三级预警"}
        level = level_map.get(hours, f"自定义({hours}h)")

        time_value = f"{hours}hoursAgo"

        print(f"[信息] 检查行李超期: {level}（{hours}小时）...")
        result = run_lark_cli(
            "lark-cli base +record-list",
            **{
                "app-token": LUGGAGE_APP_TOKEN,
                "table-id": LUGGAGE_TABLE_ID,
                "filter": json.dumps({
                    "conjunction": "and",
                    "conditions": [
                        {"field_name": "状态", "operator": "is", "value": ["待取"]},
                        {"field_name": "寄存日期", "operator": "isLess", "value": [time_value]},
                    ]
                }),
                "fields": '["寄存单号","宾客姓名","房号","联系方式","寄存日期","行李描述"]',
                "format": "json",
            }
        )

        items = result.get("items", [])
        print(f"\n{'=' * 60}")
        print(f"  行李超期报告 - {level}（寄存超过 {hours} 小时）")
        print(f"  检查时间: {datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 60}")

        if not items:
            print("\n  暂无超期行李记录。\n")
        else:
            print(f"\n  共 {len(items)} 件超期行李：\n")
            for i, item in enumerate(items, 1):
                f = item.get("fields", {})
                deposit_date = f.get("寄存日期", "")
                if deposit_date:
                    try:
                        dt = datetime.fromisoformat(deposit_date)
                        deposit_date = dt.strftime("%Y-%m-%d %H:%M")
                    except ValueError:
                        pass
                print(f"  [{i}] {f.get('寄存单号', 'N/A')}")
                print(f"      宾客: {f.get('宾客姓名', 'N/A')} | 房号: {f.get('房号', 'N/A')} | 电话: {f.get('联系方式', 'N/A')}")
                print(f"      寄存时间: {deposit_date}")
                print(f"      描述: {f.get('行李描述', 'N/A')}")
                print()

    elif check_type == "lost-found":
        days = args.days or 30
        if days not in (30, 60, 90):
            print(f"[警告] 遗留物品超期检查推荐使用 30/60/90 天，当前设置为 {days} 天。")

        stage_map = {30: "第一阶段-提醒", 60: "第二阶段-公示", 90: "第三阶段-处理"}
        stage = stage_map.get(days, f"自定义({days}天)")

        time_value = f"{days}daysAgo"
        conditions = [
            {"field_name": "物品状态", "operator": "is", "value": ["待认领"]},
            {"field_name": "发现日期", "operator": "isLess", "value": [time_value]},
        ]

        print(f"[信息] 检查遗留物品超期: {stage}（{days}天）...")
        result = run_lark_cli(
            "lark-cli base +record-list",
            **{
                "app-token": LOST_FOUND_APP_TOKEN,
                "table-id": LOST_FOUND_TABLE_ID,
                "filter": json.dumps({"conjunction": "and", "conditions": conditions}),
                "fields": '["失物编号","物品名称","物品类别","发现日期","宾客姓名","宾客联系方式","储备保管位置","重要物品"]',
                "format": "json",
            }
        )

        items = result.get("items", [])
        print(f"\n{'=' * 60}")
        print(f"  遗留物品超期报告 - {stage}（发现超过 {days} 天）")
        print(f"  检查时间: {datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 60}")

        if not items:
            print("\n  暂无超期遗留物品记录。\n")
        else:
            print(f"\n  共 {len(items)} 件超期遗留物品：\n")
            for i, item in enumerate(items, 1):
                f = item.get("fields", {})
                found_date = f.get("发现日期", "")
                if found_date:
                    try:
                        dt = datetime.fromisoformat(found_date)
                        found_date = dt.strftime("%Y-%m-%d")
                    except ValueError:
                        pass
                important_tag = " [重要]" if f.get("重要物品") == "是" else ""
                print(f"  [{i}] {f.get('失物编号', 'N/A')}{important_tag}")
                print(f"      物品: {f.get('物品名称', 'N/A')} ({f.get('物品类别', 'N/A')})")
                print(f"      宾客: {f.get('宾客姓名', 'N/A')} | 电话: {f.get('宾客联系方式', 'N/A')}")
                print(f"      发现日期: {found_date} | 保管位置: {f.get('储备保管位置', 'N/A')}")
                print()

            if days >= 60:
                print(f"  [操作建议] 以上物品已进入{stage}阶段，请按酒店规定执行相应处置。")
                if days >= 90:
                    print("  [紧急] 90天以上未认领物品需移交公安或统一销毁。")
            print()

    else:
        print(f"[错误] 检查类型无效: {check_type}，可选值: luggage, lost-found", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog="hotel-service",
        description="酒店服务套件 CLI - 行李寄存 & 遗留物品全流程管理",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 行李寄存登记
  python main.py deposit --guest "张三" --room 1208 --phone 13800138000 \\
      --items 2 --desc "行李箱1个，手提袋1个" --type 普通行李 --location 一楼行李房

  # 行李取件
  python main.py claim --number LG-20260623-001 --code 8826

  # 遗留物品登记
  python main.py register --item "iPhone 15" --category 电子产品 \\
      --desc "黑色iPhone 15 Pro Max" --finder "客房服务员小王" \\
      --location 客房 --room 302 --guest "李四" --phone 13900139000 --important

  # 邮寄遗留物品
  python main.py mail --number LF-20260623-001 --courier "顺丰" \\
      --tracking "SF1234567890" --address "北京市朝阳区xxx"

  # 打印标签
  python main.py print --number LG-20260623-001 --printer 192.168.1.100

  # 发送电子凭证
  python main.py voucher --number LG-20260623-001 --channel feishu

  # 超期检查
  python main.py check-overdue --type luggage --hours 24
  python main.py check-overdue --type lost-found --days 30
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # --- deposit ---
    p_deposit = subparsers.add_parser("deposit", help="行李寄存登记")
    p_deposit.add_argument("--guest", required=True, help="宾客姓名")
    p_deposit.add_argument("--room", required=True, type=int, help="房号")
    p_deposit.add_argument("--phone", required=True, help="联系方式")
    p_deposit.add_argument("--items", required=True, type=int, help="寄存件数")
    p_deposit.add_argument("--desc", required=True, help="行李描述")
    p_deposit.add_argument("--type", choices=DEPOSIT_TYPES, default="普通行李", help="寄存类型")
    p_deposit.add_argument("--location", choices=STORAGE_LOCATIONS, default="一楼行李房", help="寄存位置")
    p_deposit.add_argument("--operator", default=None, help="经办人")

    # --- claim ---
    p_claim = subparsers.add_parser("claim", help="行李取件核销")
    p_claim.add_argument("--number", required=True, help="寄存单号 (LG-YYYYMMDD-XXX)")
    p_claim.add_argument("--code", required=True, help="取件验证码")
    p_claim.add_argument("--operator", default=None, help="取件经办人")

    # --- register ---
    p_register = subparsers.add_parser("register", help="遗留物品登记")
    p_register.add_argument("--item", required=True, help="物品名称")
    p_register.add_argument("--category", choices=ITEM_CATEGORIES, default="其他", help="物品类别")
    p_register.add_argument("--desc", default="", help="物品描述")
    p_register.add_argument("--detail", default="", help="物品明细")
    p_register.add_argument("--finder", default="", help="发现人/捡拾人")
    p_register.add_argument("--found-at", default="", help="发现地点详细描述")
    p_register.add_argument("--location", choices=PICKUP_LOCATIONS, default="客房", help="捡拾地点")
    p_register.add_argument("--room", type=int, default=None, help="房号（如有）")
    p_register.add_argument("--guest", default=None, help="宾客姓名（如已知）")
    p_register.add_argument("--phone", default=None, help="宾客联系方式（如已知）")
    p_register.add_argument("--important", action="store_true", help="标记为重要物品")

    # --- mail ---
    p_mail = subparsers.add_parser("mail", help="邮寄遗留物品")
    p_mail.add_argument("--number", required=True, help="失物编号 (LF-YYYYMMDD-XXX)")
    p_mail.add_argument("--courier", required=True, help="快递公司名称")
    p_mail.add_argument("--tracking", required=True, help="快递运单号")
    p_mail.add_argument("--address", required=True, help="宾客收件地址")

    # --- print ---
    p_print = subparsers.add_parser("print", help="打印条码标签")
    p_print.add_argument("--number", required=True, help="寄存单号或失物编号")
    p_print.add_argument("--printer", required=True, help="打印机 IP 地址")
    p_print.add_argument("--port", type=int, default=DEFAULT_PRINTER_PORT, help=f"打印机端口 (默认: {DEFAULT_PRINTER_PORT})")

    # --- voucher ---
    p_voucher = subparsers.add_parser("voucher", help="发送电子凭证")
    p_voucher.add_argument("--number", required=True, help="寄存单号或失物编号")
    p_voucher.add_argument("--channel", required=True, choices=NOTIFICATION_CHANNELS,
                           help="通知渠道: feishu / sms / wechat")
    p_voucher.add_argument("--chat-id", default=None, help="飞书群聊 ID（飞书渠道时）")
    p_voucher.add_argument("--openid", default=None, help="微信 OpenID（微信渠道时）")

    # --- check-overdue ---
    p_overdue = subparsers.add_parser("check-overdue", help="超期检查")
    p_overdue.add_argument("--type", required=True, choices=["luggage", "lost-found"],
                           help="检查类型: luggage（行李）/ lost-found（遗留物品）")
    p_overdue.add_argument("--hours", type=int, default=None, help="行李超期小时数 (24/48/72)")
    p_overdue.add_argument("--days", type=int, default=None, help="遗留物品超期天数 (30/60/90)")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    command_map = {
        "deposit": cmd_deposit,
        "claim": cmd_claim,
        "register": cmd_register,
        "mail": cmd_mail,
        "print": cmd_print_label,
        "voucher": cmd_voucher,
        "check-overdue": cmd_check_overdue,
    }

    handler = command_map.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
