from __future__ import annotations

from backend import database_target_preflight as preflight


EXPECTED_URL = "postgresql+psycopg://private-user:private-password@ep-approved-pooler.example.neon.tech/omnishelf?sslmode=require"
EXPECTED_ENV = {
    "RENDER": "true",
    "DATABASE_URL": EXPECTED_URL,
    "OMNISHELF_EXPECTED_DATABASE_HOST": "ep-approved-pooler.example.neon.tech",
    "OMNISHELF_EXPECTED_DATABASE_NAME": "omnishelf",
}


def test_database_target_rejects_hostname_or_database_mismatch_without_echoing_url() -> None:
    errors = preflight.validate_database_target(
        "postgresql+psycopg://secret-user:secret-password@ep-unexpected.example.neon.tech/wrong_db",
        "ep-approved.example.neon.tech",
        "omnishelf",
    )

    assert any("hostname" in error for error in errors)
    assert any("database name" in error for error in errors)
    assert all("secret-password" not in error for error in errors)
    assert all("ep-unexpected" not in error for error in errors)


def test_render_guard_blocks_mismatched_target_before_connecting(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        preflight,
        "create_engine",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not connect")),
    )
    environment = {
        **EXPECTED_ENV,
        "OMNISHELF_EXPECTED_DATABASE_HOST": "ep-some-other-branch.example.neon.tech",
    }

    result = preflight.run_preflight(environment)
    output = capsys.readouterr().out

    assert result == 1
    assert "migrations are blocked" in output
    assert "private-password" not in output
    assert "private-user" not in output
    assert "ep-approved-pooler" not in output


class FakeResult:
    def __init__(self, database_name: str | None = None) -> None:
        self.database_name = database_name

    def mappings(self):
        return self

    def one(self):
        return {"database_name": self.database_name}

    def all(self):
        return [("002_shared_auth_rate_limits",)]


class FakeConnection:
    def __init__(self, database_name: str) -> None:
        self.database_name = database_name

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, statement):
        if "current_database" in str(statement):
            return FakeResult(self.database_name)
        return FakeResult()


class FakeEngine:
    def __init__(self, database_name: str) -> None:
        self.database_name = database_name
        self.disposed = False

    def connect(self):
        return FakeConnection(self.database_name)

    def dispose(self):
        self.disposed = True


class FakeInspector:
    def has_table(self, name: str) -> bool:
        assert name == "alembic_version"
        return True


def test_read_only_preflight_confirms_database_and_revision_without_credentials(monkeypatch, capsys) -> None:
    engine = FakeEngine("omnishelf")
    monkeypatch.setattr(preflight, "create_engine", lambda *args, **kwargs: engine)
    monkeypatch.setattr(preflight, "inspect", lambda connection: FakeInspector())

    result = preflight.run_preflight(EXPECTED_ENV)
    output = capsys.readouterr().out

    assert result == 0
    assert "host=ep-approved-pooler.example.neon.tech" in output
    assert "database=omnishelf" in output
    assert "applied_revision=002_shared_auth_rate_limits" in output
    assert "private-password" not in output
    assert "private-user" not in output
    assert engine.disposed


def test_connected_database_name_mismatch_blocks_migrations(monkeypatch, capsys) -> None:
    engine = FakeEngine("different_database")
    monkeypatch.setattr(preflight, "create_engine", lambda *args, **kwargs: engine)
    monkeypatch.setattr(preflight, "inspect", lambda connection: FakeInspector())

    result = preflight.run_preflight(EXPECTED_ENV)
    output = capsys.readouterr().out

    assert result == 1
    assert "migrations are blocked" in output
    assert "different_database" not in output
    assert "private-password" not in output


def test_local_development_skips_hosted_target_guard(capsys) -> None:
    result = preflight.run_preflight({"RENDER": "false"})
    output = capsys.readouterr().out

    assert result == 0
    assert "skipped outside Render" in output
