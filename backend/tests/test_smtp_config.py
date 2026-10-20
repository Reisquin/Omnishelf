from __future__ import annotations

from backend.main import _email_configuration_is_complete


API_BASE = {
    "provider": "resend_api",
    "host": "",
    "username": "",
    "password": "",
    "resend_api_key": "test-only-api-key",
    "from_email": "onboarding@resend.dev",
    "starttls": True,
    "hosted": True,
    "public_app_origin": "https://omnishelf-staging.onrender.com",
}

SMTP_BASE = {
    "provider": "smtp",
    "host": "smtp.example.test",
    "username": "test-sender",
    "password": "test-only-password",
    "resend_api_key": "",
    "from_email": "sender@example.test",
    "starttls": True,
    "hosted": True,
    "public_app_origin": "https://omnishelf-staging.onrender.com",
}


def test_resend_https_transport_does_not_require_smtp_credentials() -> None:
    assert _email_configuration_is_complete(**API_BASE)
    assert not _email_configuration_is_complete(**{**API_BASE, "resend_api_key": ""})


def test_resend_https_transport_requires_valid_sender_and_https_hosted_origin() -> None:
    assert not _email_configuration_is_complete(**{**API_BASE, "from_email": "not-an-address"})
    assert not _email_configuration_is_complete(**{**API_BASE, "public_app_origin": "http://localhost"})


def test_smtp_transport_requires_hosted_credentials_and_starttls() -> None:
    assert _email_configuration_is_complete(**SMTP_BASE)
    assert not _email_configuration_is_complete(**{**SMTP_BASE, "username": ""})
    assert not _email_configuration_is_complete(**{**SMTP_BASE, "starttls": False})


def test_local_smtp_sink_can_remain_unauthenticated() -> None:
    assert _email_configuration_is_complete(
        provider="smtp",
        host="localhost",
        username="",
        password="",
        resend_api_key="",
        from_email="test@example.com",
        starttls=True,
        hosted=False,
        public_app_origin="http://localhost",
    )


def test_unknown_provider_fails_closed() -> None:
    assert not _email_configuration_is_complete(**{**API_BASE, "provider": "unknown"})
