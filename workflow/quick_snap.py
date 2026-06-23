"""
随手拍 — AI Photo Recognition for Hotel Item Registration
==========================================================

核心流程:
  1. 员工拍照发到飞书BOT
  2. AI分析照片 → 提取物品信息
  3. 系统生成确认卡片（含预填数据）
  4. 员工确认或修改 → 自动写入多维表格
  5. 同时生成条码标签 + 电子凭证

双入口架构:
  入口A (AI Bot): 拍照 → AI识别 → 自动填报 → 确认卡片
  入口B (表单兜底): 多维表格收集表单 → 手动填写 → 自动同步主台账

借鉴快递站原则:
  存入环节: 必须拍照 → AI识别 → 贴标签 → 发凭证
  取出环节: 仅需扫码/报号 → 验证码匹配 → 自动核销 → 无需拍照
"""

import subprocess
import json
import os
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


# ============================================================
# 数据结构
# ============================================================

@dataclass
class AIRecognitionResult:
    """AI视觉识别结果"""
    item_name: str          # 物品名称 (行李箱/手机/背包...)
    category: str           # 物品类别
    description: str        # 详细描述
    color: str              # 主要颜色
    brand: Optional[str]    # 品牌 (如可识别)
    condition: str          # 物品状态 (全新/九成新/有使用痕迹/破损)
    is_valuable: bool       # 是否贵重物品
    confidence: float       # 置信度 0~1
    raw_analysis: str       # AI原始分析文本


@dataclass
class SnapDepositRequest:
    """随手拍 — 行李寄存请求"""
    photo_url: str = ""
    photo_local: str = ""       # 本地下载路径
    guest_name: str = ""
    room: str = ""
    phone: str = ""
    item_count: int = 1
    storage_type: str = "普通行李"
    storage_location: str = "一楼行李房"
    operator: str = ""
    ai_result: Optional[AIRecognitionResult] = None


@dataclass
class SnapLostFoundRequest:
    """随手拍 — 客遗物品请求"""
    photo_url: str = ""
    photo_local: str = ""
    finder: str = ""
    location: str = ""          # 发现地点
    room: str = ""
    guest_name: str = ""
    guest_phone: str = ""
    operator: str = ""
    ai_result: Optional[AIRecognitionResult] = None


# ============================================================
# AI识别Prompt模板
# ============================================================

PROMPT_LUGGAGE = """请分析这张行李/物品照片，提取以下信息用于酒店行李寄存登记：

1. 物品名称（如：行李箱、背包、手提袋、纸箱、高尔夫球包等）
2. 物品类别：普通行李/贵重行李/大件箱包/易碎物品
3. 详细描述（颜色、尺寸、品牌标识、显著特征、材质）
4. 主要颜色
5. 品牌（如可识别，否则填"未知"）
6. 物品状态：全新/九成新/有使用痕迹/有破损
7. 是否属于贵重物品（含电子产品/奢侈品/珠宝/现金 → true）

请以严格JSON格式返回:
{
  "item_name": "...",
  "category": "普通行李|贵重行李|大件箱包|易碎物品",
  "description": "...",
  "color": "...",
  "brand": "..." 或 null,
  "condition": "...",
  "is_valuable": true/false
}"""

PROMPT_LOST_FOUND = """请分析这张遗留物品照片，提取以下信息用于酒店失物招领登记：

1. 物品名称（如：手机、钱包、衣物、证件、充电器、钥匙等）
2. 物品类别：电子产品/首饰珠宝/证件文件/衣物包袋/其他
3. 详细描述（颜色、品牌、型号、显著特征、磨损/破损程度）
4. 主要颜色
5. 品牌（如可识别，否则填"未知"）
6. 物品状态：完好/有使用痕迹/破损/有污渍
7. 是否属于重要物品（电子产品/首饰珠宝/证件文件 → true，需当天18:00前入保险箱）

请以严格JSON格式返回:
{
  "item_name": "...",
  "category": "电子产品|首饰珠宝|证件文件|衣物包袋|其他",
  "description": "...",
  "color": "...",
  "brand": "..." 或 null,
  "condition": "...",
  "is_valuable": true/false
}"""


# ============================================================
# 核心处理器
# ============================================================

