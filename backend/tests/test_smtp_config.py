from __future__ import annotations

from backend.main import _smtp_configuration_is_complete


BASE = {
    "host": "smtp.resend.com",
    "username": "resend",
    "password": "test-only-api-key",
    "from_email": "onboarding@resend.dev",
    "starttls": True,
    "hosted": True,
    "public_app_origin": "https://omnishelf-staging.onrender.com",
}


def test_hosted_resend_sender_is_not_ready_without_api_key() -> None:
    assert not _smtp_configuration_is_complete(**{**BASE, "password": ""})


def test_hosted_smtp_requires_username_and_password() -> None:
    assert not _smtp_configuration_is_complete(**{**BASE, "username": ""})
    assert _smtp_configuration_is_complete(**BASE)


def test_hosted_smtp_requires_https_origin_and_starttls() -> None:
    assert not _smtp_configuration_is_complete(**{**BASE, "public_app_origin": "http://localhost"})
    assert not _smtp_configuration_is_complete(**{**BASE, "starttls": False})


def test_local_smtp_sink_can_remain_unauthenticated() -> None:
    assert _smtp_configuration_is_complete(
        host="localhost",
        username="",
        password="",
        from_email="test@example.com",
        starttls=True,
        hosted=False,
        public_app_origin="http://localhost",
    )
