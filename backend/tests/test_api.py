from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

from backend import main


ORIGIN = {"Origin": "http://testserver"}


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Use an isolated SQLite database for every test; never touch the developer DB."""
    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'omnishelf-tests.db'}",
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    main.Base.metadata.create_all(test_engine)
    TestSession = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[main.get_db] = override_get_db
    monkeypatch.setattr(main, "REGISTRATION_ENABLED", True)
    monkeypatch.setattr(main, "COOKIE_SECURE", False)
    # Existing tests cover legacy local development mode; dedicated tests enable verification.
    monkeypatch.setattr(main, "EMAIL_VERIFICATION_REQUIRED", False)
    monkeypatch.setattr(main, "SMTP_CONFIGURED", False)

    with TestClient(main.app, base_url="http://testserver") as test_client:
        yield test_client

    main.app.dependency_overrides.clear()
    test_engine.dispose()


def register(client: TestClient, username: str = "storykeeper", email: str = "reader@example.com") -> dict:
    response = client.post(
        "/api/auth/register",
        headers=ORIGIN,
        json={"username": username, "email": email, "password": "secure-example-pass-123"},
    )
    assert response.status_code == 201, response.text
    return response.json()["user"]


def state_payload(title: str = "White Nights", expected_revision: int = 0) -> dict:
    return {
        "expected_revision": expected_revision,
        "state": {
            "profile": {"name": "Story Keeper"},
            "works": [{"title": title, "medium": "Novella", "status": "In Progress"}],
            "reviews": [],
            "activity": [],
            "customLists": [],
        },
    }


def test_api_and_health_report_version_and_database(client: TestClient) -> None:
    api = client.get("/api")
    assert api.status_code == 200
    assert api.json()["version"] == "1.3.9"

    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "database": "ok", "version": "1.3.9"}
    assert health.headers["x-content-type-options"] == "nosniff"
    assert health.headers["x-frame-options"] == "DENY"


def test_registration_can_be_kept_closed(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "REGISTRATION_ENABLED", False)
    response = client.post(
        "/api/auth/register",
        headers=ORIGIN,
        json={"username": "closeduser", "email": "closed@example.com", "password": "secure-example-pass-123"},
    )
    assert response.status_code == 403
    assert "temporarily disabled" in response.json()["detail"]


def test_registration_normalizes_identity_and_sets_http_only_session(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        headers=ORIGIN,
        json={"username": "  StoryKeeper  ", "email": " Reader@Example.com ", "password": "secure-example-pass-123"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["user"]["username"] == "storykeeper"
    assert response.json()["user"]["email"] == "reader@example.com"

    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "secure" not in cookie
    assert client.get("/api/auth/me").json()["user"]["username"] == "storykeeper"


def test_duplicate_username_or_email_is_rejected(client: TestClient) -> None:
    register(client)
    duplicate_username = client.post(
        "/api/auth/register",
        headers=ORIGIN,
        json={"username": "storykeeper", "email": "other@example.com", "password": "secure-example-pass-123"},
    )
    assert duplicate_username.status_code == 409

    duplicate_email = client.post(
        "/api/auth/register",
        headers=ORIGIN,
        json={"username": "anotherperson", "email": "reader@example.com", "password": "secure-example-pass-123"},
    )
    assert duplicate_email.status_code == 409


def test_login_rejects_untrusted_or_missing_origin(client: TestClient) -> None:
    register(client)
    blocked = client.post(
        "/api/auth/login",
        headers={"Origin": "https://attacker.example"},
        json={"identifier": "storykeeper", "password": "secure-example-pass-123"},
    )
    assert blocked.status_code == 403

    missing = client.post(
        "/api/auth/login",
        json={"identifier": "storykeeper", "password": "secure-example-pass-123"},
    )
    assert missing.status_code == 403

def test_auth_rate_limits_are_shared_between_clients_and_expire(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(main._RATE_LIMITS, "login", (2, 900))
    monkeypatch.setattr(main, "RENDER_ENVIRONMENT", True)
    second_client = TestClient(main.app, base_url="http://testserver")
    try:
        first = client.post(
            "/api/auth/login",
            headers={**ORIGIN, "X-Forwarded-For": "203.0.113.44, 198.51.100.99"},
            json={"identifier": "unknown-reader", "password": "wrong-password"},
        )
        second = second_client.post(
            "/api/auth/login",
            headers={**ORIGIN, "X-Forwarded-For": "203.0.113.44, 198.51.100.23"},
            json={"identifier": "unknown-reader", "password": "wrong-password"},
        )
        blocked = client.post(
            "/api/auth/login",
            headers={**ORIGIN, "X-Forwarded-For": "203.0.113.44, 198.51.100.40"},
            json={"identifier": "unknown-reader", "password": "wrong-password"},
        )
        assert first.status_code == 401
        assert second.status_code == 401
        assert blocked.status_code == 429
        assert int(blocked.headers["retry-after"]) > 0
        assert blocked.headers["cache-control"] == "no-store"

        # Move the shared row beyond its configured window and ensure the counter resets.
        test_engine = create_engine(f"sqlite:///{tmp_path / 'omnishelf-tests.db'}")
        try:
            with test_engine.begin() as connection:
                connection.execute(
                    update(main.AuthRateLimit)
                    .where(main.AuthRateLimit.action == "login")
                    .values(window_started=datetime.now(timezone.utc) - timedelta(minutes=20), attempts=3)
                )
        finally:
            test_engine.dispose()

        after_window = second_client.post(
            "/api/auth/login",
            headers={**ORIGIN, "X-Forwarded-For": "203.0.113.44, 198.51.100.10"},
            json={"identifier": "unknown-reader", "password": "wrong-password"},
        )
        assert after_window.status_code == 401
    finally:
        second_client.close()


def test_cloud_state_round_trip_and_stale_revision_conflict(client: TestClient) -> None:
    register(client)
    first = client.put("/api/me/state", headers=ORIGIN, json=state_payload())
    assert first.status_code == 200, first.text
    assert first.json()["revision"] == 1
    assert first.json()["work_count"] == 1

    read = client.get("/api/me/state")
    assert read.status_code == 200
    assert read.json()["exists"] is True
    assert read.json()["state"]["works"][0]["title"] == "White Nights"
    assert read.headers["etag"] == '"1"'

    update = client.put("/api/me/state", headers=ORIGIN, json=state_payload("The Metamorphosis", 1))
    assert update.status_code == 200, update.text
    assert update.json()["revision"] == 2

    stale = client.put("/api/me/state", headers=ORIGIN, json=state_payload("Stale overwrite", 1))
    assert stale.status_code == 409

    after_conflict = client.get("/api/me/state").json()
    assert after_conflict["revision"] == 2
    assert after_conflict["state"]["works"][0]["title"] == "The Metamorphosis"


def test_cloud_state_is_private_to_each_account(client: TestClient) -> None:
    register(client, "firstreader", "first@example.com")
    saved = client.put("/api/me/state", headers=ORIGIN, json=state_payload("Private library"))
    assert saved.status_code == 200

    second_client = TestClient(main.app, base_url="http://testserver")
    try:
        register(second_client, "secondreader", "second@example.com")
        second_state = second_client.get("/api/me/state")
        assert second_state.status_code == 200
        assert second_state.json() == {"exists": False, "revision": 0, "updated_at": None, "state": None}
    finally:
        second_client.close()


def test_state_requires_origin_and_validates_shape(client: TestClient) -> None:
    register(client)

    missing_origin = client.put("/api/me/state", json=state_payload())
    assert missing_origin.status_code == 403

    invalid = client.put(
        "/api/me/state",
        headers=ORIGIN,
        json={"expected_revision": 0, "state": {"profile": {}, "works": [{"title": " "}]}}
    )
    assert invalid.status_code == 422


def test_logout_revokes_session_and_cloud_access(client: TestClient) -> None:
    register(client)
    assert client.get("/api/auth/me").json()["user"] is not None

    logged_out = client.post("/api/auth/logout", headers=ORIGIN)
    assert logged_out.status_code == 204
    assert client.get("/api/auth/me").json()["user"] is None
    assert client.get("/api/me/state").status_code == 401

def test_production_session_cookie_is_secure_and_response_has_hsts(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "COOKIE_SECURE", True)
    secure_client = TestClient(main.app, base_url="https://testserver")
    try:
        response = secure_client.post(
            "/api/auth/register",
            headers={"Origin": "https://testserver"},
            json={"username": "secure_reader", "email": "secure@example.com", "password": "secure-example-pass-123"},
        )
        assert response.status_code == 201, response.text
        cookie = response.headers["set-cookie"].lower()
        assert "secure" in cookie
        assert "httponly" in cookie
        assert "samesite=lax" in cookie
        assert response.headers["strict-transport-security"].startswith("max-age=31536000")
        assert response.headers["cache-control"] == "no-store"
    finally:
        secure_client.close()


def test_oversized_request_is_rejected_before_route_processing(client: TestClient) -> None:
    declared_size = main.MAX_STATE_BYTES + 1024 * 1024 + 1
    response = client.post(
        "/api/auth/login",
        headers={"Content-Length": str(declared_size), **ORIGIN},
        content=b"x",
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "Request body is too large."


def test_backend_serves_the_real_139_frontend_shell(client: TestClient) -> None:
    page = client.get("/")
    assert page.status_code == 200
    assert "text/html" in page.headers.get("content-type", "")
    assert 'content="1.3.9"' in page.text
    assert "Every story has a place." in page.text

    api = client.get("/api")
    assert api.status_code == 200
    assert api.json()["cloud_state"] == "/api/me/state"

def test_account_export_includes_library_but_never_credentials_or_sessions(client: TestClient) -> None:
    register(client)
    saved = client.put("/api/me/state", headers=ORIGIN, json=state_payload("Exportable library"))
    assert saved.status_code == 200

    exported = client.get("/api/me/export")
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("application/json")
    assert "attachment" in exported.headers.get("content-disposition", "").lower()
    assert exported.headers["cache-control"] == "no-store"
    document = exported.json()
    assert document["format"] == "omnishelf-account-export"
    assert document["version"] == 1
    assert document["account"]["username"] == "storykeeper"
    assert document["account"]["email"] == "reader@example.com"
    assert document["cloud_library"]["exists"] is True
    assert document["cloud_library"]["revision"] == 1
    assert document["cloud_library"]["state"]["works"][0]["title"] == "Exportable library"
    encoded = __import__("json").dumps(document).lower()
    assert "password_hash" not in encoded
    assert "token_hash" not in encoded
    assert '"sessions"' not in encoded


def test_account_deletion_requires_password_and_revokes_every_session(client: TestClient) -> None:
    register(client)
    saved = client.put("/api/me/state", headers=ORIGIN, json=state_payload("Private before deletion"))
    assert saved.status_code == 200

    second_client = TestClient(main.app, base_url="http://testserver")
    try:
        login = second_client.post(
            "/api/auth/login",
            headers=ORIGIN,
            json={"identifier": "storykeeper", "password": "secure-example-pass-123"},
        )
        assert login.status_code == 200, login.text

        wrong_password = client.request(
            "DELETE",
            "/api/me/account",
            headers=ORIGIN,
            json={"password": "incorrect-password"},
        )
        assert wrong_password.status_code == 403
        assert client.get("/api/auth/me").json()["user"] is not None
        assert client.get("/api/me/state").json()["state"]["works"][0]["title"] == "Private before deletion"

        deleted = client.request(
            "DELETE",
            "/api/me/account",
            headers=ORIGIN,
            json={"password": "secure-example-pass-123"},
        )
        assert deleted.status_code == 204
        assert "max-age=0" in deleted.headers.get("set-cookie", "").lower()
        assert client.get("/api/auth/me").json()["user"] is None
        assert client.get("/api/me/state").status_code == 401
        assert second_client.get("/api/auth/me").json()["user"] is None
        assert second_client.get("/api/me/state").status_code == 401
        assert client.get("/api/me/export").status_code == 401
    finally:
        second_client.close()


def test_staging_acceptance_routes_are_not_available_in_default_preview_mode(
    client: TestClient,
) -> None:
    """Staging bootstrap endpoints must stay absent unless a dedicated service opts in."""
    assert main.STAGING_ACCEPTANCE_ENABLED is False
    response = client.post("/__staging/acceptance/cleanup")
    assert response.status_code in (404, 405)



def _email_link_token(body: str, query_key: str) -> str:
    link = next((line.strip() for line in body.splitlines() if f"{query_key}=" in line), None)
    assert link, f"No {query_key} link was included in the delivered message."
    parsed = urlparse(link)
    query = parse_qs(parsed.query)
    if query_key in query:
        return query[query_key][0]
    fragment = parsed.fragment.split("?", 1)[1] if "?" in parsed.fragment else ""
    return parse_qs(fragment)[query_key][0]


def test_email_verification_requires_one_time_token_and_resend_invalidates_old_link(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "EMAIL_VERIFICATION_REQUIRED", True)
    monkeypatch.setattr(main, "SMTP_CONFIGURED", True)
    delivered: list[tuple[str, str, str]] = []
    monkeypatch.setattr(main, "_send_email", lambda to, subject, body: delivered.append((to, subject, body)))

    created = client.post(
        "/api/auth/register",
        headers=ORIGIN,
        json={"username": "verifyreader", "email": "verify@example.com", "password": "secure-example-pass-123"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["requires_email_verification"] is True
    assert "set-cookie" not in created.headers
    assert len(delivered) == 1
    old_token = _email_link_token(delivered[0][2], "verify_email")

    login_before_verification = client.post(
        "/api/auth/login",
        headers=ORIGIN,
        json={"identifier": "verifyreader", "password": "secure-example-pass-123"},
    )
    assert login_before_verification.status_code == 403
    assert "verify your email" in login_before_verification.json()["detail"].lower()

    resend = client.post(
        "/api/auth/verification-email",
        headers=ORIGIN,
        json={"email": "verify@example.com"},
    )
    assert resend.status_code == 202
    assert len(delivered) == 2
    new_token = _email_link_token(delivered[1][2], "verify_email")
    assert old_token != new_token

    stale = client.post("/api/auth/verify-email", headers=ORIGIN, json={"token": old_token})
    assert stale.status_code == 400
    verified = client.post("/api/auth/verify-email", headers=ORIGIN, json={"token": new_token})
    assert verified.status_code == 200, verified.text
    assert verified.json()["verified"] is True
    assert verified.json()["user"]["email_verified"] is True

    replay = client.post("/api/auth/verify-email", headers=ORIGIN, json={"token": new_token})
    assert replay.status_code == 400
    signed_in = client.post(
        "/api/auth/login",
        headers=ORIGIN,
        json={"identifier": "verifyreader", "password": "secure-example-pass-123"},
    )
    assert signed_in.status_code == 200
    assert signed_in.json()["user"]["email_verified"] is True


def test_password_reset_uses_single_use_token_and_revokes_all_sessions(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    register(client, username="resetreader", email="reset@example.com")
    monkeypatch.setattr(main, "SMTP_CONFIGURED", True)
    delivered: list[tuple[str, str, str]] = []
    monkeypatch.setattr(main, "_send_email", lambda to, subject, body: delivered.append((to, subject, body)))

    request = client.post(
        "/api/auth/password-reset/request",
        headers=ORIGIN,
        json={"email": "reset@example.com"},
    )
    assert request.status_code == 202
    assert len(delivered) == 1
    token = _email_link_token(delivered[0][2], "reset_password")

    missing = client.post(
        "/api/auth/password-reset/request",
        headers=ORIGIN,
        json={"email": "not-an-account@example.com"},
    )
    assert missing.status_code == 202
    assert missing.json() == request.json()

    updated = client.post(
        "/api/auth/password-reset/confirm",
        headers=ORIGIN,
        json={"token": token, "password": "a-new-secure-password-456"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["reset"] is True
    # The session created by register() must no longer authenticate after a reset.
    assert client.get("/api/auth/me").json()["user"] is None

    old_password = client.post(
        "/api/auth/login",
        headers=ORIGIN,
        json={"identifier": "resetreader", "password": "secure-example-pass-123"},
    )
    assert old_password.status_code == 401
    new_password = client.post(
        "/api/auth/login",
        headers=ORIGIN,
        json={"identifier": "resetreader", "password": "a-new-secure-password-456"},
    )
    assert new_password.status_code == 200

    replay = client.post(
        "/api/auth/password-reset/confirm",
        headers=ORIGIN,
        json={"token": token, "password": "another-secure-password-789"},
    )
    assert replay.status_code == 400


def test_verification_registration_fails_closed_without_smtp(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "EMAIL_VERIFICATION_REQUIRED", True)
    monkeypatch.setattr(main, "SMTP_CONFIGURED", False)
    response = client.post(
        "/api/auth/register",
        headers=ORIGIN,
        json={"username": "blockedreader", "email": "blocked@example.com", "password": "secure-example-pass-123"},
    )
    assert response.status_code == 503
    assert "email delivery is not configured" in response.json()["detail"].lower()
