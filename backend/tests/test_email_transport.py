from __future__ import annotations

import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from backend import main


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self) -> bytes:
        return b'{"id":"resend-sandbox-message-id"}'


def test_resend_https_transport_uses_bearer_key_and_fixed_api_endpoint(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["content_type"] = request.get_header("Content-type")
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(main, "EMAIL_DELIVERY_PROVIDER", "resend_api")
    monkeypatch.setattr(main, "RESEND_API_KEY", "test-only-api-key")
    monkeypatch.setattr(main, "SMTP_CONFIGURED", True)
    monkeypatch.setattr(main, "SMTP_FROM_EMAIL", "onboarding@resend.dev")
    monkeypatch.setattr(main, "SMTP_FROM_NAME", "OmniShelf")
    monkeypatch.setattr(main, "urlopen", fake_urlopen)

    main._send_email("delivered@resend.dev", "Test subject", "No account token included.")

    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["authorization"] == "Bearer test-only-api-key"
    assert captured["content_type"] == "application/json"
    assert captured["timeout"] == 15
    assert captured["payload"] == {
        "from": "OmniShelf <onboarding@resend.dev>",
        "to": ["delivered@resend.dev"],
        "subject": "Test subject",
        "text": "No account token included.",
    }


def test_resend_api_error_is_sanitized(monkeypatch) -> None:
    def fail_with_http_error(request, timeout):
        raise HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            hdrs=None,
            fp=BytesIO(b"private-provider-response-must-not-leak"),
        )

    monkeypatch.setattr(main, "EMAIL_DELIVERY_PROVIDER", "resend_api")
    monkeypatch.setattr(main, "RESEND_API_KEY", "test-only-api-key")
    monkeypatch.setattr(main, "SMTP_CONFIGURED", True)
    monkeypatch.setattr(main, "urlopen", fail_with_http_error)

    with pytest.raises(RuntimeError, match="HTTP 401") as error:
        main._send_email("delivered@resend.dev", "Test subject", "No token")

    assert "private-provider-response-must-not-leak" not in str(error.value)
    assert "test-only-api-key" not in str(error.value)


def test_resend_error_classifier_returns_only_safe_categories() -> None:
    assert main._safe_resend_error_category(
        b'{"name":"validation_error","message":"You can only send testing emails to your own email address"}',
        403,
    ) == "sandbox_recipient_restriction"
    assert main._safe_resend_error_category(
        b'{"name":"validation_error","message":"The domain has not been verified"}',
        403,
    ) == "sender_domain_unverified"
    assert main._safe_resend_error_category(
        b'{"name":"restricted_api_key","message":"API key is scoped to another domain"}',
        403,
    ) == "api_key_scope"
    assert main._safe_resend_error_category(
        b'{"name":"private_code","message":"secret-specific provider account detail"}',
        403,
    ) == "forbidden_by_provider"
    assert main._safe_resend_error_category(
        b'not-json with private provider detail',
        502,
    ) == "provider_rejection"


def test_resend_transport_fails_closed_when_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(main, "EMAIL_DELIVERY_PROVIDER", "resend_api")
    monkeypatch.setattr(main, "RESEND_API_KEY", "")
    monkeypatch.setattr(main, "SMTP_CONFIGURED", False)

    with pytest.raises(RuntimeError, match="not configured"):
        main._send_email("delivered@resend.dev", "Test subject", "No token")
