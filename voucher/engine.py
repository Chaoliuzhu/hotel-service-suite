"""
voucher.engine — 电子凭证引擎

为酒店服务套件提供两种凭证类型的多渠道渲染：
  1. 行李寄存凭证 (Luggage Storage Voucher)
  2. 遗留物品凭证 (Lost & Found Voucher)

每种凭证均支持四种输出渠道：
  - 飞书交互卡片 (Feishu Interactive Card)
  - 短信模板 (SMS Template)
  - 微信模板消息 (WeChat Template Message)
  - HTML（邮件/打印用）

使用 Jinja2 模板引擎渲染，模板文件存放在 templates/ 目录下。
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

# 模板目录：与本文件同级的 templates/ 目录
_TEMPLATE_DIR = Path(__file__).parent / "templates"

# 酒店品牌信息
HOTEL_NAME = "天津瑞湾开元名都酒店"
HOTEL_NAME_EN = "New Century Grand Hotel Tianjin Ruiwan"
HOTEL_PHONE = "022-XXXX-XXXX"
HOTEL_ADDRESS = "天津市滨海新区"


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class LuggageVoucherData:
    """行李寄存凭证数据"""

    deposit_number: str          # 寄存编号，如 LG-20250101-001
    guest_name: str              # 宾客姓名
    room: str                    # 房间号
    item_count: int              # 寄存件数
    deposit_time: str            # 寄存时间
    expected_pickup: str         # 预计提取时间
    storage_type: str = ""       # 寄存类型（短期/长期）
    storage_location: str = ""   # 寄存位置
    item_desc: str = ""          # 物品描述
    barcode: str = ""            # 条形码数据
    verification_code: str = ""  # 提取验证码
    qr_code_data_uri: str = ""   # 二维码 Data URI（base64 PNG）
    detail_url: str = ""         # 详情页链接
    contact_url: str = ""        # 联系前台链接

    def to_dict(self) -> dict[str, Any]:
        """转为字典，供模板渲染使用"""
        return {
            "deposit_number": self.deposit_number,
            "guest_name": self.guest_name,
            "room": self.room,
            "item_count": self.item_count,
            "deposit_time": self.deposit_time,
            "expected_pickup": self.expected_pickup,
            "storage_type": self.storage_type or "短期寄存",
            "storage_location": self.storage_location or "前台行李房",
            "item_desc": self.item_desc or "标准行李",
            "barcode": self.barcode or self.deposit_number,
            "verification_code": self.verification_code or "----",
            "qr_code_data_uri": self.qr_code_data_uri or "",
            "detail_url": self.detail_url or "#",
            "contact_url": self.contact_url or "#",
            "hotel_name": HOTEL_NAME,
            "hotel_name_en": HOTEL_NAME_EN,
            "hotel_phone": HOTEL_PHONE,
            "hotel_address": HOTEL_ADDRESS,
        }


@dataclass
class LostFoundVoucherData:
    """遗留物品凭证数据"""

    case_number: str             # 案件编号
    guest_name: str              # 宾客姓名
    item_description: str        # 物品描述
    discovery_date: str          # 发现日期
    discovery_location: str      # 发现地点
    status: str = "待处理"        # 当前状态
    category: str = ""           # 物品类别
    finder: str = ""             # 拾获人
    guest_phone: str = ""        # 宾客联系电话
    is_important: bool = False   # 是否贵重物品
    courier_company: str = ""    # 快递公司
    tracking_number: str = ""    # 快递运单号
    mailing_address: str = ""    # 邮寄地址
    detail_url: str = ""         # 详情页链接
    contact_url: str = ""        # 联系前台链接

    def to_dict(self) -> dict[str, Any]:
        """转为字典，供模板渲染使用"""
        return {
            "case_number": self.case_number,
            "guest_name": self.guest_name,
            "item_description": self.item_description,
            "discovery_date": self.discovery_date,
            "discovery_location": self.discovery_location,
            "status": self.status,
            "category": self.category or "其他",
            "finder": self.finder or "酒店员工",
            "guest_phone": self.guest_phone or "未登记",
            "is_important": self.is_important,
            "is_important_text": "是 — 已存入保险箱" if self.is_important else "否",
            "courier_company": self.courier_company or "",
            "tracking_number": self.tracking_number or "",
            "mailing_address": self.mailing_address or "",
            "detail_url": self.detail_url or "#",
            "contact_url": self.contact_url or "#",
            "hotel_name": HOTEL_NAME,
            "hotel_name_en": HOTEL_NAME_EN,
            "hotel_phone": HOTEL_PHONE,
            "hotel_address": HOTEL_ADDRESS,
        }


# ---------------------------------------------------------------------------
# Jinja2 环境初始化
# ---------------------------------------------------------------------------

def _create_jinja_env() -> Environment:
    """创建 Jinja2 模板环境"""
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


_jinja_env: Environment | None = None


def _get_jinja_env() -> Environment:
    """获取或创建 Jinja2 环境（懒加载单例）"""
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = _create_jinja_env()
    return _jinja_env


def _load_card_template(filename: str) -> str:
    """加载飞书卡片 JSON 模板文件"""
    filepath = _TEMPLATE_DIR / filename
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# 行李寄存凭证 — 多渠道渲染
# ---------------------------------------------------------------------------

class LuggageVoucherRenderer:
    """
    行李寄存凭证渲染器

    提供四种渠道的渲染输出：飞书卡片、短信、微信模板消息、HTML。
    """

    @staticmethod
    def render_feishu_card(data: LuggageVoucherData) -> dict[str, Any]:
        """
        渲染飞书交互卡片 JSON。

        Args:
            data: 行李寄存凭证数据

        Returns:
            完整的飞书卡片 JSON 字典，可直接通过 Bot Message API 发送
        """
        ctx = data.to_dict()
        # 加载 JSON 模板并用 Jinja2 渲染
        template_str = _load_card_template("luggage_card.json")
        env = _get_jinja_env()
        template = env.from_string(template_str)
        rendered = template.render(**ctx)

        try:
            card = json.loads(rendered)
        except json.JSONDecodeError as exc:
            logger.error("飞书卡片 JSON 渲染失败: %s", exc)
            # 降级：返回基础卡片结构
            card = _fallback_feishu_card(
                title="🧳 行李寄存凭证",
                content=(
                    f"**寄存编号：** {ctx['deposit_number']}\n"
                    f"**宾客：** {ctx['guest_name']} | **房间：** {ctx['room']}\n"
                    f"**件数：** {ctx['item_count']} 件 | **类型：** {ctx['storage_type']}\n"
                    f"**寄存时间：** {ctx['deposit_time']}\n"
                    f"**预计提取：** {ctx['expected_pickup']}"
                ),
            )
        return card

    @staticmethod
    def render_sms(data: LuggageVoucherData) -> str:
        """
        渲染短信模板文本。

        短信内容控制在 70 字符以内（中文短信限制）。

        Args:
            data: 行李寄存凭证数据

        Returns:
            短信文本字符串
        """
        ctx = data.to_dict()
        # 构造精简短信内容
        sms = (
            f"【{HOTEL_NAME}】{ctx['guest_name']}您好，"
            f"您的行李寄存成功。编号:{ctx['deposit_number']}，"
            f"验证码:{ctx['verification_code']}，"
            f"预计{ctx['expected_pickup']}提取。"
            f"详情 s.xx.cn/{ctx['deposit_number']}"
        )
        # 检查长度，超长则截短
        if len(sms) > 70:
            sms = (
                f"【{HOTEL_NAME}】{ctx['guest_name']}您好，"
                f"行李寄存成功。编号:{ctx['deposit_number']}，"
                f"验证码:{ctx['verification_code']}。"
                f"详查 s.xx.cn/{ctx['deposit_number']}"
            )
        return sms

    @staticmethod
    def render_wechat_template(data: LuggageVoucherData) -> dict[str, Any]:
        """
        渲染微信模板消息 JSON。

        Args:
            data: 行李寄存凭证数据

        Returns:
            微信模板消息字典，包含 touser / template_id / data 字段
        """
        ctx = data.to_dict()
        return {
            "template_id": "LUGGAGE_STORAGE_VOUCHER",
            "url": ctx["detail_url"],
            "data": {
                "first": {
                    "value": "行李寄存凭证",
                    "color": "#173177",
                },
                "keyword1": {
                    "value": ctx["deposit_number"],
                    "color": "#173177",
                },
                "keyword2": {
                    "value": ctx["guest_name"],
                    "color": "#173177",
                },
                "keyword3": {
                    "value": f"{ctx['room']}  |  {ctx['item_count']}件",
                    "color": "#173177",
                },
                "keyword4": {
                    "value": ctx["deposit_time"],
                    "color": "#173177",
                },
                "keyword5": {
                    "value": ctx["expected_pickup"],
                    "color": "#173177",
                },
                "remark": {
                    "value": (
                        f"验证码：{ctx['verification_code']}\n"
                        f"寄存位置：{ctx['storage_location']}\n"
                        f"请妥善保管凭证，提取时需出示验证码。"
                    ),
                    "color": "#666666",
                },
            },
            "miniprogram": {
                "appid": "",
                "pagepath": f"/pages/luggage/detail?id={ctx['deposit_number']}",
            },
        }

    @staticmethod
    def render_html(data: LuggageVoucherData) -> str:
        """
        渲染自包含 HTML 凭证（适用于邮件发送或打印）。

        Args:
            data: 行李寄存凭证数据

        Returns:
            完整的 HTML 字符串
        """
        ctx = data.to_dict()
        env = _get_jinja_env()
        template = env.get_template("luggage_voucher.html")
        return template.render(**ctx)


# ---------------------------------------------------------------------------
# 遗留物品凭证 — 多渠道渲染
# ---------------------------------------------------------------------------

class LostFoundVoucherRenderer:
    """
    遗留物品凭证渲染器

    提供四种渠道的渲染输出：飞书卡片、短信、微信模板消息、HTML。
    """

    @staticmethod
    def render_feishu_card(data: LostFoundVoucherData) -> dict[str, Any]:
        """
        渲染飞书交互卡片 JSON。

        Args:
            data: 遗留物品凭证数据

        Returns:
            完整的飞书卡片 JSON 字典
        """
        ctx = data.to_dict()
        template_str = _load_card_template("lost_found_card.json")
        env = _get_jinja_env()
        template = env.from_string(template_str)
        rendered = template.render(**ctx)

        try:
            card = json.loads(rendered)
        except json.JSONDecodeError as exc:
            logger.error("飞书卡片 JSON 渲染失败: %s", exc)
            card = _fallback_feishu_card(
                title="🔍 遗留物品凭证",
                content=(
                    f"**案件编号：** {ctx['case_number']}\n"
                    f"**宾客：** {ctx['guest_name']}\n"
                    f"**物品：** {ctx['item_description']}\n"
                    f"**发现地点：** {ctx['discovery_location']}\n"
                    f"**发现日期：** {ctx['discovery_date']}\n"
                    f"**状态：** {ctx['status']}"
                ),
            )
        return card

    @staticmethod
    def render_sms(data: LostFoundVoucherData) -> str:
        """
        渲染短信模板文本。

        短信内容控制在 70 字符以内。

        Args:
            data: 遗留物品凭证数据

        Returns:
            短信文本字符串
        """
        ctx = data.to_dict()
        sms = (
            f"【{HOTEL_NAME}】{ctx['guest_name']}您好，"
            f"您在酒店遗留物品已登记（编号:{ctx['case_number']}），"
            f"请联系前台领取。电话:{HOTEL_PHONE} "
            f"s.xx.cn/{ctx['case_number']}"
        )
        if len(sms) > 70:
            sms = (
                f"【{HOTEL_NAME}】{ctx['guest_name']}您好，"
                f"您有遗留物品待领取，编号:{ctx['case_number']}，"
                f"请联系前台{HOTEL_PHONE}。"
                f"详情 s.xx.cn/{ctx['case_number']}"
            )
        return sms

    @staticmethod
    def render_wechat_template(data: LostFoundVoucherData) -> dict[str, Any]:
        """
        渲染微信模板消息 JSON。

        Args:
            data: 遗留物品凭证数据

        Returns:
            微信模板消息字典
        """
        ctx = data.to_dict()
        return {
            "template_id": "LOST_FOUND_VOUCHER",
            "url": ctx["detail_url"],
            "data": {
                "first": {
                    "value": "遗留物品通知",
                    "color": "#C0392B",
                },
                "keyword1": {
                    "value": ctx["case_number"],
                    "color": "#173177",
                },
                "keyword2": {
                    "value": ctx["guest_name"],
                    "color": "#173177",
                },
                "keyword3": {
                    "value": ctx["item_description"],
                    "color": "#173177",
                },
                "keyword4": {
                    "value": ctx["discovery_location"],
                    "color": "#173177",
                },
                "keyword5": {
                    "value": ctx["discovery_date"],
                    "color": "#173177",
                },
                "keyword6": {
                    "value": ctx["status"],
                    "color": "#E67E22",
                },
                "remark": {
                    "value": (
                        f"请联系酒店前台领取遗留物品。\n"
                        f"酒店电话：{HOTEL_PHONE}\n"
                        f"领取时请携带有效身份证件。"
                    ),
                    "color": "#666666",
                },
            },
            "miniprogram": {
                "appid": "",
                "pagepath": f"/pages/lost-found/detail?id={ctx['case_number']}",
            },
        }

    @staticmethod
    def render_html(data: LostFoundVoucherData) -> str:
        """
        渲染自包含 HTML 凭证。

        Args:
            data: 遗留物品凭证数据

        Returns:
            完整的 HTML 字符串
        """
        ctx = data.to_dict()
        env = _get_jinja_env()
        template = env.get_template("lost_found_voucher.html")
        return template.render(**ctx)


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------

def render_luggage_voucher(
    data: LuggageVoucherData,
    channel: str = "html",
) -> str | dict[str, Any]:
    """
    一站式行李寄存凭证渲染函数。

    Args:
        data: 凭证数据
        channel: 输出渠道，可选 'feishu' / 'sms' / 'wechat' / 'html'

    Returns:
        渲染结果（str 或 dict）

    Raises:
        ValueError: 不支持的渠道
    """
    renderer = LuggageVoucherRenderer()
    match channel:
        case "feishu":
            return renderer.render_feishu_card(data)
        case "sms":
            return renderer.render_sms(data)
        case "wechat":
            return renderer.render_wechat_template(data)
        case "html":
            return renderer.render_html(data)
        case _:
            raise ValueError(f"不支持的渠道: {channel}")


def render_lost_found_voucher(
    data: LostFoundVoucherData,
    channel: str = "html",
) -> str | dict[str, Any]:
    """
    一站式遗留物品凭证渲染函数。

    Args:
        data: 凭证数据
        channel: 输出渠道，可选 'feishu' / 'sms' / 'wechat' / 'html'

    Returns:
        渲染结果（str 或 dict）

    Raises:
        ValueError: 不支持的渠道
    """
    renderer = LostFoundVoucherRenderer()
    match channel:
        case "feishu":
            return renderer.render_feishu_card(data)
        case "sms":
            return renderer.render_sms(data)
        case "wechat":
            return renderer.render_wechat_template(data)
        case "html":
            return renderer.render_html(data)
        case _:
            raise ValueError(f"不支持的渠道: {channel}")


# ---------------------------------------------------------------------------
# 内部工具函数
# ---------------------------------------------------------------------------

def _fallback_feishu_card(title: str, content: str) -> dict[str, Any]:
    """
    构造降级的飞书卡片 — 当 JSON 模板渲染失败时使用。

    Args:
        title: 卡片标题
        content: Markdown 正文内容

    Returns:
        最小可用的飞书卡片 JSON
    """
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": "blue",
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": content}},
            {"tag": "hr"},
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": f"{HOTEL_NAME} | {HOTEL_PHONE}",
                    }
                ],
            },
        ],
    }


# ---------------------------------------------------------------------------
# 条码 / 二维码生成辅助
# ---------------------------------------------------------------------------

def generate_barcode_data(deposit_number: str) -> str:
    """
    生成条码数据字符串。

    直接使用寄存编号作为条码内容，实际渲染时可交给条码库（如 python-barcode）处理。

    Args:
        deposit_number: 寄存编号

    Returns:
        条码字符串
    """
    return deposit_number


def generate_qr_data(deposit_number: str, verification_code: str) -> str:
    """
    生成二维码内容字符串。

    二维码内容为 JSON 格式，包含编号和验证码，供扫码设备解析。

    Args:
        deposit_number: 寄存编号
        verification_code: 提取验证码

    Returns:
        JSON 格式的二维码内容
    """
    return json.dumps({
        "type": "luggage_deposit",
        "deposit_number": deposit_number,
        "verification_code": verification_code,
        "hotel": HOTEL_NAME,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }, ensure_ascii=False)


def generate_verification_code() -> str:
    """
    生成 6 位提取验证码（数字）。

    Returns:
        6 位数字验证码字符串
    """
    import secrets
    return f"{secrets.randbelow(1_000_000):06d}"
