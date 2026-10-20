"""Self-cleaning, authenticated HTTPS + Resend sandbox acceptance test for staging (single retry).

GitHub Actions supplies a short-lived OIDC token. The staging backend validates
that token against GitHub's signing keys and this repository/workflow/ref before
creating temporary test accounts. Passwords are random at runtime and never
written to workflow source or logs. Registration remains disabled throughout.
"""
from __future__ import annotations

import json
import os
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from urllib.parse import urlencode

import requests

BASE_URL = os.getenv(
    "OMNISHELF_AUTH_STAGING_URL",
    "https://omnishelf-1-3-8-auth-staging.onrender.com",
).rstrip("/")
ORIGIN = BASE_URL
AUDIENCE = "omnishelf-auth-staging"
COOKIE_NAME = "omnishelf_session"
PREPARE_PATH = "/__staging/acceptance/prepare"
CLEANUP_PATH = "/__staging/acceptance/cleanup"


def get_github_actions_oidc_token() -> str:
    token_url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    request_token = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    if not token_url or not request_token:
        raise RuntimeError("GitHub Actions OIDC is unavailable; ensure this job has id-token: write permission.")
    response = requests.get(
        token_url,
        params={"audience": AUDIENCE},
        headers={"Authorization": f"Bearer {request_token}"},
        timeout=20,
    )
    response.raise_for_status()
    token = response.json().get("value")
    if not isinstance(token, str) or not token:
        raise RuntimeError("GitHub Actions did not issue an OIDC token.")
    return token


def state_payload(title: str, expected_revision: int = 0, profile_name: str = "Staging acceptance") -> dict:
    return {
        "expected_revision": expected_revision,
        "state": {
            "profile": {"name": profile_name},
            "works": [{
                "title": title,
                "medium": "Novella",
                "status": "In Progress",
                "progress": 4,
                "total": 20,
                "unit": "pages",
            }],
            "reviews": [],
            "activity": [],
            "customLists": [],
        },
    }


def prepare_account(oidc_token: str, slot: str, password: str) -> dict:
    headers = {"Authorization": f"Bearer {oidc_token}", "Content-Type": "application/json"}
    deadline = time.monotonic() + 240
    last_problem = "staging acceptance route is not ready yet"
    while time.monotonic() < deadline:
        try:
            response = requests.post(
                BASE_URL + PREPARE_PATH,
                headers=headers,
                json={"slot": slot, "password": password},
                timeout=30,
            )
            if response.status_code == 201:
                return response.json()
            if response.status_code in (404, 405, 502, 503, 504):
                last_problem = f"staging prepare returned HTTP {response.status_code}"
                time.sleep(5)
                continue
            raise RuntimeError(
                f"Staging account preparation failed with HTTP {response.status_code}: {response.text[:300]}"
            )
        except requests.RequestException as exc:
            last_problem = repr(exc)
            time.sleep(5)
    raise RuntimeError(f"Staging acceptance hook did not become ready: {last_problem}")


def login(username: str, password: str) -> requests.Session:
    session = requests.Session()
    response = session.post(
        BASE_URL + "/api/auth/login",
        headers={"Origin": ORIGIN},
        json={"identifier": username, "password": password},
        timeout=30,
    )
    assert response.status_code == 200, f"Login failed: HTTP {response.status_code}, {response.text[:250]}"
    cookie_header = response.headers.get("set-cookie", "").lower()
    for attribute in ("secure", "httponly", "samesite=lax"):
        assert attribute in cookie_header, f"Session cookie is missing {attribute!r}: {cookie_header!r}"
    assert response.headers.get("cache-control") == "no-store", "Login response must be no-store."
    assert response.headers.get("strict-transport-security", "").startswith("max-age="), "Login response must have HSTS."
    assert session.cookies.get(COOKIE_NAME), "Login did not set the session cookie."
    return session


def assert_cleanup(oidc_token: str) -> dict:
    response = requests.post(
        BASE_URL + CLEANUP_PATH,
        headers={"Authorization": f"Bearer {oidc_token}"},
        timeout=30,
    )
    assert response.status_code == 200, (
        f"Staging test-account cleanup failed: HTTP {response.status_code}, {response.text[:300]}"
    )
    result = response.json()
    assert isinstance(result.get("deleted_accounts"), int)
    return result



def send_email_acceptance(oidc_token: str) -> dict:
    """Trigger one sandbox-only email delivery acceptance message per workflow attempt."""
    response = requests.post(
        BASE_URL + "/__staging/acceptance/email",
        headers={"Authorization": f"Bearer {oidc_token}", "Origin": ORIGIN},
        timeout=30,
    )
    assert response.status_code == 200, (
        f"Staging email acceptance failed with HTTP {response.status_code}: {response.text[:250]}"
    )
    result = response.json()
    assert result.get("result") == "accepted_by_provider"
    assert result.get("recipient") == "delivered@resend.dev"
    return result


