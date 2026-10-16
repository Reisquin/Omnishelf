from __future__ import annotations

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

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
    main._rate_buckets.clear()

    try:
        with TestClient(main.app, base_url="http://testserver") as client:
            yield client
    finally:
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(previous_overrides)
        main.Base.metadata.drop_all(engine)
        engine.dispose()
        main._rate_buckets.clear()


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

    # Each TestClient has its own cookie jar and issues requests through its own client.
    with TestClient(main.app, base_url="http://testserver") as second_client:
        second_client.cookies.set(main.COOKIE_NAME, token, domain="testserver", path="/")
        start_together = Barrier(2)

        def save(client: TestClient, title: str):
            start_together.wait(timeout=10)
            return client.put(
                "/api/me/state",
                headers=ORIGIN,
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

    latest = postgres_client.get("/api/me/state")
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