class QuickSnapProcessor:
    """
    随手拍处理器

    借鉴快递站模式:
    - 存入: 必须拍照 → AI识别 → 自动填报 → 生成条码 → 打印标签 → 发凭证
    - 取出: 仅需扫码/报号 → 验证码匹配 → 自动核销 → 无需拍照

    双入口:
    - 入口A (AI Bot): 拍照发消息 → AI识别+自动填报 → 确认卡片
    - 入口B (表单兜底): 多维表格收集表单 → 手动填写 → 写入主台账
    """

    def __init__(self, config=None, bot_app_id: str = ""):
        self.config = config
        self.bot_app_id = bot_app_id

    # ----------------------------------------------------------
    # 1. 图片下载
    # ----------------------------------------------------------

    def download_photo(self, message_id: str, file_key: str,
                       output_dir: str = "/tmp/snap_photos") -> str:
        """
        从飞书消息下载图片到本地

        使用 lark-cli im +messages-resources-download
        返回本地文件路径
        """
        os.makedirs(output_dir, exist_ok=True)
        cmd = [
            "lark-cli", "im", "+messages-resources-download",
            "--message-id", message_id,
            "--file-key", file_key,
            "--output", output_dir,
            "--as", "bot"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"图片下载失败: {result.stderr}")

        # 返回下载的文件路径
        expected = os.path.join(output_dir, file_key)
        for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
            path = expected + ext
            if os.path.exists(path):
                return path
        # 如果找不到带扩展名的，返回目录里最新文件
        files = sorted(
            [os.path.join(output_dir, f) for f in os.listdir(output_dir)],
            key=os.path.getmtime, reverse=True
        )
        return files[0] if files else expected

    # ----------------------------------------------------------
    # 2. AI视觉分析
    # ----------------------------------------------------------

    def build_analysis_prompt(self, context: str = "luggage") -> str:
        """根据场景返回AI分析prompt"""
        if context == "lost_found":
            return PROMPT_LOST_FOUND
        return PROMPT_LUGGAGE

    def parse_ai_response(self, ai_text: str, context: str = "luggage") -> AIRecognitionResult:
        """
        解析AI返回的JSON结果为结构化数据

        ai_text: AI返回的文本（可能包含JSON块）
        """
        # 尝试提取JSON
        json_str = ai_text
        if "```json" in ai_text:
            json_str = ai_text.split("```json")[1].split("```")[0]
        elif "```" in ai_text:
            json_str = ai_text.split("```")[1].split("```")[0]

        try:
            data = json.loads(json_str.strip())
        except json.JSONDecodeError:
            # 解析失败，返回待人工确认的结果
            return AIRecognitionResult(
                item_name="待人工确认",
                category="待确认",
                description=ai_text[:200],
                color="",
                brand=None,
                condition="",
                is_valuable=False,
                confidence=0.0,
                raw_analysis=ai_text
            )

        # 映射类别
        category_map_luggage = {
            "普通行李": "普通行李", "贵重行李": "贵重行李",
            "大件箱包": "大件箱包", "易碎物品": "易碎物品"
        }
        category_map_lf = {
            "电子产品": "电子产品", "首饰珠宝": "首饰珠宝",
            "证件文件": "证件文件", "衣物包袋": "衣物包袋", "其他": "其他"
        }

        cat_map = category_map_lf if context == "lost_found" else category_map_luggage
        raw_cat = data.get("category", "待确认")
        category = cat_map.get(raw_cat, raw_cat)

        return AIRecognitionResult(
            item_name=data.get("item_name", "待确认"),
            category=category,
            description=data.get("description", ""),
            color=data.get("color", ""),
            brand=data.get("brand"),
            condition=data.get("condition", ""),
            is_valuable=bool(data.get("is_valuable", False)),
            confidence=0.85,  # 成功解析JSON给较高置信度
            raw_analysis=ai_text
        )

    # ----------------------------------------------------------
    # 3. 确认卡片生成
    # ----------------------------------------------------------

    def generate_luggage_confirm_card(self, req: SnapDepositRequest,
                                       ai: AIRecognitionResult) -> dict:
        """生成行李寄存确认卡片（飞书交互卡片JSON）"""
        valuable_note = "⚠️ **贵重行李** — 请确认存放位置" if ai.is_valuable else ""
        brand_text = f" | 品牌: {ai.brand}" if ai.brand else ""

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "📦 行李寄存 — 随手拍AI识别"},
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**🤖 AI识别结果** (置信度: {ai.confidence:.0%})\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"**物品名称:** {ai.item_name}\n"
                            f"**物品类别:** {ai.category}\n"
                            f"**颜色:** {ai.color}{brand_text}\n"
                            f"**状态:** {ai.condition}\n"
                            f"**详细描述:** {ai.description}\n"
                            f"{valuable_note}"
                        )
                    }
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**👤 宾客信息**\n"
                            f"姓名: {req.guest_name or '(待填写)'} | "
                            f"房号: {req.room or '(待填写)'}\n"
                            f"电话: {req.phone or '(待填写)'} | "
                            f"件数: {req.item_count}\n"
                            f"寄存位置: {req.storage_location}\n"
                            f"经手人: {req.operator or '(当前用户)'}"
                        )
                    }
                },
                {"tag": "hr"},
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": "✅确认后将自动: ①生成条码标签 ②写入台账 ③打印标签 ④发送电子凭证"
                        }
                    ]
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "✅ 确认寄存"},
                            "type": "primary",
                            "value": {
                                "action": "confirm_deposit",
                                "mode": "luggage",
                                "ai_item": ai.item_name,
                                "ai_category": ai.category,
                                "ai_desc": ai.description
                            }
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "✏️ 我要修改"},
                            "type": "default",
                            "value": {"action": "edit_info", "mode": "luggage"}
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "❌ 取消"},
                            "type": "danger",
                            "value": {"action": "cancel", "mode": "luggage"}
                        }
                    ]
                }
            ]
        }

    def generate_lostfound_confirm_card(self, req: SnapLostFoundRequest,
                                         ai: AIRecognitionResult) -> dict:
        """生成客遗物品确认卡片"""
        important_note = ""
        if ai.is_valuable:
            important_note = "\n🔒 **重要物品** — 需当天18:00前存入保险箱!"

        brand_text = f" | 品牌: {ai.brand}" if ai.brand else ""

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "🔍 遗留物品 — 随手拍AI识别"},
                "template": "orange"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**🤖 AI识别结果** (置信度: {ai.confidence:.0%})\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"**物品名称:** {ai.item_name}\n"
                            f"**物品类别:** {ai.category}\n"
                            f"**颜色:** {ai.color}{brand_text}\n"
                            f"**状态:** {ai.condition}\n"
                            f"**详细描述:** {ai.description}"
                            f"{important_note}"
                        )
                    }
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**📍 发现信息**\n"
                            f"发现人: {req.finder or '(待填写)'} | "
                            f"地点: {req.location or '(待填写)'}\n"
                            f"宾客: {req.guest_name or '(待确认)'} | "
                            f"电话: {req.guest_phone or '(待确认)'}\n"
                            f"登记人: {req.operator or '(当前用户)'}"
                        )
                    }
                },
                {"tag": "hr"},
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": "✅确认后将自动: ①登记到台账 ②打印标签 ③通知宾客(如已联系) ④重要物品提醒入保险箱"
                        }
                    ]
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "✅ 确认登记"},
                            "type": "primary",
                            "value": {
                                "action": "confirm_register",
                                "mode": "lost_found",
                                "ai_item": ai.item_name,
                                "ai_category": ai.category,
                                "ai_desc": ai.description,
                                "ai_important": ai.is_valuable
                            }
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "✏️ 我要修改"},
                            "type": "default",
                            "value": {"action": "edit_info", "mode": "lost_found"}
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "❌ 取消"},
                            "type": "danger",
                            "value": {"action": "cancel", "mode": "lost_found"}
                        }
                    ]
                }
            ]
        }

    # ----------------------------------------------------------
    # 4. 消息路由
    # ----------------------------------------------------------

    def detect_message_type(self, msg_type: str, content: str,
                            image_keys: list) -> str:
        """
        识别飞书消息类型，路由到对应处理流程

        返回: "snap_luggage" | "snap_lost_found" | "pickup" |
              "query" | "text_deposit" | "unknown"
        """
        # 图片消息 → 随手拍
        if msg_type == "image" and image_keys:
            return "snap_luggage"  # 默认走行李，确认卡片里可切换

        # 文本命令
        text = content.lower().strip()
        keywords = {
            "寄存": "text_deposit_luggage",
            "行李寄存": "text_deposit_luggage",
            "遗留": "text_deposit_lost",
            "捡到": "text_deposit_lost",
            "客遗": "text_deposit_lost",
            "取行李": "pickup",
            "领取": "pickup",
            "取件": "pickup",
            "查询": "query",
            "查": "query",
        }

        for kw, action in keywords.items():
            if kw in text:
                return action

        return "unknown"