def main() -> None:
    oidc_token = get_github_actions_oidc_token()
    passwords = {"p": secrets.token_urlsafe(40), "s": secrets.token_urlsafe(40)}
    account_users: dict[str, dict] = {}
    try:
        # The API creates accounts only after validating this run's signed GitHub OIDC identity.
        account_users["p"] = prepare_account(oidc_token, "p", passwords["p"])
        account_users["s"] = prepare_account(oidc_token, "s", passwords["s"])
        primary_name = account_users["p"]["username"]
        secondary_name = account_users["s"]["username"]
        assert primary_name != secondary_name
        assert "@example.invalid" in account_users["p"]["email"]
        assert "@example.invalid" in account_users["s"]["email"]

        # This is constrained by the server to Resend's synthetic delivered@resend.dev
        # test recipient; it sends no real user email or account token.
        email_result = send_email_acceptance(oidc_token)

        # New accounts have no state; signing in works while ordinary registration stays closed.
        anonymous = requests.Session()
        whoami = anonymous.get(BASE_URL + "/api/auth/me", timeout=30)
        assert whoami.status_code == 200 and whoami.json().get("user") is None
        assert whoami.headers.get("cache-control") == "no-store"
        no_state = anonymous.get(BASE_URL + "/api/me/state")
        assert no_state.status_code == 401
        assert no_state.headers.get("cache-control") == "no-store"

        primary = login(primary_name, passwords["p"])
        identity = primary.get(BASE_URL + "/api/auth/me", timeout=30)
        assert identity.status_code == 200
        assert identity.json()["user"]["username"] == primary_name

        # Two concurrent initial saves must serialize: exactly one revision-zero write wins.
        cookie = primary.cookies.get(COOKIE_NAME)
        assert cookie, "The primary session cookie is missing."
        barrier = Barrier(2)

        def first_write(title: str) -> requests.Response:
            barrier.wait(timeout=15)
            return requests.put(
                BASE_URL + "/api/me/state",
                headers={
                    "Origin": ORIGIN,
                    "Cookie": f"{COOKIE_NAME}={cookie}",
                    "Content-Type": "application/json",
                },
                json=state_payload(title, 0, "Concurrent first-write"),
                timeout=45,
            )

        titles = {"Staging concurrent write A", "Staging concurrent write B"}
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(first_write, "Staging concurrent write A")
            future_b = executor.submit(first_write, "Staging concurrent write B")
            writes = [future_a.result(timeout=60), future_b.result(timeout=60)]
        statuses = sorted(response.status_code for response in writes)
        assert statuses == [200, 409], [
            {"status": response.status_code, "body": response.text[:250]} for response in writes
        ]
        saved = primary.get(BASE_URL + "/api/me/state", timeout=30)
        assert saved.status_code == 200
        assert saved.headers.get("cache-control") == "no-store"
        assert saved.headers.get("etag") in ('"1"', 'W/"1"'), f"Expected revision-1 ETag, got {saved.headers.get('etag')!r}"
        saved_body = saved.json()
        assert saved_body["revision"] == 1 and saved_body["exists"] is True
        committed_title = saved_body["state"]["works"][0]["title"]
        assert committed_title in titles

        # Repeated stale revision must fail and must not overwrite the winning save.
        stale = primary.put(
            BASE_URL + "/api/me/state",
            headers={"Origin": ORIGIN},
            json=state_payload("Stale staging overwrite must not win", 0),
            timeout=30,
        )
        assert stale.status_code == 409, f"Stale write should return 409, got {stale.status_code}"
        still_saved = primary.get(BASE_URL + "/api/me/state", timeout=30).json()
        assert still_saved["revision"] == 1
        assert still_saved["state"]["works"][0]["title"] == committed_title

        # Sign out revokes the session; a fresh login restores the same Postgres snapshot.
        logout = primary.post(BASE_URL + "/api/auth/logout", headers={"Origin": ORIGIN}, timeout=30)
        assert logout.status_code == 204
        assert primary.get(BASE_URL + "/api/auth/me", timeout=30).json().get("user") is None
        assert primary.get(BASE_URL + "/api/me/state", timeout=30).status_code == 401

        primary_relogin = login(primary_name, passwords["p"])
        restored = primary_relogin.get(BASE_URL + "/api/me/state", timeout=30)
        assert restored.status_code == 200
        assert restored.json()["revision"] == 1
        assert restored.json()["state"]["works"][0]["title"] == committed_title

        # A second real account must have an independent snapshot and cannot see the first.
        secondary = login(secondary_name, passwords["s"])
        secondary_empty = secondary.get(BASE_URL + "/api/me/state", timeout=30)
        assert secondary_empty.status_code == 200
        assert secondary_empty.json() == {
            "exists": False, "revision": 0, "updated_at": None, "state": None
        }
        second_save = secondary.put(
            BASE_URL + "/api/me/state",
            headers={"Origin": ORIGIN},
            json=state_payload("Secondary account private library", 0, "Secondary staging user"),
            timeout=30,
        )
        assert second_save.status_code == 200 and second_save.json()["revision"] == 1

        primary_again = login(primary_name, passwords["p"])
        primary_private = primary_again.get(BASE_URL + "/api/me/state", timeout=30).json()
        assert primary_private["revision"] == 1
        assert primary_private["state"]["works"][0]["title"] == committed_title

        secondary_again = login(secondary_name, passwords["s"])
        secondary_private = secondary_again.get(BASE_URL + "/api/me/state", timeout=30).json()
        assert secondary_private["revision"] == 1
        assert secondary_private["state"]["works"][0]["title"] == "Secondary account private library"

        # Export contains the complete account/library payload but no password or session secrets.
        exported = secondary_again.get(BASE_URL + "/api/me/export", timeout=30)
        assert exported.status_code == 200, f"Account export failed: HTTP {exported.status_code}, {exported.text[:250]}"
        assert "attachment" in exported.headers.get("content-disposition", "").lower()
        assert exported.headers.get("cache-control") == "no-store"
        export_document = exported.json()
        assert export_document["format"] == "omnishelf-account-export"
        assert export_document["version"] == 1
        assert export_document["account"]["username"] == secondary_name
        assert export_document["cloud_library"]["revision"] == 1
        assert export_document["cloud_library"]["state"]["works"][0]["title"] == "Secondary account private library"
        encoded_export = json.dumps(export_document).lower()
        assert "password_hash" not in encoded_export and "token_hash" not in encoded_export
        assert "sessions" not in export_document

        # Deletion is password-confirmed, removes cloud state, and revokes all sessions.
        secondary_second_session = login(secondary_name, passwords["s"])
        wrong_delete = secondary_again.delete(
            BASE_URL + "/api/me/account",
            headers={"Origin": ORIGIN},
            json={"password": "incorrect-staging-password-for-test"},
            timeout=30,
        )
        assert wrong_delete.status_code == 403, f"Wrong-password delete should be denied, got {wrong_delete.status_code}"
        still_authenticated = secondary_again.get(BASE_URL + "/api/auth/me", timeout=30)
        assert still_authenticated.status_code == 200 and still_authenticated.json()["user"]["username"] == secondary_name
        still_saved = secondary_again.get(BASE_URL + "/api/me/state", timeout=30).json()
        assert still_saved["state"]["works"][0]["title"] == "Secondary account private library"

        delete_response = secondary_again.delete(
            BASE_URL + "/api/me/account",
            headers={"Origin": ORIGIN},
            json={"password": passwords["s"]},
            timeout=30,
        )
        assert delete_response.status_code == 204, (
            f"Password-confirmed account deletion failed: HTTP {delete_response.status_code}, {delete_response.text[:250]}"
        )
        assert "max-age=0" in delete_response.headers.get("set-cookie", "").lower()
        assert secondary_again.get(BASE_URL + "/api/auth/me", timeout=30).json().get("user") is None
        assert secondary_again.get(BASE_URL + "/api/me/state", timeout=30).status_code == 401
        assert secondary_second_session.get(BASE_URL + "/api/auth/me", timeout=30).json().get("user") is None
        assert secondary_second_session.get(BASE_URL + "/api/me/state", timeout=30).status_code == 401
        assert secondary_again.get(BASE_URL + "/api/me/export", timeout=30).status_code == 401

        # Deleting account two must not affect account one's data.
        primary_final = login(primary_name, passwords["p"])
        primary_final_state = primary_final.get(BASE_URL + "/api/me/state", timeout=30)
        assert primary_final_state.status_code == 200
        assert primary_final_state.json()["state"]["works"][0]["title"] == committed_title

        # Ordinary public registration must still be closed during this authenticated test.
        register = requests.post(
            BASE_URL + "/api/auth/register",
            json={
                "username": "stagingclosed",
                "email": "stagingclosed@example.invalid",
                "password": "NeverCreateThisAccount_123!",
            },
            timeout=30,
        )
        assert register.status_code == 403, f"Public registration unexpectedly returned {register.status_code}"

        print(json.dumps({
            "result": "passed",
            "staging_url": BASE_URL,
            "checks": [
                "ephemeral OIDC-authorized accounts",
                "Resend HTTPS simulated-delivery test accepted by the provider",
                "Secure/HttpOnly/SameSite session cookie",
                "registration stays closed",
                "two concurrent first saves produce one success and one 409",
                "stale revision cannot overwrite committed state",
                "logout revokes session",
                "cloud snapshot persists across fresh sign-in",
                "two-account snapshot isolation",
                "account export excludes password/session secrets",
                "wrong-password account deletion is denied",
                "password-confirmed account deletion revokes every session",
                "deleting account two does not affect account one's library",
            ],
            "temporary_accounts_created": 2,
            "email_test": {
                "result": email_result["result"],
                "recipient": email_result["recipient"],
                "is_real_inbox_delivery": False,
            },
            "credentials_logged": False,
        }, indent=2))
    finally:
        # This route deletes only the e2e accounts derived from this signed workflow run ID.
        result = assert_cleanup(oidc_token)
        print(f"Staging acceptance cleanup completed: {result['deleted_accounts']} temporary account(s) removed.")


if __name__ == "__main__":
    main()
