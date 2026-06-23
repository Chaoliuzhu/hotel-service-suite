"""
快递站模式 — Express Station Pattern for Hotel Item Management
===============================================================

借鉴菜鸟驿站/丰巢的物品存取流程，适配酒店行李寄存+客遗管理。

核心原则: 存入拍照、取出扫码

┌─────┬──────────────────────┬─────────────────────────┐
│环节 │ 快递站               │ 酒店行李/客遗            │
├─────┼──────────────────────┼─────────────────────────┤
│存入 │ 扫码→拍照→上架→发短信│ 拍照→AI识别→贴标签→发凭证│
│取出 │ 报取件码→扫码→取走   │ 报编号/扫码→验证码→取走  │
│通知 │ 短信+APP推送         │ 飞书卡片+短信+微信        │
│超期 │ 3天催取→7天退回      │ 24h预警→72h上报→30天处理  │
└─────┴──────────────────────┴─────────────────────────┘

双入口架构:
  入口A (AI智能): 拍照发BOT → AI识别 → 确认 → 自动录入
  入口B (表单兜底): 多维表格表单 → 手动填写 → 写入主台账
"""

import subprocess
import json
import os
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta

from .quick_snap import (
    QuickSnapProcessor, SnapDepositRequest, SnapLostFoundRequest,
    AIRecognitionResult
)


# ============================================================
# 快递站模式主处理器
# ============================================================

