"""
bitable.client — 飞书多维表格 (Bitable) 客户端封装

通过 subprocess 调用 lark-cli 的 base 命令族，对多维表格记录进行增删改查操作。
包含重试逻辑、JSON 解析、统一错误处理。
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 异常定义
# ---------------------------------------------------------------------------

class BitableError(Exception):
    """多维表格操作通用异常"""

    def __init__(self, message: str, command: str = "", returncode: int = -1):
        super().__init__(message)
        self.command = command
        self.returncode = returncode


class BitableRetryError(BitableError):
    """重试次数耗尽后抛出的异常"""


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BitableConfig:
    """客户端配置"""

    lark_cli_path: str = "lark-cli"
    max_retries: int = 3
    retry_delay: float = 1.0          # 初始重试间隔（秒）
    retry_backoff: float = 2.0        # 退避倍数
    timeout: int = 30                 # 单次命令超时（秒）
    extra_env: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 客户端
# ---------------------------------------------------------------------------

class BitableClient:
    """
    飞书多维表格客户端 — 封装 lark-cli base 命令族。

    所有公开方法均通过 ``subprocess.run`` 调用 lark-cli，解析其 JSON 输出，
    并在遇到瞬态错误时自动重试。

    用法::

        client = BitableClient()
        records = client.list_records("appTOKEN", "tblXXXX")
        rid = client.create_record("appTOKEN", "tblXXXX", {"字段1": "值"})
    """

    def __init__(self, config: BitableConfig | None = None) -> None:
        self._cfg = config or BitableConfig()

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def list_records(
        self,
        app_token: str,
        table_id: str,
        filters: dict[str, Any] | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """
        获取多维表格记录列表。

        Args:
            app_token: 多维表格 app_token
            table_id: 数据表 ID
            filters: 可选筛选条件（将拼接为 --filter 参数）
            limit: 最大返回记录数，默认 200

        Returns:
            记录字典列表，每条记录包含 record_id 和 fields

        Raises:
            BitableError: 命令执行失败
        """
        cmd = [
            self._cfg.lark_cli_path, "base", "+record-list",
            "--app-token", app_token,
            "--table-id", table_id,
            "--limit", str(limit),
        ]
        if filters:
            # 将筛选条件序列化为 JSON 字符串传给 --filter
            cmd.extend(["--filter", json.dumps(filters, ensure_ascii=False)])

        result = self._run(cmd)
        items = result.get("items") or result.get("records") or result.get("data") or []
        if not isinstance(items, list):
            items = [items]
        return items

    def create_record(
        self,
        app_token: str,
        table_id: str,
        fields: dict[str, Any],
    ) -> str:
        """
        创建一条多维表格记录。

        Args:
            app_token: 多维表格 app_token
            table_id: 数据表 ID
            fields: 字段名 → 值 映射

        Returns:
            新建记录的 record_id

        Raises:
            BitableError: 命令执行失败或返回值中缺少 record_id
        """
        cmd = [
            self._cfg.lark_cli_path, "base", "+record-create",
            "--app-token", app_token,
            "--table-id", table_id,
            "--fields", json.dumps(fields, ensure_ascii=False),
        ]
        result = self._run(cmd)

        # 尝试从多种可能的字段中提取 record_id
        record_id = (
            result.get("record_id")
            or result.get("recordId")
            or result.get("id")
            or ""
        )
        if not record_id:
            # 部分 lark-cli 版本把 record 嵌套在 data 里
            nested = result.get("data") or result.get("record") or {}
            record_id = nested.get("record_id") or nested.get("recordId") or nested.get("id") or ""
        if not record_id:
            raise BitableError(
                f"无法从返回结果中提取 record_id: {json.dumps(result, ensure_ascii=False)}",
                command=" ".join(cmd),
            )
        return record_id

    def update_record(
        self,
        app_token: str,
        table_id: str,
        record_id: str,
        fields: dict[str, Any],
    ) -> bool:
        """
        更新一条多维表格记录。

        Args:
            app_token: 多维表格 app_token
            table_id: 数据表 ID
            record_id: 待更新记录 ID
            fields: 需要更新的字段名 → 值 映射

        Returns:
            更新是否成功

        Raises:
            BitableError: 命令执行失败
        """
        cmd = [
            self._cfg.lark_cli_path, "base", "+record-update",
            "--app-token", app_token,
            "--table-id", table_id,
            "--record-id", record_id,
            "--fields", json.dumps(fields, ensure_ascii=False),
        ]
        self._run(cmd)
        return True

    def get_record(
        self,
        app_token: str,
        table_id: str,
        record_id: str,
    ) -> dict[str, Any]:
        """
        获取单条多维表格记录详情。

        Args:
            app_token: 多维表格 app_token
            table_id: 数据表 ID
            record_id: 记录 ID

        Returns:
            包含 record_id 和 fields 的记录字典

        Raises:
            BitableError: 命令执行失败
        """
        cmd = [
            self._cfg.lark_cli_path, "base", "+record-get",
            "--app-token", app_token,
            "--table-id", table_id,
            "--record-id", record_id,
        ]
        return self._run(cmd)

    def count_records(
        self,
        app_token: str,
        table_id: str,
        filter_formula: str | None = None,
    ) -> int:
        """
        统计多维表格记录数量。

        Args:
            app_token: 多维表格 app_token
            table_id: 数据表 ID
            filter_formula: 可选筛选公式（飞书公式语法）

        Returns:
            记录总数

        Raises:
            BitableError: 命令执行失败
        """
        cmd = [
            self._cfg.lark_cli_path, "base", "+record-count",
            "--app-token", app_token,
            "--table-id", table_id,
        ]
        if filter_formula:
            cmd.extend(["--filter", filter_formula])

        result = self._run(cmd)
        count = result.get("count") or result.get("total") or result.get("data")
        if isinstance(count, int):
            return count
        if isinstance(count, str) and count.isdigit():
            return int(count)
        # 如果接口返回的是记录列表，则直接计数
        items = result.get("items") or result.get("records") or result.get("data") or []
        if isinstance(items, list):
            return len(items)
        raise BitableError(
            f"无法从返回结果中解析记录数: {json.dumps(result, ensure_ascii=False)}",
            command=" ".join(cmd),
        )

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _run(self, cmd: list[str]) -> dict[str, Any]:
        """
        执行 lark-cli 命令，解析 JSON 输出，带重试逻辑。

        重试策略：
        - 仅对非零退出码且错误信息包含瞬态关键字（timeout, throttle, 5xx 等）时重试
        - 使用指数退避
        - 超过最大重试次数后抛出 BitableRetryError

        Args:
            cmd: 命令及参数列表

        Returns:
            解析后的 JSON 字典

        Raises:
            BitableRetryError: 重试耗尽
            BitableError: 非瞬态错误
        """
        last_error: Exception | None = None
        delay = self._cfg.retry_delay

        for attempt in range(1, self._cfg.max_retries + 1):
            try:
                env = None
                if self._cfg.extra_env:
                    import os
                    env = {**os.environ, **self._cfg.extra_env}

                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self._cfg.timeout,
                    env=env,
                )

                if proc.returncode == 0:
                    return self._parse_output(proc.stdout)

                stderr = proc.stderr.strip()
                logger.warning(
                    "lark-cli 命令失败 (attempt %d/%d, rc=%d): %s",
                    attempt, self._cfg.max_retries, proc.returncode, stderr,
                )

                if not self._is_transient(stderr, proc.returncode):
                    raise BitableError(
                        f"lark-cli 执行失败 (rc={proc.returncode}): {stderr}",
                        command=" ".join(cmd),
                        returncode=proc.returncode,
                    )

                last_error = BitableError(stderr, command=" ".join(cmd), returncode=proc.returncode)

            except subprocess.TimeoutExpired as exc:
                logger.warning(
                    "lark-cli 命令超时 (attempt %d/%d, timeout=%ds)",
                    attempt, self._cfg.max_retries, self._cfg.timeout,
                )
                last_error = exc

            except json.JSONDecodeError as exc:
                # JSON 解析错误不重试
                raise BitableError(
                    f"lark-cli 输出 JSON 解析失败: {exc}",
                    command=" ".join(cmd),
                ) from exc

            if attempt < self._cfg.max_retries:
                logger.info("等待 %.1f 秒后重试...", delay)
                time.sleep(delay)
                delay *= self._cfg.retry_backoff

        raise BitableRetryError(
            f"lark-cli 命令重试 {self._cfg.max_retries} 次后仍失败: {last_error}",
            command=" ".join(cmd),
        )

    @staticmethod
    def _parse_output(stdout: str) -> dict[str, Any]:
        """
        解析 lark-cli 的 stdout 为字典。

        lark-cli 可能在 JSON 前后输出日志行，因此逐行从后往前查找有效 JSON。
        """
        stdout = stdout.strip()
        if not stdout:
            return {}

        # 先尝试直接解析
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            pass

        # 从后向前逐行查找 JSON 对象
        lines = stdout.splitlines()
        json_lines: list[str] = []
        brace_depth = 0
        found_end = False

        for line in reversed(lines):
            stripped = line.strip()
            if not found_end:
                if stripped.endswith("}"):
                    found_end = True
                else:
                    continue
            json_lines.insert(0, line)
            brace_depth += stripped.count("{") - stripped.count("}")
            if brace_depth == 0 and found_end:
                break

        if json_lines:
            candidate = "\n".join(json_lines)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        # 最终兜底：查找第一个 { 和最后一个 }
        start = stdout.find("{")
        end = stdout.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(stdout[start : end + 1])

        raise json.JSONDecodeError("无法从 lark-cli 输出中提取有效 JSON", stdout, 0)

    @staticmethod
    def _is_transient(stderr: str, returncode: int) -> bool:
        """
        判断错误是否为瞬态错误，值得重试。

        瞬态错误包括：
        - HTTP 429 (限流) / 5xx (服务端错误)
        - 超时
        - 网络连接问题
        """
        transient_keywords = [
            "timeout", "throttle", "rate limit", "too many requests",
            "connection refused", "connection reset", "eof",
            "500", "502", "503", "504", "429",
            "internal server error", "bad gateway", "service unavailable",
        ]
        lower = stderr.lower()
        return any(kw in lower for kw in transient_keywords)

    def __repr__(self) -> str:
        return (
            f"BitableClient(cli={self._cfg.lark_cli_path!r}, "
            f"retries={self._cfg.max_retries}, timeout={self._cfg.timeout})"
        )
