from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
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
    main._rate_buckets.clear()

    with TestClient(main.app, base_url="http://testserver") as test_client:
        yield test_client

    main.app.dependency_overrides.clear()
    main._rate_buckets.clear()
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
    assert api.json()["version"] == "1.3.8"

    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "database": "ok", "version": "1.3.8"}
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


def test_backend_serves_the_real_1358_frontend_shell(client: TestClient) -> None:
    page = client.get("/")
    assert page.status_code == 200
    assert "text/html" in page.headers.get("content-type", "")
    assert 'content="1.3.8"' in page.text
    assert "Every story has a place." in page.text

    api = client.get("/api")
    assert api.status_code == 200
    assert api.json()["cloud_state"] == "/api/me/state"

def test_staging_acceptance_routes_are_not_available_in_default_preview_mode(
    client: TestClient,
) -> None:
    """Staging bootstrap endpoints must stay absent unless a dedicated service opts in."""
    assert main.STAGING_ACCEPTANCE_ENABLED is False
    response = client.post("/__staging/acceptance/cleanup")
    assert response.status_code in (404, 405)