class ExpressModeProcessor:
    """
    快递站模式处理器

    统一管理行李寄存和客遗物品的存取流程
    """

    def __init__(self, config=None):
        self.config = config
        self.snap = QuickSnapProcessor(config)
        self.luggage_app_token = "Atj6bOVJtaDGSjspKDqcx3Jqnfd"
        self.luggage_table_id = "tblMPvX3VKodb80I"
        self.lf_app_token = "JJpTbxNJgaVojJsfUItcmvq5nqf"
        self.lf_table_id = "tblgcBcPR9P8fina"

    # ----------------------------------------------------------
    # 存入流程 (必须拍照)
    # ----------------------------------------------------------

    def deposit_luggage(self, photo_local: str, guest_name: str,
                        room: str, phone: str = "", item_count: int = 1,
                        storage_type: str = "普通行李",
                        storage_location: str = "一楼行李房",
                        operator: str = "",
                        ai_result: AIRecognitionResult = None) -> dict:
        """
        行李寄存 — 存入流程

        步骤:
        1. 接收照片 + AI识别结果
        2. 生成寄存编号 LG-YYYYMMDD-XXX
        3. 生成验证码(4位)
        4. 写入多维表格
        5. 生成条码标签(打印指令)
        6. 生成电子凭证(飞书卡片)
        7. 返回完整结果

        返回: {
            "deposit_number": "LG-20260623-001",
            "verification_code": "5864",
            "barcode_data": "...",
            "status": "deposited",
            "label_tspl": "...",
            "voucher_card": {...}
        }
        """
        from barcode.generator import (
            generate_luggage_code, generate_verification_code,
            generate_barcode_base64, generate_qr_base64
        )
        from printer.thermal import generate_tspl_label, generate_printable_html

        # 1. 生成编号
        seq = self._get_today_seq("luggage")
        deposit_number = generate_luggage_code(seq)
        vc = generate_verification_code()

        # 2. 描述信息
        desc = ""
        if ai_result:
            desc = f"{ai_result.item_name}({ai_result.color})"
            if ai_result.description:
                desc = ai_result.description

        # 3. 写入多维表格
        fields = {
            "寄存单号": deposit_number,
            "宾客姓名": guest_name,
            "房号": room,
            "入住房号": room,
            "联系方式": phone,
            "寄存日期": datetime.now().strftime("%Y/%m/%d"),
            "寄存件数": item_count,
            "寄存类型": [storage_type],
            "寄存位置": [storage_location],
            "行李描述": desc,
            "标签打印状态": ["未打印"],
            "取件验证码": vc,
            "状态": ["待取"],
            "备注": f"经手人:{operator}" if operator else ""
        }

        record_id = self._bitable_create(self.luggage_app_token,
                                          self.luggage_table_id, fields)

        # 4. 生成条码标签
        today = datetime.now().strftime("%Y-%m-%d")
        info_lines = [
            f"宾客: {guest_name}",
            f"房号: {room}",
            f"件数: {item_count}件",
            f"类型: {storage_type}",
            f"位置: {storage_location}",
            f"验证码: {vc}",
            f"日期: {today}"
        ]
        label_tspl = generate_tspl_label(
            deposit_number, deposit_number,
            "行李寄存标签", "天津瑞湾开元名都酒店",
            info_lines
        )
        label_html = generate_printable_html(
            deposit_number, deposit_number,
            "行李寄存标签", "天津瑞湾开元名都酒店",
            info_lines
        )

        return {
            "deposit_number": deposit_number,
            "verification_code": vc,
            "record_id": record_id,
            "status": "deposited",
            "label_tspl": label_tspl,
            "label_html": label_html,
            "fields": fields
        }

    def register_lost_found(self, photo_local: str, finder: str,
                            location: str, item_name: str = "",
                            description: str = "", category: str = "",
                            room: str = "", guest_name: str = "",
                            guest_phone: str = "", operator: str = "",
                            ai_result: AIRecognitionResult = None) -> dict:
        """
        客遗物品 — 登记流程

        步骤:
        1. 接收照片 + AI识别结果
        2. 生成编号 LF-YYYYMMDD-XXX
        3. 写入多维表格
        4. 重要物品标记入保险箱
        5. 生成条码标签
        """
        from barcode.generator import generate_lost_found_code

        seq = self._get_today_seq("lost_found")
        case_number = generate_lost_found_code(seq)

        # 从AI结果或手动输入获取信息
        if ai_result:
            item_name = item_name or ai_result.item_name
            description = description or ai_result.description
            category = category or ai_result.category
            is_important = ai_result.is_valuable
        else:
            is_important = category in ["电子产品", "首饰珠宝", "证件文件"]

        # 重要物品默认放保险箱
        storage = "客房部保险箱" if is_important else "前厅部保管柜"

        fields = {
            "失物编号": case_number,
            "物品名称": item_name,
            "物品类别": [category] if category else [],
            "物品描述": description,
            "发现日期": datetime.now().strftime("%Y/%m/%d %H:%M"),
            "发现地点": location,
            "发现人": finder,
            "捡拾地点": [location] if location in ["客房", "大堂", "餐厅", "泳池", "停车场", "会议室"] else [],
            "宾客姓名": guest_name,
            "宾客联系方式": guest_phone,
            "重要物品": is_important,
            "储备保管位置": [storage],
            "物品状态": ["待认领"],
            "认领状态": ["待认领"],
            "捡拾人": [finder] if finder else []
        }

        record_id = self._bitable_create(self.lf_app_token,
                                          self.lf_table_id, fields)

        return {
            "case_number": case_number,
            "record_id": record_id,
            "is_important": is_important,
            "storage": storage,
            "status": "registered",
            "fields": fields
        }

    # ----------------------------------------------------------
    # 取出流程 (不拍照，仅扫码)
    # ----------------------------------------------------------

    def pickup_luggage(self, scan_input: str, verification_code: str,
                       claimer_name: str = "") -> dict:
        """
        行李取件 — 取出流程 (无需拍照)

        支持两种取件方式:
        1. 扫描条码/二维码 → 自动解析寄存单号
        2. 手动输入寄存单号 (如 LG-20260623-001)

        验证: 验证码必须匹配

        返回: {"status": "picked_up", "deposit_number": "...", ...}
        """
        # 解析编号 (条码扫描或手动输入)
        deposit_number = self._parse_scan_input(scan_input)

        # 查询记录
        record = self._bitable_find_by_number(
            self.luggage_app_token, self.luggage_table_id,
            "寄存单号", deposit_number
        )

        if not record:
            return {"status": "not_found", "error": f"未找到寄存记录: {deposit_number}"}

        # 验证验证码
        stored_code = record.get("取件验证码", "")
        if stored_code and stored_code.strip() != verification_code.strip():
            return {"status": "code_mismatch", "error": "验证码不匹配"}

        # 检查是否已取
        current_status = record.get("状态", [])
        if isinstance(current_status, list) and "已取" in current_status:
            return {"status": "already_picked", "error": "该行李已取走"}

        # 更新状态
        record_id = record.get("_record_id", record.get("record_id", ""))
        now = datetime.now()
        update_fields = {
            "状态": ["已取"],
            "取件日期": now.strftime("%Y/%m/%d"),
            "取件时间": now.strftime("%Y/%m/%d %H:%M"),
            "取件经办人": [claimer_name] if claimer_name else []
        }

        self._bitable_update(self.luggage_app_token, self.luggage_table_id,
                             record_id, update_fields)

        return {
            "status": "picked_up",
            "deposit_number": deposit_number,
            "guest_name": record.get("宾客姓名", ""),
            "room": record.get("房号", ""),
            "item_count": record.get("寄存件数", 0),
            "pickup_time": now.strftime("%Y-%m-%d %H:%M"),
            "claimer": claimer_name
        }

    def claim_lost_found(self, scan_input: str, claimer_name: str,
                         claim_method: str = "本人领取",
                         contact_phone: str = "") -> dict:
        """
        客遗物品认领 — 取出流程 (无需拍照)

        claim_method: 本人领取/代领/邮寄/逾期销毁
        """
        case_number = self._parse_scan_input(scan_input)

        record = self._bitable_find_by_number(
            self.lf_app_token, self.lf_table_id,
            "失物编号", case_number
        )

        if not record:
            return {"status": "not_found", "error": f"未找到客遗记录: {case_number}"}

        current_status = record.get("物品状态", [])
        if isinstance(current_status, list) and current_status[0] in ["已认领", "已销毁", "已移交公安"]:
            return {"status": "already_claimed", "error": f"物品已{current_status[0]}"}

        record_id = record.get("_record_id", record.get("record_id", ""))
        update_fields = {
            "物品状态": ["已认领"],
            "认领状态": ["已认领"],
            "认领时间": datetime.now().strftime("%Y/%m/%d"),
            "领取签字备注": f"{claimer_name}({claim_method}) {datetime.now().strftime('%H:%M')}"
        }

        self._bitable_update(self.lf_app_token, self.lf_table_id,
                             record_id, update_fields)

        return {
            "status": "claimed",
            "case_number": case_number,
            "item_name": record.get("物品名称", ""),
            "claimer": claimer_name,
            "method": claim_method,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M")
        }

    # ----------------------------------------------------------
    # 超期管理 (借鉴快递站催取)
    # ----------------------------------------------------------

    def check_overdue(self, mode: str = "luggage",
                      hours_threshold: int = 24) -> list:
        """
        检查超期未取物品

        快递站催取规则 → 酒店适配:
        - 快递站: 3天催取 → 7天退回
        - 酒店行李: 24h预警 → 48h通知主管 → 72h上报
        - 酒店客遗: 30天提醒 → 60天公示 → 90天处理
        """
        if mode == "luggage":
            return self._check_luggage_overdue(hours_threshold)
        else:
            return self._check_lostfound_overdue()

    def _check_luggage_overdue(self, hours: int) -> list:
        """检查行李超期"""
        records = self._bitable_list(self.luggage_app_token,
                                      self.luggage_table_id,
                                      filter_status="待取")
        overdue = []
        cutoff = datetime.now() - timedelta(hours=hours)

        for r in records:
            deposit_date_str = r.get("寄存日期", "")
            if not deposit_date_str:
                continue
            try:
                deposit_date = datetime.strptime(
                    deposit_date_str.split(" ")[0], "%Y/%m/%d"
                )
                if deposit_date < cutoff:
                    overdue.append({
                        "deposit_number": r.get("寄存单号", ""),
                        "guest_name": r.get("宾客姓名", ""),
                        "room": r.get("房号", ""),
                        "phone": r.get("联系方式", ""),
                        "deposit_date": deposit_date_str,
                        "overdue_hours": int(
                            (datetime.now() - deposit_date).total_seconds() / 3600
                        ),
                        "level": self._overdue_level(
                            (datetime.now() - deposit_date).total_seconds() / 3600
                        )
                    })
            except ValueError:
                continue

        return sorted(overdue, key=lambda x: x["overdue_hours"], reverse=True)

    def _check_lostfound_overdue(self) -> list:
        """检查客遗物品超期"""
        records = self._bitable_list(self.lf_app_token,
                                      self.lf_table_id,
                                      filter_status="待认领")
        overdue = []
        now = datetime.now()

        for r in records:
            date_str = r.get("发现日期", "")
            if not date_str:
                continue
            try:
                found_date = datetime.strptime(
                    date_str.split(" ")[0], "%Y/%m/%d"
                )
                days = (now - found_date).days
                if days >= 30:
                    overdue.append({
                        "case_number": r.get("失物编号", ""),
                        "item_name": r.get("物品名称", ""),
                        "guest_name": r.get("宾客姓名", ""),
                        "found_date": date_str,
                        "days_since": days,
                        "stage": self._expiry_stage(days),
                        "is_important": r.get("重要物品", False)
                    })
            except ValueError:
                continue

        return sorted(overdue, key=lambda x: x["days_since"], reverse=True)

    @staticmethod
    def _overdue_level(hours: float) -> str:
        """行李超期等级"""
        if hours >= 72:
            return "🔴 严重超期(72h+)"
        elif hours >= 48:
            return "🟡 通知主管(48h+)"
        else:
            return "🟢 预警(24h+)"

    @staticmethod
    def _expiry_stage(days: int) -> str:
        """客遗超期阶段"""
        if days >= 90:
            return "🔴 可处理(90天+)"
        elif days >= 60:
            return "🟡 公示期(60天+)"
        else:
            return "🟢 提醒期(30天+)"

    # ----------------------------------------------------------
    # 今日统计
    # ----------------------------------------------------------

    def today_stats(self) -> dict:
        """今日存取统计 (类似快递站日报)"""
        today = datetime.now().strftime("%Y/%m/%d")

        luggage_records = self._bitable_list(
            self.luggage_app_token, self.luggage_table_id
        )
        lf_records = self._bitable_list(
            self.lf_app_token, self.lf_table_id
        )

        stats = {
            "date": today,
            "luggage": {
                "deposited_today": 0,
                "picked_today": 0,
                "currently_stored": 0,
                "overdue": 0
            },
            "lost_found": {
                "registered_today": 0,
                "claimed_today": 0,
                "pending": 0,
                "important_items": 0
            }
        }

        for r in luggage_records:
            deposit_date = r.get("寄存日期", "")
            status = r.get("状态", [])
            if isinstance(status, list):
                status = status[0] if status else ""
            if today in str(deposit_date):
                stats["luggage"]["deposited_today"] += 1
            if status == "待取":
                stats["luggage"]["currently_stored"] += 1

        for r in lf_records:
            status = r.get("物品状态", [])
            if isinstance(status, list):
                status = status[0] if status else ""
            if status == "待认领":
                stats["lost_found"]["pending"] += 1
            if r.get("重要物品", False) and status == "待认领":
                stats["lost_found"]["important_items"] += 1

        return stats

    # ----------------------------------------------------------
    # 消息处理入口
    # ----------------------------------------------------------

    def handle_bot_message(self, msg_type: str, content: str,
                           image_keys: list, sender_name: str = "",
                           chat_id: str = "") -> dict:
        """
        处理飞书BOT收到的消息 — 统一入口

        msg_type: "image" | "text" | "interactive"
        content: 文本内容或XML
        image_keys: 图片file_key列表

        返回: {"action": "...", "card": {...}} 或 {"action": "text", "text": "..."}
        """
        detected = self.snap.detect_message_type(msg_type, content, image_keys)

        if detected == "snap_luggage":
            # 图片消息 → 随手拍行李寄存
            return {
                "action": "snap_luggage",
                "hint": "收到照片，正在AI识别中...",
                "image_keys": image_keys
            }

        elif detected == "snap_lost_found":
            return {
                "action": "snap_lost_found",
                "hint": "收到照片，正在识别遗留物品...",
                "image_keys": image_keys
            }

        elif detected == "pickup":
            # 取件 — 解析编号和验证码
            # 支持格式: "取行李 LG-20260623-001 验证码5864"
            # 或: "取行李 001 5864" (简写)
            return {
                "action": "pickup_prompt",
                "text": (
                    "📦 **行李取件**\n\n"
                    "请提供以下信息:\n"
                    "1. 扫描行李标签条码\n"
                    "2. 或输入寄存单号(如 LG-20260623-001)\n"
                    "3. 以及4位取件验证码\n\n"
                    "示例: `取行李 LG-20260623-001 5864`"
                )
            }

        elif detected in ("text_deposit_luggage", "text_deposit_lost"):
            return {
                "action": "deposit_prompt",
                "mode": "luggage" if "luggage" in detected else "lost_found",
                "text": (
                    "📸 **请拍照**\n\n"
                    "请直接拍摄物品照片发送给我，"
                    "我会自动识别并帮你完成登记。\n\n"
                    "💡 也可以手动输入: "
                    "`寄存 张三 1208 13800138000 2件 行李箱`"
                )
            }

        elif detected == "query":
            return {
                "action": "query_prompt",
                "text": (
                    "🔍 **查询**\n\n"
                    "支持查询:\n"
                    "- `查询 LG-20260623-001` (按编号)\n"
                    "- `查询 张三` (按宾客名)\n"
                    "- `查询 超期` (超期物品)\n"
                    "- `查询 今日` (今日统计)"
                )
            }

        else:
            # 未知消息 → 引导
            return {
                "action": "guide",
                "text": (
                    "🏨 **酒店物品管理助手**\n\n"
                    "支持以下操作:\n"
                    "📸 **拍照** → 自动识别并登记(随手拍)\n"
                    "📦 `寄存` → 行李寄存\n"
                    "🔍 `遗留` → 客遗物品登记\n"
                    "📤 `取行李` → 行李取件(扫码)\n"
                    "🔎 `查询` → 查询记录\n\n"
                    "💡 直接拍照最快!"
                )
            }

    # ----------------------------------------------------------
    # 内部辅助方法
    # ----------------------------------------------------------

    def _parse_scan_input(self, scan_input: str) -> str:
        """解析条码扫描或手动输入，提取编号"""
        scan_input = scan_input.strip()
        # 条码扫描通常直接返回编号
        if scan_input.startswith("LG-") or scan_input.startswith("LF-"):
            return scan_input
        # 手动输入可能带空格
        parts = scan_input.split()
        for p in parts:
            if p.startswith("LG-") or p.startswith("LF-"):
                return p
        return scan_input

    def _get_today_seq(self, mode: str) -> int:
        """获取今日序号 (用于编号自增)"""
        today = datetime.now().strftime("%Y%m%d")
        if mode == "luggage":
            records = self._bitable_list(
                self.luggage_app_token, self.luggage_table_id
            )
        else:
            records = self._bitable_list(
                self.lf_app_token, self.lf_table_id
            )

        count = 0
        for r in records:
            num_field = "寄存单号" if mode == "luggage" else "失物编号"
            num = r.get(num_field, "")
            if today in str(num):
                count += 1
        return count + 1

    def _bitable_create(self, app_token: str, table_id: str,
                        fields: dict) -> str:
        """创建多维表格记录 (通过临时文件传递JSON避免shell拆分)"""
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(fields, tmp, ensure_ascii=False)
            tmp_path = tmp.name

        try:
            cmd = [
                "lark-cli", "base", "+record-upsert",
                "--base-token", app_token,
                "--table-id", table_id,
                "--json-file", tmp_path,
                "--as", "bot"
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                try:
                    data = json.loads(r.stdout)
                    return data.get("data", {}).get("record_id", "created")
                except json.JSONDecodeError:
                    return "created"
            # Fallback: 如果 --json-file 不支持, 用逐字段方式
            return self._bitable_create_fallback(app_token, table_id, fields)
        finally:
            os.unlink(tmp_path)

    def _bitable_create_fallback(self, app_token: str, table_id: str,
                                  fields: dict) -> str:
        """Fallback: 逐字段传递创建记录"""
        # 构建 --field 参数列表
        field_args = []
        for k, v in fields.items():
            if isinstance(v, list):
                val = json.dumps(v, ensure_ascii=False)
            elif isinstance(v, bool):
                val = "true" if v else "false"
            else:
                val = str(v)
            field_args.extend(["--field", f"{k}={val}"])

        cmd = [
            "lark-cli", "base", "+record-upsert",
            "--base-token", app_token,
            "--table-id", table_id,
            "--as", "bot"
        ] + field_args

        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            try:
                data = json.loads(r.stdout)
                return data.get("data", {}).get("record_id", "created")
            except json.JSONDecodeError:
                return "created"
        raise RuntimeError(f"创建记录失败: {r.stderr[:200]}")

    def _bitable_update(self, app_token: str, table_id: str,
                        record_id: str, fields: dict) -> bool:
        """更新多维表格记录"""
        cmd = [
            "lark-cli", "base", "+record-batch-update",
            "--base-token", app_token,
            "--table-id", table_id,
            "--record-id", record_id,
            "--json", json.dumps(fields, ensure_ascii=False),
            "--as", "bot"
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return r.returncode == 0

    def _bitable_list(self, app_token: str, table_id: str,
                      filter_status: str = "", limit: int = 200) -> list:
        """列出多维表格记录"""
        cmd = [
            "lark-cli", "base", "+record-list",
            "--base-token", app_token,
            "--table-id", table_id,
            "--limit", str(limit),
            "--as", "bot",
            "--format", "json"
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return []
        try:
            data = json.loads(r.stdout)
            records = data.get("data", {}).get("items", [])
            if filter_status:
                records = [
                    rec for rec in records
                    if filter_status in str(rec.get("状态", []))
                    or filter_status in str(rec.get("物品状态", []))
                ]
            return records
        except json.JSONDecodeError:
            return []

    def _bitable_find_by_number(self, app_token: str, table_id: str,
                                 field_name: str, number: str) -> dict:
        """按编号查找记录"""
        records = self._bitable_list(app_token, table_id)
        for r in records:
            if r.get(field_name, "") == number:
                return r
        return {}
