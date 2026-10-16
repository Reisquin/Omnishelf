"""Data-bearing PostgreSQL backup/restore drill for disposable CI databases.

Seeds one non-login canary into the CI Postgres service, takes a custom-format
pg_dump, restores it into a fresh database, and asserts that the schema,
migration marker, account row, revision number, and library payload survived.
The restore target is created by this script and is always dropped at the end.
Never point this script at a production database.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.types.json import Json


def run_checked(label: str, command: list[str], env: dict[str, str]) -> None:
    result = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    if result.returncode:
        # Do not print command arguments because they may contain database credentials.
        detail = (result.stderr or result.stdout or "no diagnostic output").strip()[-1600:]
        raise RuntimeError(f"{label} failed with exit code {result.returncode}: {detail}")


def main() -> None:
    dsn = os.getenv("BACKUP_RESTORE_TEST_DSN", "")
    if not dsn.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("BACKUP_RESTORE_TEST_DSN must point to the disposable CI PostgreSQL service.")
    conninfo = conninfo_to_dict(dsn)
    host = conninfo.get("host", "127.0.0.1")
    port = conninfo.get("port", "5432")
    user = conninfo.get("user", "postgres")
    source_db = conninfo.get("dbname", "")
    if source_db != "omnishelf_test" or host not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("Refusing to run backup/restore drill outside the expected disposable local CI database.")

    env = os.environ.copy()
    if conninfo.get("password"):
        env["PGPASSWORD"] = conninfo["password"]
    options = ["--host", host, "--port", str(port), "--username", user]

    suffix = uuid.uuid4().hex[:12]
    user_id = f"backup-restore-{suffix}"
    username = f"backup_restore_{suffix}"
    email = f"backup-restore-{suffix}@example.invalid"
    canary_title = f"BACKUP_RESTORE_CANARY_{suffix}"
    target_db = f"omnishelf_restore_{suffix}"
    payload = {
        "profile": {"name": "PostgreSQL Backup Restore Canary", "handle": username},
        "works": [{
            "id": f"canary-{suffix}",
            "title": canary_title,
            "medium": "Novella",
            "status": "In Progress",
            "progress": 12,
            "total": 40,
            "unit": "pages",
        }],
        "reviews": [],
        "activity": [],
        "customLists": [],
    }

    target_created = False
    with tempfile.TemporaryDirectory(prefix="omnishelf-backup-restore-") as temp_dir:
        archive = Path(temp_dir) / "omnishelf-ci-backup.dump"
        try:
            with psycopg.connect(dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT version_num FROM alembic_version")
                    source_migration = cursor.fetchone()
                    if not source_migration:
                        raise RuntimeError("Source database is missing its Alembic migration marker.")
                    cursor.execute(
                        """
                        INSERT INTO users (id, username, email, password_hash, created_at)
                        VALUES (%s, %s, %s, %s, now())
                        """,
                        (user_id, username, email, "NON_LOGIN_BACKUP_RESTORE_FIXTURE"),
                    )
                    cursor.execute(
                        """
                        INSERT INTO state_snapshots (user_id, revision, state_json, updated_at)
                        VALUES (%s, %s, %s, now())
                        """,
                        (user_id, 42, Json(payload)),
                    )

            run_checked(
                "pg_dump",
                ["pg_dump", "--format=custom", "--no-owner", "--no-acl",
                 "--file", str(archive), *options, "--dbname", source_db],
                env,
            )
            if not archive.exists() or archive.stat().st_size < 1024:
                raise RuntimeError("pg_dump did not produce a plausible backup archive.")

            # Create a new empty restore target using the local disposable Postgres server.
            run_checked(
                "create restore database",
                ["createdb", *options, "--maintenance-db", "postgres", target_db],
                env,
            )
            target_created = True
            run_checked(
                "pg_restore",
                ["pg_restore", "--exit-on-error", "--no-owner", "--no-acl",
                 *options, "--dbname", target_db, str(archive)],
                env,
            )

            restored_dsn = make_conninfo(dsn, dbname=target_db)
            with psycopg.connect(restored_dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT version_num FROM alembic_version")
                    restored_migration = cursor.fetchone()
                    if not restored_migration or restored_migration[0] != source_migration[0]:
                        raise AssertionError("Restored Alembic migration marker did not match the source.")
                    cursor.execute(
                        """
                        SELECT u.username, u.email, s.revision,
                               s.state_json->'works'->0->>'title'
                        FROM users AS u
                        JOIN state_snapshots AS s ON s.user_id = u.id
                        WHERE u.id = %s
                        """,
                        (user_id,),
                    )
                    recovered = cursor.fetchone()
                    assert recovered == (username, email, 42, canary_title), (
                        "Restored account/library fixture did not match the source backup."
                    )
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_name IN ('users', 'sessions', 'state_snapshots', 'alembic_version')
                        """
                    )
                    table_count = cursor.fetchone()[0]
                    assert table_count == 4, f"Expected four application/migration tables, got {table_count}"
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM information_schema.table_constraints
                        WHERE table_schema = 'public'
                          AND table_name = 'state_snapshots'
                          AND constraint_type = 'FOREIGN KEY'
                        """
                    )
                    fk_count = cursor.fetchone()[0]
                    assert fk_count >= 1, "The restored user-to-snapshot foreign key is missing."

            print(json.dumps({
                "result": "passed",
                "backup_format": "PostgreSQL custom archive (pg_dump -Fc)",
                "archive_bytes": archive.stat().st_size,
                "restore_target": "fresh disposable database",
                "migration_version": source_migration[0],
                "restored_account": username,
                "restored_snapshot_revision": 42,
                "restored_library_canary": canary_title,
                "restored_schema_tables": table_count,
                "restored_foreign_key_constraints": fk_count,
                "credentials_logged": False,
            }, indent=2))
        finally:
            if target_created:
                # This database was uniquely named and created by this script alone.
                maintenance_dsn = make_conninfo(dsn, dbname="postgres")
                with psycopg.connect(maintenance_dsn, autocommit=True) as connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s",
                            (target_db,),
                        )
                        cursor.execute("DROP DATABASE IF EXISTS " + '"' + target_db + '"')


if __name__ == "__main__":
    main()
