from __future__ import annotations

import smtplib

from backend import smtp_acceptance


VALID_CONFIG = {
    "OMNISHELF_SMTP_ACCEPTANCE_ENABLED": "true",
    "SMTP_TEST_RECIPIENT": "controlled-test-mailbox@example.com",
    "SMTP_HOST": "smtp.example.com",
    "SMTP_PORT": "587",
    "SMTP_USERNAME": "private-smtp-username",
    "SMTP_PASSWORD": "private-smtp-password",
    "SMTP_FROM_EMAIL": "noreply@example.com",
    "SMTP_FROM_NAME": "OmniShelf test",
    "SMTP_STARTTLS": "true",
    "EMAIL_VERIFICATION_REQUIRED": "true",
    "PUBLIC_APP_ORIGIN": "https://omnishelf.example.com",
    "COOKIE_SECURE": "true",
    "REGISTRATION_ENABLED": "false",
}


class FakeSMTP:
    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.calls = []
        self.message = None

    def __enter__(self):
        self.calls.append(("enter",))
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.calls.append(("exit",))
        return False

    def ehlo(self):
        self.calls.append(("ehlo",))

    def starttls(self, *, context):
        self.calls.append(("starttls", context))

    def login(self, username, password):
        self.calls.append(("login", username, password))

    def send_message(self, message):
        self.message = message
        self.calls.append(("send_message",))
        return {}


def test_acceptance_requires_explicit_enable_flag_and_does_not_connect(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        smtp_acceptance.smtplib,
        "SMTP",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not connect")),
    )

    result = smtp_acceptance.run_acceptance({**VALID_CONFIG, "OMNISHELF_SMTP_ACCEPTANCE_ENABLED": "false"})
    output = capsys.readouterr().out

    assert result == 1
    assert "explicitly opt in" in output
    assert "private-smtp-password" not in output


def test_acceptance_refuses_bad_or_missing_recipient_before_connection(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        smtp_acceptance.smtplib,
        "SMTP",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not connect")),
    )

    result = smtp_acceptance.run_acceptance({**VALID_CONFIG, "SMTP_TEST_RECIPIENT": "not-a-mailbox"})
    output = capsys.readouterr().out

    assert result == 1
    assert "SMTP_TEST_RECIPIENT" in output
    assert "private-smtp-password" not in output


def test_acceptance_uses_validated_starttls_auth_and_sends_only_test_message(monkeypatch, capsys) -> None:
    server = FakeSMTP("smtp.example.com", 587, 15)
    monkeypatch.setattr(smtp_acceptance.smtplib, "SMTP", lambda host, port, timeout: server)
    sentinel_context = object()
    monkeypatch.setattr(smtp_acceptance.ssl, "create_default_context", lambda: sentinel_context)

    result = smtp_acceptance.run_acceptance(VALID_CONFIG)
    output = capsys.readouterr().out

    assert result == 0
    assert server.calls[0] == ("enter",)
    assert ("starttls", sentinel_context) in server.calls
    assert ("login", "private-smtp-username", "private-smtp-password") in server.calls
    assert server.message["To"] == "controlled-test-mailbox@example.com"
    assert server.message["Subject"] == "OmniShelf email delivery acceptance test"
    assert "No account token or password" in server.message.get_content()
    assert "private-smtp-password" not in server.message.as_string()
    assert "private-smtp-password" not in output
    assert "Check the mailbox" in output


def test_acceptance_does_not_print_smtp_exception_details(monkeypatch, capsys) -> None:
    class FailingSMTP(FakeSMTP):
        def starttls(self, *, context):
            raise smtplib.SMTPAuthenticationError(535, b"unsafe-private-provider-detail")

    server = FailingSMTP("smtp.example.com", 587, 15)
    monkeypatch.setattr(smtp_acceptance.smtplib, "SMTP", lambda host, port, timeout: server)
    monkeypatch.setattr(smtp_acceptance.ssl, "create_default_context", lambda: object())

    result = smtp_acceptance.run_acceptance(VALID_CONFIG)
    output = capsys.readouterr().out

    assert result == 1
    assert "SMTP acceptance failed" in output
    assert "unsafe-private-provider-detail" not in output
    assert "private-smtp-password" not in output


def test_acceptance_requires_starttls_before_connecting(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        smtp_acceptance.smtplib,
        "SMTP",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not connect")),
    )

    result = smtp_acceptance.run_acceptance({**VALID_CONFIG, "SMTP_STARTTLS": "false"})
    output = capsys.readouterr().out

    assert result == 1
    assert "SMTP_STARTTLS" in output
    assert "private-smtp-password" not in output
