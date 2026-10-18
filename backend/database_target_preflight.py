"""Fail-closed, read-only target check before Alembic migrations.

On Render, require an explicit expected hostname and database name and compare
them to both DATABASE_URL and the connected server. Never print DATABASE_URL,
usernames, or passwords. This module issues SELECT statements only.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url


EXPECTED_HOST_ENV = "OMNISHELF_EXPECTED_DATABASE_HOST"
EXPECTED_DATABASE_ENV = "OMNISHELF_EXPECTED_DATABASE_NAME"
DATABASE_URL_ENV = "DATABASE_URL"


@dataclass(frozen=True)
class DatabaseIdentity:
    host: str
    database: str
    revision: str


def _normalized_url(database_url: str) -> URL:
    url = make_url(database_url)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    return url


def validate_database_target(
    database_url: str,
    expected_host: str,
    expected_database: str,
) -> list[str]:
    """Validate the configured target without opening a connection or exposing credentials."""
    errors: list[str] = []
    if not expected_host.strip():
        errors.append(f"Missing required setting: {EXPECTED_HOST_ENV}")
    if not expected_database.strip():
        errors.append(f"Missing required setting: {EXPECTED_DATABASE_ENV}")
    if not database_url.strip():
        errors.append(f"Missing required setting: {DATABASE_URL_ENV}")
    if errors:
        return errors

    try:
        url = _normalized_url(database_url)
    except Exception:
        return ["DATABASE_URL is not a valid database URL."]
    if url.drivername != "postgresql+psycopg":
        errors.append("Hosted DATABASE_URL must use PostgreSQL.")
    if not url.host:
        errors.append("DATABASE_URL must include a database hostname.")
    elif url.host.rstrip(".").casefold() != expected_host.strip().rstrip(".").casefold():
        errors.append(f"DATABASE_URL hostname does not match {EXPECTED_HOST_ENV}.")
    if not url.database:
        errors.append("DATABASE_URL must include a database name.")
    elif url.database != expected_database.strip():
        errors.append(f"DATABASE_URL database name does not match {EXPECTED_DATABASE_ENV}.")
    return errors


def read_database_identity(database_url: str) -> DatabaseIdentity:
    """Read current database name and Alembic revision; never writes to the database."""
    url = _normalized_url(database_url)
    engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT current_database() AS database_name")
            ).mappings().one()
            database_name = str(row["database_name"])
            if inspect(connection).has_table("alembic_version"):
                rows = connection.execute(
                    text("SELECT version_num FROM alembic_version ORDER BY version_num")
                ).all()
                revision = ",".join(str(value[0]) for value in rows) if rows else "empty"
            else:
                revision = "not-initialized"
        if not url.host:
            raise ValueError("Database hostname is missing.")
        return DatabaseIdentity(host=url.host, database=database_name, revision=revision)
    finally:
        engine.dispose()


def run_preflight(environment: Mapping[str, str] = os.environ) -> int:
    is_render = environment.get("RENDER", "").strip().lower() == "true"
    if not is_render:
        print("Database target guard skipped outside Render; local development migrations may continue.")
        return 0

    database_url = environment.get(DATABASE_URL_ENV, "")
    expected_host = environment.get(EXPECTED_HOST_ENV, "")
    expected_database = environment.get(EXPECTED_DATABASE_ENV, "")
    errors = validate_database_target(database_url, expected_host, expected_database)
    if errors:
        print("Hosted database target check failed; migrations are blocked:")
        for error in errors:
            print(f"- {error}")
        return 1

    try:
        identity = read_database_identity(database_url)
    except Exception:
        # Driver exceptions can embed connection details; suppress them to keep secrets out of logs.
        print("Could not verify the hosted database identity; migrations are blocked. Check connectivity and target settings.")
        return 1

    if identity.database != expected_database.strip():
        print(f"Connected database does not match {EXPECTED_DATABASE_ENV}; migrations are blocked.")
        return 1

    print(
        "Hosted database target verified (read-only): "
        f"host={identity.host}; database={identity.database}; applied_revision={identity.revision}. "
        "Connection credentials were not printed."
    )
    return 0


def main() -> int:
    return run_preflight()


if __name__ == "__main__":
    raise SystemExit(main())
