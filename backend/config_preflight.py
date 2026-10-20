"""Safe, non-networking preflight for hosted email/account security settings.

Run with: python -m backend.config_preflight
The command reports setting names and policy failures, never environment values.
"""
from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from urllib.parse import urlparse


_COMMON_REQUIRED_SETTINGS = (
    "SMTP_FROM_EMAIL",
    "EMAIL_VERIFICATION_REQUIRED",
    "PUBLIC_APP_ORIGIN",
    "COOKIE_SECURE",
    "REGISTRATION_ENABLED",
)
_SMTP_REQUIRED_SETTINGS = ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_STARTTLS")


def validate_hosted_email_config(environment: Mapping[str, str]) -> list[str]:
    """Return safe diagnostics for hosted email settings without network access.

    Render Free blocks outbound SMTP ports, so its default transport is Resend's
    HTTPS API. SMTP remains available for local or paid-hosted environments.
    """
    errors: list[str] = []
    provider = environment.get("EMAIL_DELIVERY_PROVIDER", "").strip().lower()
    if not provider:
        provider = "resend_api" if environment.get("RENDER", "").strip().lower() == "true" else "smtp"

    common_missing = [key for key in _COMMON_REQUIRED_SETTINGS if not environment.get(key, "").strip()]
    errors.extend(f"Missing required setting: {key}" for key in common_missing)

    if provider == "resend_api":
        if not (environment.get("RESEND_API_KEY", "").strip() or environment.get("SMTP_PASSWORD", "").strip()):
            errors.append("Missing required setting: RESEND_API_KEY (or SMTP_PASSWORD for the existing setup).")
    elif provider == "smtp":
        smtp_missing = [key for key in _SMTP_REQUIRED_SETTINGS if not environment.get(key, "").strip()]
        errors.extend(f"Missing required setting: {key}" for key in smtp_missing)
        starttls_value = environment.get("SMTP_STARTTLS", "").strip().lower()
        if starttls_value not in {"1", "true", "yes", "on"}:
            errors.append("SMTP_STARTTLS must be true.")
        port_text = environment.get("SMTP_PORT", "").strip()
        if port_text:
            try:
                port = int(port_text)
            except ValueError:
                errors.append("SMTP_PORT must be an integer from 1 to 65535.")
            else:
                if not 1 <= port <= 65535:
                    errors.append("SMTP_PORT must be an integer from 1 to 65535.")
    else:
        errors.append("EMAIL_DELIVERY_PROVIDER must be either 'resend_api' or 'smtp'.")

    truthy = {"1", "true", "yes", "on"}
    falsey = {"0", "false", "no", "off"}
    if environment.get("EMAIL_VERIFICATION_REQUIRED", "").strip().lower() not in truthy:
        errors.append("EMAIL_VERIFICATION_REQUIRED must be true.")
    if environment.get("COOKIE_SECURE", "").strip().lower() not in truthy:
        errors.append("COOKIE_SECURE must be true.")
    if environment.get("REGISTRATION_ENABLED", "").strip().lower() not in falsey:
        errors.append("REGISTRATION_ENABLED must be false before email acceptance.")

    origin_text = environment.get("PUBLIC_APP_ORIGIN", "").strip()
    if origin_text:
        try:
            origin = urlparse(origin_text)
            # Accessing .port/.hostname can itself reject malformed authority syntax.
            host = origin.hostname
            _ = origin.port
            valid_origin = (
                origin.scheme.lower() == "https"
                and bool(host)
                and origin.username is None
                and origin.password is None
                and origin.path in ("", "/")
                and not origin.query
                and not origin.fragment
            )
        except ValueError:
            valid_origin = False
        if not valid_origin:
            errors.append(
                "PUBLIC_APP_ORIGIN must be a valid HTTPS origin without credentials, query, or fragment."
            )

    return errors


def main() -> int:
    errors = validate_hosted_email_config(os.environ)
    if errors:
        print("Email configuration preflight failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    provider = os.environ.get("EMAIL_DELIVERY_PROVIDER", "").strip().lower()
    if not provider:
        provider = "resend_api" if os.environ.get("RENDER", "").strip().lower() == "true" else "smtp"
    print(
        f"Email configuration preflight passed for {provider}: required settings and safety flags are present. "
        "Transport connectivity and actual delivery are not tested."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
