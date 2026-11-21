from __future__ import annotations

from dataclasses import replace

import pytest

from app.database.repositories.settings_repository import SettingsRepository
from app.models.message import CapturedMessage
from app.services.ai_settings_service import AISettingsService, DeepSeekConfig
from app.services.privacy import redact_messages, redact_text


class FakeCredentials:
    def __init__(self):
        self.value = ""
        self.deleted = 0

    def get_api_key(self):
        return self.value

    def set_api_key(self, value):
        self.value = value

    def delete_api_key(self):
        self.value = ""
        self.deleted += 1


def test_deepseek_settings_persist_nonsecrets_and_key_uses_credential_store(database):
    credentials = FakeCredentials()
    service = AISettingsService(SettingsRepository(database), credentials)
    config = DeepSeekConfig(
        base_url="https://api.deepseek.com",
        api_key="sk-real-secret",
        model="deepseek-flash",
        advanced_model="deepseek-v4-pro",
        temperature=0.6,
        max_tokens=4000,
        timeout=45,
    )

    service.save(config)

    assert credentials.value == "sk-real-secret"
    assert service.load(include_api_key=True) == config
    assert service.load().api_key == ""
    stored = " ".join(
        row["value"]
        for row in database.connection.execute("SELECT value FROM settings")
    )
    assert "sk-real-secret" not in stored
    assert "sk-real-secret" not in repr(config)


def test_blank_api_key_preserves_existing_and_clear_deletes(database):
    credentials = FakeCredentials()
    service = AISettingsService(SettingsRepository(database), credentials)
    original = DeepSeekConfig(api_key="sk-original")
    service.save(original)

    service.save(replace(original, api_key="", model="editable-model"))
    assert credentials.value == "sk-original"
    assert service.has_api_key()
    service.clear_api_key()
    assert not service.has_api_key()
    assert credentials.deleted == 1


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"base_url": "not-a-url"}, "Base URL"),
        ({"model": " "}, "模型"),
        ({"temperature": 2.1}, "Temperature"),
        ({"max_tokens": 0}, "Token"),
        ({"timeout": 0}, "超时"),
    ],
)
def test_deepseek_config_validation(database, changes, message):
    service = AISettingsService(SettingsRepository(database), FakeCredentials())
    with pytest.raises(ValueError, match=message):
        service.save(replace(DeepSeekConfig(), **changes))


def test_privacy_redacts_phone_email_company_but_not_order_quantity():
    text = "ACME GmbH: call +49 171 234 5678 or buyer@acme.example; need 500 units"

    redacted = redact_text(text, company_names=["ACME GmbH"])

    assert "[已脱敏公司]" in redacted
    assert "[已脱敏电话]" in redacted
    assert "[已脱敏邮箱]" in redacted
    assert "500 units" in redacted
    assert "ACME GmbH" not in redacted
    assert "buyer@acme.example" not in redacted


def test_privacy_redacts_only_message_content():
    messages = [CapturedMessage("Email buyer@example.com", sender_name="Alice")]

    redacted = redact_messages(messages)

    assert redacted[0].content == "Email [已脱敏邮箱]"
    assert redacted[0].sender_name == "Alice"
    assert messages[0].content == "Email buyer@example.com"
