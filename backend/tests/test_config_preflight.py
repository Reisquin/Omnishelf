from __future__ import annotations

from backend.config_preflight import main, validate_hosted_email_config


VALID_CONFIG = {
    "SMTP_HOST": "smtp.mail.example",
    "SMTP_PORT": "587",
    "SMTP_USERNAME": "test-user-secret",
    "SMTP_PASSWORD": "test-password-secret",
    "SMTP_FROM_EMAIL": "noreply@example.com",
    "SMTP_STARTTLS": "true",
    "EMAIL_VERIFICATION_REQUIRED": "true",
    "PUBLIC_APP_ORIGIN": "https://app.example.com",
    "COOKIE_SECURE": "true",
    "REGISTRATION_ENABLED": "false",
}


def test_hosted_email_config_accepts_required_settings_and_safe_flags() -> None:
    assert validate_hosted_email_config(VALID_CONFIG) == []


def test_preflight_rejects_missing_settings_without_reporting_values() -> None:
    config = dict(VALID_CONFIG)
    config.pop("SMTP_PASSWORD")
    config["SMTP_USERNAME"] = "do-not-print-this-username"

    errors = validate_hosted_email_config(config)

    assert errors == ["Missing required setting: SMTP_PASSWORD"]
    assert all("do-not-print-this-username" not in error for error in errors)
    assert all("test-password-secret" not in error for error in errors)


def test_preflight_rejects_unsafe_hosted_flags_and_invalid_origin() -> None:
    config = {
        **VALID_CONFIG,
        "SMTP_PORT": "70000",
        "SMTP_STARTTLS": "false",
        "EMAIL_VERIFICATION_REQUIRED": "false",
        "COOKIE_SECURE": "false",
        "REGISTRATION_ENABLED": "true",
        "PUBLIC_APP_ORIGIN": "http://app.example.com/path?token=should-not-be-logged",
    }

    errors = validate_hosted_email_config(config)

    assert any("SMTP_PORT" in error for error in errors)
    assert any("SMTP_STARTTLS" in error for error in errors)
    assert any("EMAIL_VERIFICATION_REQUIRED" in error for error in errors)
    assert any("COOKIE_SECURE" in error for error in errors)
    assert any("REGISTRATION_ENABLED" in error for error in errors)
    assert any("PUBLIC_APP_ORIGIN" in error for error in errors)
    assert all("should-not-be-logged" not in error for error in errors)


def test_cli_reports_only_setting_names_and_never_secret_values(monkeypatch, capsys) -> None:
    for key, value in VALID_CONFIG.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    status = main()
    output = capsys.readouterr().out

    assert status == 1
    assert "SMTP_PASSWORD" in output
    assert "test-user-secret" not in output
    assert "test-password-secret" not in output

def test_resend_api_preflight_needs_no_smtp_ports_or_username() -> None:
    from backend.config_preflight import validate_hosted_email_config

    config = {
        "EMAIL_DELIVERY_PROVIDER": "resend_api",
        "SMTP_PASSWORD": "resend-test-api-key",
        "SMTP_FROM_EMAIL": "onboarding@resend.dev",
        "EMAIL_VERIFICATION_REQUIRED": "true",
        "PUBLIC_APP_ORIGIN": "https://app.onrender.com",
        "COOKIE_SECURE": "true",
        "REGISTRATION_ENABLED": "false",
    }

    assert validate_hosted_email_config(config) == []


def test_resend_api_preflight_requires_api_key_without_printing_it() -> None:
    from backend.config_preflight import validate_hosted_email_config

    config = {
        "EMAIL_DELIVERY_PROVIDER": "resend_api",
        "SMTP_FROM_EMAIL": "onboarding@resend.dev",
        "EMAIL_VERIFICATION_REQUIRED": "true",
        "PUBLIC_APP_ORIGIN": "https://app.onrender.com",
        "COOKIE_SECURE": "true",
        "REGISTRATION_ENABLED": "false",
    }

    errors = validate_hosted_email_config(config)
    assert len(errors) == 1
    assert "RESEND_API_KEY" in errors[0]
