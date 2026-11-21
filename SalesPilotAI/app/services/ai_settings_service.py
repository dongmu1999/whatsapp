"""DeepSeek 非密配置与系统安全凭据存储。"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from urllib.parse import urlparse

from app.database.repositories.settings_repository import SettingsRepository


class CredentialStoreError(RuntimeError):
    """系统凭据库不可用。"""


class KeyringCredentialStore:
    """使用系统 keyring；Windows 默认进入凭据管理器，不回退到明文。"""

    SERVICE_NAME = "SalesPilotAI"
    USERNAME = "deepseek_api_key"

    def get_api_key(self) -> str:
        try:
            import keyring

            return keyring.get_password(self.SERVICE_NAME, self.USERNAME) or ""
        except Exception as exc:
            raise CredentialStoreError("无法读取系统安全凭据库，请检查系统凭据服务。") from exc

    def set_api_key(self, value: str) -> None:
        try:
            import keyring

            keyring.set_password(self.SERVICE_NAME, self.USERNAME, value)
        except Exception as exc:
            raise CredentialStoreError("无法将 API Key 保存到系统安全凭据库。") from exc

    def delete_api_key(self) -> None:
        try:
            import keyring

            keyring.delete_password(self.SERVICE_NAME, self.USERNAME)
        except Exception as exc:
            # 删除不存在的条目与真正不可用需要区分，但均不降级为明文。
            if exc.__class__.__name__ == "PasswordDeleteError":
                return
            raise CredentialStoreError("无法从系统安全凭据库删除 API Key。") from exc


@dataclass(frozen=True)
class DeepSeekConfig:
    base_url: str = "https://api.deepseek.com"
    api_key: str = field(default="", repr=False, compare=True)
    model: str = "deepseek-flash"
    advanced_model: str = "deepseek-v4-pro"
    temperature: float = 0.7
    max_tokens: int = 4000
    timeout: int = 60

    def validate(self) -> None:
        parsed = urlparse(self.base_url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Base URL 必须是有效的 http:// 或 https:// 地址")
        if not self.model.strip() or not self.advanced_model.strip():
            raise ValueError("默认模型和高级模型名称不能为空")
        if not 0.0 <= float(self.temperature) <= 2.0:
            raise ValueError("Temperature 必须在 0 到 2 之间")
        if isinstance(self.max_tokens, bool) or not 1 <= int(self.max_tokens) <= 32000:
            raise ValueError("最大输出 Token 必须在 1 到 32000 之间")
        if isinstance(self.timeout, bool) or not 1 <= int(self.timeout) <= 600:
            raise ValueError("请求超时时间必须在 1 到 600 秒之间")


class AISettingsService:
    def __init__(self, settings: SettingsRepository, credentials=None):
        self.settings = settings
        self.credentials = credentials or KeyringCredentialStore()

    def load(self, include_api_key: bool = False) -> DeepSeekConfig:
        defaults = DeepSeekConfig()
        config = DeepSeekConfig(
            base_url=self.settings.get("deepseek_base_url", defaults.base_url),
            api_key=self.credentials.get_api_key() if include_api_key else "",
            model=self.settings.get("deepseek_model", defaults.model),
            advanced_model=self.settings.get(
                "deepseek_advanced_model", defaults.advanced_model
            ),
            temperature=self._float_setting("deepseek_temperature", defaults.temperature),
            max_tokens=self._int_setting("deepseek_max_tokens", defaults.max_tokens),
            timeout=self._int_setting("deepseek_timeout", defaults.timeout),
        )
        return config

    def save(self, config: DeepSeekConfig) -> None:
        config.validate()
        values = {
            "deepseek_base_url": config.base_url.strip().rstrip("/"),
            "deepseek_model": config.model.strip(),
            "deepseek_advanced_model": config.advanced_model.strip(),
            "deepseek_temperature": str(float(config.temperature)),
            "deepseek_max_tokens": str(int(config.max_tokens)),
            "deepseek_timeout": str(int(config.timeout)),
        }
        if config.api_key.strip():
            self.credentials.set_api_key(config.api_key.strip())
        for key, value in values.items():
            self.settings.set(key, value)

    def has_api_key(self) -> bool:
        return bool(self.credentials.get_api_key().strip())

    def clear_api_key(self) -> None:
        self.credentials.delete_api_key()

    def _int_setting(self, key: str, default: int) -> int:
        try:
            return int(self.settings.get(key, str(default)))
        except (TypeError, ValueError):
            return default

    def _float_setting(self, key: str, default: float) -> float:
        try:
            return float(self.settings.get(key, str(default)))
        except (TypeError, ValueError):
            return default
