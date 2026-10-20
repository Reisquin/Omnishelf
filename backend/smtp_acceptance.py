"""Explicit, opt-in email delivery acceptance check.

Run only in a controlled environment with a dedicated test mailbox:
    OMNISHELF_SMTP_ACCEPTANCE_ENABLED=true
    SMTP_TEST_RECIPIENT=your-controlled-mailbox@example.com
    python -m backend.smtp_acceptance

This sends one harmless test message. It does not run at app startup.
"""
from __future__ import annotations

import os
import re
import smtplib
import ssl
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen
from collections.abc import Mapping
from email.message import EmailMessage
from email.utils import formataddr

from backend.config_preflight import validate_hosted_email_config


ENABLE_FLAG = "OMNISHELF_SMTP_ACCEPTANCE_ENABLED"
RECIPIENT_SETTING = "SMTP_TEST_RECIPIENT"
_ADDRESS = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def run_acceptance(environment: Mapping[str, str] = os.environ) -> int:
    """Send one explicit acceptance message only after all safety checks pass."""
    if environment.get(ENABLE_FLAG, "").strip().lower() not in {"1", "true", "yes", "on"}:
        print(f"SMTP acceptance not run; set {ENABLE_FLAG}=true to explicitly opt in.")
        return 1

    errors = validate_hosted_email_config(environment)
    recipient = environment.get(RECIPIENT_SETTING, "").strip()
    if not recipient:
        errors.append(f"Missing required setting: {RECIPIENT_SETTING}")
    elif not _ADDRESS.fullmatch(recipient):
        errors.append(f"{RECIPIENT_SETTING} must be a valid mailbox address.")

    if errors:
        print("SMTP acceptance blocked by configuration checks:")
        for error in errors:
            print(f"- {error}")
        return 1

    sender = environment["SMTP_FROM_EMAIL"].strip()
    sender_name = environment.get("SMTP_FROM_NAME", "OmniShelf").strip() or "OmniShelf"
    provider = environment.get("EMAIL_DELIVERY_PROVIDER", "").strip().lower()
    if not provider:
        provider = "resend_api" if environment.get("RENDER", "").strip().lower() == "true" else "smtp"
    subject = "OmniShelf email delivery acceptance test"
    body = (
        "This is a one-time OmniShelf email delivery acceptance test. "
        "No account token or password is included. If you did not initiate "
        "this test, you may ignore this message."
    )

    if provider == "resend_api":
        api_key = environment.get("RESEND_API_KEY", "").strip() or environment.get("SMTP_PASSWORD", "").strip()
        if not api_key:
            print("Email acceptance blocked: RESEND_API_KEY (or existing SMTP_PASSWORD) is missing.")
            return 1
        request = UrlRequest(
            "https://api.resend.com/emails",
            data=json.dumps({
                "from": formataddr((sender_name, sender)),
                "to": [recipient],
                "subject": subject,
                "text": body,
            }).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=15) as response:
                result = json.loads(response.read().decode("utf-8"))
                if response.status < 200 or response.status >= 300 or not isinstance(result, dict) or not result.get("id"):
                    print("Resend API did not accept the acceptance-test message.")
                    return 1
        except HTTPError as exc:
            print(f"Resend API acceptance failed with HTTP {exc.code}; provider details were not printed.")
            return 1
        except (URLError, OSError, RuntimeError, ValueError, json.JSONDecodeError):
            print("Resend API acceptance failed; provider details and credentials were not printed.")
            return 1
        print("Resend accepted the acceptance-test message.")
        print("For Resend's simulated-delivery recipient, this is not real inbox delivery.")
        return 0

    if provider != "smtp":
        print("Email acceptance blocked: EMAIL_DELIVERY_PROVIDER is unsupported.")
        return 1

    host = environment["SMTP_HOST"].strip()
    port = int(environment["SMTP_PORT"].strip())
    username = environment["SMTP_USERNAME"].strip()
    password = environment["SMTP_PASSWORD"]
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((sender_name, sender))
    message["To"] = recipient
    message.set_content(body)
    try:
        # Certificate validation is enabled by create_default_context; no insecure fallback.
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            server.login(username, password)
            refused = server.send_message(message)
            if refused:
                print("SMTP server refused delivery to the designated test mailbox.")
                return 1
    except (smtplib.SMTPException, OSError, RuntimeError, ValueError):
        print("SMTP acceptance failed. Server details and credentials were not printed.")
        return 1

    print("SMTP server accepted the acceptance-test message for the configured mailbox.")
    print("Check the mailbox (including spam/quarantine) to confirm actual delivery.")
    return 0


def main() -> int:
    return run_acceptance()


if __name__ == "__main__":
    raise SystemExit(main())
