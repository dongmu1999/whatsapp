"""OpenAI SDK 兼容的 DeepSeek 请求、中文异常与用量统计。"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter


@dataclass
class APIUsageStats:
    model: str
    endpoint: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    duration_ms: int = 0
    status: str = "success"
    error_type: str | None = None


@dataclass
class Completion:
    content: str
    stats: APIUsageStats


@dataclass
class ConnectionTestResult:
    message: str
    stats: APIUsageStats


class DeepSeekAPIError(RuntimeError):
    def __init__(self, message: str, error_type: str = "api_error", stats=None):
        super().__init__(message)
        self.error_type = error_type
        self.stats = stats
        self.api_calls = [stats] if stats is not None else []
        self.raw_response = ""
        self.customer_id = None
        self.conversation_id = None


class DeepSeekClient:
    def __init__(self, settings_service, client_factory=None):
        self.settings_service = settings_service
        self.client_factory = client_factory or self._create_sdk_client

    @staticmethod
    def _create_sdk_client(config):
        from openai import OpenAI

        return OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout,
        )

    def test_connection(self, config=None) -> ConnectionTestResult:
        if config is None:
            config = self.settings_service.load(include_api_key=True)
        self._require_key(config)
        response, stats = self._request(
            config,
            model=config.model,
            messages=[{"role": "user", "content": "请只回复 OK"}],
            max_tokens=5,
        )
        self._content(response, stats)
        return ConnectionTestResult(f"DeepSeek 连接成功，模型：{config.model}", stats)

    def complete_json(
        self, messages: list[dict], *, advanced: bool = False, config=None
    ) -> Completion:
        if config is None:
            config = self.settings_service.load(include_api_key=True)
        self._require_key(config)
        model = config.advanced_model if advanced else config.model
        response, stats = self._request(
            config,
            model=model,
            messages=messages,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            response_format={"type": "json_object"},
        )
        return Completion(self._content(response, stats), stats)

    @staticmethod
    def _require_key(config) -> None:
        if not config.api_key.strip():
            raise DeepSeekAPIError(
                "请先在“AI 模型设置”中填写并安全保存 DeepSeek API Key。",
                "missing_key",
            )

    def _request(
        self,
        config,
        *,
        model: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float | None = None,
        response_format: dict | None = None,
    ):
        started = perf_counter()
        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "timeout": config.timeout,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if response_format is not None:
            kwargs["response_format"] = response_format
        try:
            sdk = self.client_factory(config)
            response = sdk.chat.completions.create(**kwargs)
        except Exception as exc:
            error_type, message = self._classify_error(exc)
            stats = APIUsageStats(
                model=model,
                endpoint=config.base_url,
                duration_ms=int((perf_counter() - started) * 1000),
                status="failed",
                error_type=error_type,
            )
            raise DeepSeekAPIError(message, error_type, stats) from exc
        usage = getattr(response, "usage", None)
        stats = APIUsageStats(
            model=model,
            endpoint=config.base_url,
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
            duration_ms=int((perf_counter() - started) * 1000),
        )
        return response, stats

    @staticmethod
    def _content(response, stats: APIUsageStats) -> str:
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError):
            content = None
        if not content or not str(content).strip():
            stats.status = "failed"
            stats.error_type = "empty_response"
            raise DeepSeekAPIError("DeepSeek 返回内容为空，请稍后重试。", "empty_response", stats)
        return str(content)

    @staticmethod
    def _classify_error(exc: Exception) -> tuple[str, str]:
        name = exc.__class__.__name__
        status = getattr(exc, "status_code", None)
        detail = str(exc).casefold()
        if name == "AuthenticationError" or status in {401, 403}:
            return "authentication", "DeepSeek API Key 无效或没有权限，请检查设置。"
        if status == 402 or "insufficient balance" in detail or "余额不足" in detail:
            return "balance", "DeepSeek 账户余额不足，请充值后重试。"
        if name == "RateLimitError" or status == 429:
            return "rate_limit", "DeepSeek 请求触发限流，请稍后重试。"
        if name == "APITimeoutError" or isinstance(exc, TimeoutError):
            return "timeout", "DeepSeek 请求超时，请检查网络或增大超时时间。"
        if name == "APIConnectionError" or isinstance(exc, ConnectionError):
            return "network", "无法连接 DeepSeek，请检查网络、代理和 Base URL。"
        if status is not None and 500 <= int(status) < 600:
            return "api_error", "DeepSeek 服务暂时失败，请稍后重试。"
        return "api_error", "DeepSeek 请求失败，请检查模型名称、参数和服务状态。"
