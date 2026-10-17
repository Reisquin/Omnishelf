from __future__ import annotations

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import main


POSTGRES_TEST_URL = os.getenv("OMNISHELF_POSTGRES_TEST_URL", "")
ORIGIN = {"Origin": "http://testserver"}
pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL.startswith(("postgresql://", "postgresql+psycopg://")),
    reason="Set OMNISHELF_POSTGRES_TEST_URL to run PostgreSQL integration tests.",
)


@pytest.fixture()
def postgres_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Use a disposable PostgreSQL database supplied only by the CI service container."""
    engine = create_engine(
        POSTGRES_TEST_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
    )
    main.Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    previous_overrides = main.app.dependency_overrides.copy()
    main.app.dependency_overrides[main.get_db] = override_get_db
    monkeypatch.setattr(main, "REGISTRATION_ENABLED", True)
    monkeypatch.setattr(main, "COOKIE_SECURE", False)
    monkeypatch.setattr(main, "EMAIL_VERIFICATION_REQUIRED", False)
    monkeypatch.setattr(main, "SMTP_CONFIGURED", False)

    try:
        with TestClient(main.app, base_url="http://testserver") as client:
            yield client
    finally:
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(previous_overrides)
        main.Base.metadata.drop_all(engine)
        engine.dispose()
    

def register(client: TestClient, username: str, email: str) -> dict:
    response = client.post(
        "/api/auth/register",
        headers=ORIGIN,
        json={
            "username": username,
            "email": email,
            "password": "integration-test-password-123",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["user"]


def state_payload(title: str, expected_revision: int = 0) -> dict:
    return {
        "expected_revision": expected_revision,
        "state": {
            "profile": {"name": "PostgreSQL Integration Test"},
            "works": [{"title": title, "medium": "Novella", "status": "In Progress"}],
            "reviews": [],
            "activity": [],
            "customLists": [],
        },
    }


def test_postgres_rejects_stale_revision_without_overwriting_latest_state(postgres_client: TestClient) -> None:
    register(postgres_client, "pg_revision_reader", "pg-revision@example.com")

    first = postgres_client.put(
        "/api/me/state",
        headers=ORIGIN,
        json=state_payload("First committed version", 0),
    )
    assert first.status_code == 200, first.text
    assert first.json()["revision"] == 1

    stale = postgres_client.put(
        "/api/me/state",
        headers=ORIGIN,
        json=state_payload("Stale overwrite must not win", 0),
    )
    assert stale.status_code == 409, stale.text

    latest = postgres_client.get("/api/me/state")
    assert latest.status_code == 200
    assert latest.json()["revision"] == 1
    assert latest.json()["state"]["works"][0]["title"] == "First committed version"


def test_postgres_serializes_concurrent_first_snapshot_writes(postgres_client: TestClient) -> None:
    register(postgres_client, "pg_race_reader", "pg-race@example.com")
    token = postgres_client.cookies.get(main.COOKIE_NAME)
    assert token, "Registration should issue a session cookie"

    # Send the same opaque session cookie explicitly on both clients so the test exercises
    # concurrent saves, not differences in TestClient cookie-jar domain matching.
    postgres_client.cookies.clear()
    with TestClient(main.app, base_url="http://testserver") as second_client:
        start_together = Barrier(2)

        def save(client: TestClient, title: str):
            start_together.wait(timeout=10)
            return client.put(
                "/api/me/state",
                headers={**ORIGIN, "Cookie": f"{main.COOKIE_NAME}={token}"},
                json=state_payload(title, expected_revision=0),
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(save, postgres_client, "Concurrent write A"),
                pool.submit(save, second_client, "Concurrent write B"),
            ]
            responses = [future.result(timeout=30) for future in futures]

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200, 409], [
        {"status": response.status_code, "body": response.text} for response in responses
    ]

    latest = postgres_client.get("/api/me/state", headers={"Cookie": f"{main.COOKIE_NAME}={token}"})
    assert latest.status_code == 200
    assert latest.json()["revision"] == 1
    assert latest.json()["state"]["works"][0]["title"] in {
        "Concurrent write A",
        "Concurrent write B",
    }


def test_postgres_session_and_snapshot_persist_after_relogin_and_are_account_scoped(
    postgres_client: TestClient,
) -> None:
    register(postgres_client, "pg_owner_reader", "pg-owner@example.com")
    saved = postgres_client.put(
        "/api/me/state",
        headers=ORIGIN,
        json=state_payload("A persistent private library", 0),
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == 1

    logout = postgres_client.post("/api/auth/logout", headers=ORIGIN)
    assert logout.status_code == 204
    assert postgres_client.get("/api/auth/me").json()["user"] is None

    # A new client signs in, proving the session and snapshot can be reconstructed from PostgreSQL.
    with TestClient(main.app, base_url="http://testserver") as relogin_client:
        login = relogin_client.post(
            "/api/auth/login",
            headers=ORIGIN,
            json={
                "identifier": "pg_owner_reader",
                "password": "integration-test-password-123",
            },
        )
        assert login.status_code == 200, login.text
        assert "httponly" in login.headers.get("set-cookie", "").lower()
        assert "samesite=lax" in login.headers.get("set-cookie", "").lower()

        restored = relogin_client.get("/api/me/state")
        assert restored.status_code == 200
        assert restored.json()["revision"] == 1
        assert restored.json()["state"]["works"][0]["title"] == "A persistent private library"

        # A different account cannot read another user's snapshot.
        with TestClient(main.app, base_url="http://testserver") as other_client:
            register(other_client, "pg_other_reader", "pg-other@example.com")
            other_state = other_client.get("/api/me/state")
            assert other_state.status_code == 200
            assert other_state.json() == {
                "exists": False,
                "revision": 0,
                "updated_at": None,
                "state": None,
            }



def test_postgres_https_login_works_while_registration_is_closed(
    postgres_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the production auth mode over HTTP routes without opening live sign-up."""
    existing_password = "integration-test-password-123"
    other_password = "integration-test-password-123"

    # Seed only the disposable CI database while the fixture's test registration path is open.
    register(postgres_client, "pg_secure_existing", "pg-secure-existing@example.com")
    with TestClient(main.app, base_url="http://testserver") as setup_other_client:
        register(setup_other_client, "pg_secure_other", "pg-secure-other@example.com")

    # Production mode: users can sign in, but new public account creation is closed.
    monkeypatch.setattr(main, "REGISTRATION_ENABLED", False)
    monkeypatch.setattr(main, "COOKIE_SECURE", True)
    https_origin = {"Origin": "https://testserver"}

    with TestClient(main.app, base_url="https://testserver") as secure_client:
        blocked_registration = secure_client.post(
            "/api/auth/register",
            headers=https_origin,
            json={
                "username": "pg_must_stay_closed",
                "email": "pg-must-stay-closed@example.com",
                "password": existing_password,
            },
        )
        assert blocked_registration.status_code == 403, blocked_registration.text

        login = secure_client.post(
            "/api/auth/login",
            headers=https_origin,
            json={"identifier": "pg_secure_existing", "password": existing_password},
        )
        assert login.status_code == 200, login.text
        cookie = login.headers.get("set-cookie", "").lower()
        assert "secure" in cookie
        assert "httponly" in cookie
        assert "samesite=lax" in cookie
        assert login.headers.get("cache-control") == "no-store"
        assert login.headers.get("strict-transport-security", "").startswith("max-age=")
        assert secure_client.get("/api/auth/me").json()["user"]["username"] == "pg_secure_existing"

        saved = secure_client.put(
            "/api/me/state",
            headers=https_origin,
            json=state_payload("HTTPS production-mode library", 0),
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["revision"] == 1

        read = secure_client.get("/api/me/state")
        assert read.status_code == 200
        assert read.headers.get("cache-control") == "no-store"
        assert read.headers.get("etag") == '"1"'
        assert read.json()["state"]["works"][0]["title"] == "HTTPS production-mode library"

        stale = secure_client.put(
            "/api/me/state",
            headers=https_origin,
            json=state_payload("Stale write must not win", 0),
        )
        assert stale.status_code == 409, stale.text
        assert secure_client.get("/api/me/state").json()["state"]["works"][0]["title"] == "HTTPS production-mode library"

        logout = secure_client.post("/api/auth/logout", headers=https_origin)
        assert logout.status_code == 204
        assert secure_client.get("/api/auth/me").json()["user"] is None
        no_session = secure_client.get("/api/me/state")
        assert no_session.status_code == 401
        assert no_session.headers.get("cache-control") == "no-store"

    # A new secure session restores the same PostgreSQL snapshot after sign-out/sign-in.
    with TestClient(main.app, base_url="https://testserver") as relogin_client:
        login = relogin_client.post(
            "/api/auth/login",
            headers=https_origin,
            json={"identifier": "pg_secure_existing", "password": existing_password},
        )
        assert login.status_code == 200, login.text
        restored = relogin_client.get("/api/me/state")
        assert restored.status_code == 200
        assert restored.json()["revision"] == 1
        assert restored.json()["state"]["works"][0]["title"] == "HTTPS production-mode library"

    # A second existing account still sees no snapshot belonging to the first account.
    with TestClient(main.app, base_url="https://testserver") as other_client:
        login = other_client.post(
            "/api/auth/login",
            headers=https_origin,
            json={"identifier": "pg_secure_other", "password": other_password},
        )
        assert login.status_code == 200, login.text
        other_state = other_client.get("/api/me/state")
        assert other_state.status_code == 200
        assert other_state.json() == {
            "exists": False,
            "revision": 0,
            "updated_at": None,
            "state": None,
        }


def test_postgres_account_export_and_deletion_revoke_all_sessions(postgres_client: TestClient) -> None:
    register(postgres_client, "pg_delete_reader", "pg-delete-reader@example.com")
    saved = postgres_client.put(
        "/api/me/state",
        headers=ORIGIN,
        json=state_payload("Delete-account PostgreSQL fixture", 0),
    )
    assert saved.status_code == 200

    with TestClient(main.app, base_url="http://testserver") as second_session:
        signed_in = second_session.post(
            "/api/auth/login",
            headers=ORIGIN,
            json={
                "identifier": "pg_delete_reader",
                "password": "integration-test-password-123",
            },
        )
        assert signed_in.status_code == 200

        exported = postgres_client.get("/api/me/export")
        assert exported.status_code == 200
        assert exported.json()["cloud_library"]["state"]["works"][0]["title"] == "Delete-account PostgreSQL fixture"
        assert "password_hash" not in str(exported.json())
        assert "token_hash" not in str(exported.json())

        deleted = postgres_client.request(
            "DELETE",
            "/api/me/account",
            headers=ORIGIN,
            json={"password": "integration-test-password-123"},
        )
        assert deleted.status_code == 204
        assert postgres_client.get("/api/auth/me").json()["user"] is None
        assert postgres_client.get("/api/me/state").status_code == 401
        assert second_session.get("/api/auth/me").json()["user"] is None
        assert second_session.get("/api/me/state").status_code == 401

def test_postgres_rate_limit_is_shared_and_concurrency_safe(postgres_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(main._RATE_LIMITS, "login", (3, 900))
    clients = [TestClient(main.app, base_url="http://testserver") for _ in range(8)]
    try:
        def attempt(client: TestClient):
            return client.post(
                "/api/auth/login",
                headers=ORIGIN,
                json={"identifier": "unknown-rate-reader", "password": "wrong-password"},
            )

        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(attempt, clients))
        assert sum(response.status_code == 401 for response in responses) == 3
        rejected = [response for response in responses if response.status_code == 429]
        assert len(rejected) == 5
        assert all(int(response.headers["retry-after"]) > 0 for response in rejected)
        another = clients[0].post(
            "/api/auth/login",
            headers=ORIGIN,
            json={"identifier": "unknown-rate-reader", "password": "wrong-password"},
        )
        assert another.status_code == 429
    finally:
        for test_client in clients:
            test_client.close()



def test_postgres_email_verification_uses_one_time_hashed_token(
    postgres_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "EMAIL_VERIFICATION_REQUIRED", True)
    monkeypatch.setattr(main, "SMTP_CONFIGURED", True)
    delivered: list[tuple[str, str, str]] = []
    monkeypatch.setattr(main, "_send_email", lambda to, subject, body: delivered.append((to, subject, body)))

    created = postgres_client.post(
        "/api/auth/register",
        headers=ORIGIN,
        json={
            "username": "pg_verified_reader",
            "email": "pg-verified@example.com",
            "password": "integration-test-password-123",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["requires_email_verification"] is True
    assert "set-cookie" not in created.headers
    assert len(delivered) == 1
    link = next(line.strip() for line in delivered[0][2].splitlines() if "verify_email=" in line)
    token = parse_qs(urlparse(link).query)["verify_email"][0]

    session = postgres_client.post(
        "/api/auth/login",
        headers=ORIGIN,
        json={"identifier": "pg_verified_reader", "password": "integration-test-password-123"},
    )
    assert session.status_code == 403

    verified = postgres_client.post("/api/auth/verify-email", headers=ORIGIN, json={"token": token})
    assert verified.status_code == 200, verified.text
    assert verified.json()["user"]["email_verified"] is True
    replay = postgres_client.post("/api/auth/verify-email", headers=ORIGIN, json={"token": token})
    assert replay.status_code == 400

    signed_in = postgres_client.post(
        "/api/auth/login",
        headers=ORIGIN,
        json={"identifier": "pg_verified_reader", "password": "integration-test-password-123"},
    )
    assert signed_in.status_code == 200
    assert signed_in.json()["user"]["email_verified"] is True
