"""
Hotel Service Suite - Core Configuration Module.

Provides centralized configuration management for all hotel service modules
including Feishu Bitable integration, printer settings, SMS gateway, and
WeChat service configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class BitableTableConfig:
    """Configuration for a single Feishu Bitable table."""

    app_token: str
    table_id: str

    def __post_init__(self) -> None:
        if not self.app_token:
            raise ValueError("app_token must not be empty")
        if not self.table_id:
            raise ValueError("table_id must not be empty")


@dataclass(frozen=True)
class BitableConfig:
    """Configuration for all Feishu Bitable integrations."""

    lost_found: BitableTableConfig
    luggage: BitableTableConfig

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BitableConfig:
        """Build a BitableConfig from a raw dictionary.

        Args:
            data: Dictionary with ``lost_found`` and ``luggage`` keys, each
                  containing ``app_token`` and ``table_id``.

        Returns:
            A fully validated :class:`BitableConfig` instance.
        """
        lost_found = BitableTableConfig(
            app_token=data["lost_found"]["app_token"],
            table_id=data["lost_found"]["table_id"],
        )
        luggage = BitableTableConfig(
            app_token=data["luggage"]["app_token"],
            table_id=data["luggage"]["table_id"],
        )
        return cls(lost_found=lost_found, luggage=luggage)


@dataclass(frozen=True)
class PrinterSettings:
    """Thermal printer connection and label settings."""

    ip: str = "192.168.1.100"
    port: int = 9100
    protocol: str = "tspl"
    label_width_mm: int = 75
    label_height_mm: int = 50

    def __post_init__(self) -> None:
        if self.protocol not in ("tspl", "zpl"):
            raise ValueError(
                f"Unsupported printer protocol: {self.protocol!r}. "
                "Must be 'tspl' or 'zpl'."
            )
        if not (1 <= self.port <= 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {self.port}")


@dataclass(frozen=True)
class FeishuBotConfig:
    """Feishu (Lark) bot application credentials."""

    app_id: str = ""
    app_secret: str = ""

    @property
    def is_configured(self) -> bool:
        """Return ``True`` when both credentials are present."""
        return bool(self.app_id and self.app_secret)


@dataclass(frozen=True)
class SMSGatewayConfig:
    """SMS gateway configuration (placeholder for future integration)."""

    provider: str = ""
    api_key: str = ""
    api_secret: str = ""
    sign_name: str = ""
    template_code: str = ""

    @property
    def is_configured(self) -> bool:
        """Return ``True`` when minimum required fields are present."""
        return bool(self.provider and self.api_key)


@dataclass(frozen=True)
class WeChatConfig:
    """WeChat Official Account / Mini-Program configuration (placeholder)."""

    app_id: str = ""
    app_secret: str = ""
    token: str = ""
    encoding_aes_key: str = ""

    @property
    def is_configured(self) -> bool:
        """Return ``True`` when minimum required fields are present."""
        return bool(self.app_id and self.app_secret)


@dataclass
class HotelServiceConfig:
    """Top-level configuration for the Hotel Service Suite.

    Loads settings from a YAML file (``config/settings.yaml`` by default) and
    exposes them as strongly-typed dataclass attributes.

    Attributes:
        bitable: Feishu Bitable tokens and table IDs.
        printer: Thermal printer connection settings.
        feishu_bot: Feishu bot credentials.
        sms: SMS gateway settings.
        wechat: WeChat integration settings.
    """

    bitable: BitableConfig
    printer: PrinterSettings = field(default_factory=PrinterSettings)
    feishu_bot: FeishuBotConfig = field(default_factory=FeishuBotConfig)
    sms: SMSGatewayConfig = field(default_factory=SMSGatewayConfig)
    wechat: WeChatConfig = field(default_factory=WeChatConfig)

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: str | Path | None = None) -> HotelServiceConfig:
        """Load configuration from a YAML file.

        Args:
            path: Path to the YAML settings file. When *None* the loader
                  searches for ``config/settings.yaml`` relative to the
                  project root (the directory containing this package).

        Returns:
            A fully populated :class:`HotelServiceConfig`.

        Raises:
            FileNotFoundError: If the resolved settings file does not exist.
            yaml.YAMLError: If the file contains invalid YAML.
            KeyError: If required configuration sections are missing.
        """
        if path is None:
            # Default: config/settings.yaml relative to project root
            project_root = Path(__file__).resolve().parent.parent
            path = project_root / "config" / "settings.yaml"
        else:
            path = Path(path)

        # Allow override via environment variable
        env_path = os.environ.get("HOTEL_SERVICE_CONFIG")
        if env_path:
            path = Path(env_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {path}\n"
                "Create config/settings.yaml or set the HOTEL_SERVICE_CONFIG "
                "environment variable."
            )

        with open(path, "r", encoding="utf-8") as fh:
            raw: dict[str, Any] = yaml.safe_load(fh)

        return cls._from_dict(raw)

    @classmethod
    def _from_dict(cls, raw: dict[str, Any]) -> HotelServiceConfig:
        """Build a config instance from a parsed YAML dictionary."""
        bitable = BitableConfig.from_dict(raw["bitable"])

        printer_raw = raw.get("printer", {})
        printer = PrinterSettings(
            ip=printer_raw.get("ip", "192.168.1.100"),
            port=printer_raw.get("port", 9100),
            protocol=printer_raw.get("protocol", "tspl"),
            label_width_mm=printer_raw.get("label_width_mm", 75),
            label_height_mm=printer_raw.get("label_height_mm", 50),
        )

        feishu_raw = raw.get("feishu_bot", {})
        feishu_bot = FeishuBotConfig(
            app_id=feishu_raw.get("app_id", ""),
            app_secret=feishu_raw.get("app_secret", ""),
        )

        sms_raw = raw.get("sms", {})
        sms = SMSGatewayConfig(
            provider=sms_raw.get("provider", ""),
            api_key=sms_raw.get("api_key", ""),
            api_secret=sms_raw.get("api_secret", ""),
            sign_name=sms_raw.get("sign_name", ""),
            template_code=sms_raw.get("template_code", ""),
        )

        wechat_raw = raw.get("wechat", {})
        wechat = WeChatConfig(
            app_id=wechat_raw.get("app_id", ""),
            app_secret=wechat_raw.get("app_secret", ""),
            token=wechat_raw.get("token", ""),
            encoding_aes_key=wechat_raw.get("encoding_aes_key", ""),
        )

        return cls(
            bitable=bitable,
            printer=printer,
            feishu_bot=feishu_bot,
            sms=sms,
            wechat=wechat,
        )

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize the configuration back to a plain dictionary.

        Useful for logging or debugging. Secrets are masked.
        """
        from dataclasses import asdict

        d = asdict(self)
        # Mask sensitive fields
        if d.get("feishu_bot", {}).get("app_secret"):
            d["feishu_bot"]["app_secret"] = "***"
        if d.get("sms", {}).get("api_secret"):
            d["sms"]["api_secret"] = "***"
        if d.get("wechat", {}).get("app_secret"):
            d["wechat"]["app_secret"] = "***"
        if d.get("wechat", {}).get("encoding_aes_key"):
            d["wechat"]["encoding_aes_key"] = "***"
        return d