# ============================================================
# 多维表格表单兜底
# ============================================================

def create_bitable_fallback_forms(luggage_app_token: str, luggage_table_id: str,
                                   lf_app_token: str, lf_table_id: str) -> dict:
    """
    创建多维表格收集表单作为兜底入口

    当AI BOT不可用时，员工可直接打开表单链接手动填写
    表单提交后自动写入主台账，与AI入口数据完全一致

    返回: {"luggage_form_url": "...", "lost_found_form_url": "..."}
    """
    results = {}

    # 行李寄存表单
    luggage_cmd = [
        "lark-cli", "base", "+form-create",
        "--base-token", luggage_app_token,
        "--table-id", luggage_table_id,
        "--name", "行李寄存登记表单",
        "--as", "bot"
    ]
    r = subprocess.run(luggage_cmd, capture_output=True, text=True, timeout=30)
    if r.returncode == 0:
        data = json.loads(r.stdout) if r.stdout.startswith("{") else {}
        form_id = data.get("data", {}).get("form_id", "")
        results["luggage_form_url"] = (
            f"https://delonix.feishu.cn/base/{luggage_app_token}"
            f"?form={form_id}" if form_id else "创建失败"
        )
    else:
        results["luggage_form_url"] = f"创建失败: {r.stderr[:100]}"

    # 客遗物品表单
    lf_cmd = [
        "lark-cli", "base", "+form-create",
        "--base-token", lf_app_token,
        "--table-id", lf_table_id,
        "--name", "遗留物品登记表单",
        "--as", "bot"
    ]
    r = subprocess.run(lf_cmd, capture_output=True, text=True, timeout=30)
    if r.returncode == 0:
        data = json.loads(r.stdout) if r.stdout.startswith("{") else {}
        form_id = data.get("data", {}).get("form_id", "")
        results["lost_found_form_url"] = (
            f"https://delonix.feishu.cn/base/{lf_app_token}"
            f"?form={form_id}" if form_id else "创建失败"
        )
    else:
        results["lost_found_form_url"] = f"创建失败: {r.stderr[:100]}"

    return results
