from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.ai_settings_service import DeepSeekConfig
from app.services.deepseek_service import DeepSeekAPIError, DeepSeekClient


def response(content='{"ok": true}', prompt=10, completion=20):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion,
        ),
    )


class FakeCompletions:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeOpenAI:
    def __init__(self, outcomes):
        self.chat = SimpleNamespace(completions=FakeCompletions(outcomes))


class FakeSettings:
    def __init__(self):
        self.config = DeepSeekConfig(api_key="sk-test", timeout=33)

    def load(self, include_api_key=False):
        return self.config


class FakeStatusError(RuntimeError):
    def __init__(self, status_code, text=""):
        super().__init__(text)
        self.status_code = status_code


def make_client(outcomes):
    sdk = FakeOpenAI(outcomes)
    captured = []

    def factory(config):
        captured.append(config)
        return sdk

    return DeepSeekClient(FakeSettings(), client_factory=factory), sdk, captured


def test_json_completion_uses_openai_compatible_configuration_and_usage():
    client, sdk, captured = make_client([response()])

    completion = client.complete_json(
        [{"role": "user", "content": "Analyze"}], advanced=True
    )

    assert completion.content == '{"ok": true}'
    assert captured[0].api_key == "sk-test"
    assert captured[0].base_url == "https://api.deepseek.com"
    call = sdk.chat.completions.calls[0]
    assert call["model"] == "deepseek-v4-pro"
    assert call["response_format"] == {"type": "json_object"}
    assert call["max_tokens"] == 4000
    assert call["timeout"] == 33
    assert completion.stats.prompt_tokens == 10
    assert completion.stats.completion_tokens == 20
    assert completion.stats.total_tokens == 30
    assert completion.stats.status == "success"
    assert completion.stats.duration_ms >= 0


def test_connection_test_uses_small_request_and_returns_chinese_status():
    client, sdk, _ = make_client([response("OK", 2, 1)])

    result = client.test_connection()

    assert "连接成功" in result.message
    assert sdk.chat.completions.calls[0]["max_tokens"] <= 8
    assert result.stats.total_tokens == 3


@pytest.mark.parametrize(
    "error, error_type, message",
    [
        (FakeStatusError(401), "authentication", "API Key"),
        (FakeStatusError(402), "balance", "余额"),
        (FakeStatusError(429), "rate_limit", "限流"),
        (FakeStatusError(503), "api_error", "失败"),
        (TimeoutError("timeout"), "timeout", "超时"),
        (ConnectionError("offline"), "network", "网络"),
    ],
)
def test_api_errors_are_sanitized_chinese_and_include_failed_usage(
    error, error_type, message
):
    client, _, _ = make_client([error])

    with pytest.raises(DeepSeekAPIError) as caught:
        client.complete_json([{"role": "user", "content": "secret chat"}])

    assert caught.value.error_type == error_type
    assert message in str(caught.value)
    assert "secret chat" not in str(caught.value)
    assert "sk-test" not in str(caught.value)
    assert caught.value.stats.status == "failed"
    assert caught.value.stats.error_type == error_type


def test_missing_api_key_fails_before_creating_sdk_client():
    settings = FakeSettings()
    settings.config = DeepSeekConfig(api_key="")
    called = []
    client = DeepSeekClient(settings, client_factory=lambda config: called.append(config))

    with pytest.raises(DeepSeekAPIError, match="API Key") as caught:
        client.test_connection()

    assert called == []
    assert caught.value.error_type == "missing_key"
