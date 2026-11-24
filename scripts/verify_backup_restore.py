"""Verify downloaded OmniShelf Neon backups against live sources.

The source Neon connections are read-only. Restores run only into disposable
local PostgreSQL databases on the isolated GitHub Actions runner.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

import psycopg
from psycopg import sql


def inspect_database(dsn: str) -> dict[str, Any]:
    """Return a structural and row-count signature for a PostgreSQL database."""
    with psycopg.connect(dsn, connect_timeout=30) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")

            cursor.execute(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type = 'BASE TABLE'
                  AND table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_schema, table_name
                """
            )
            tables = cursor.fetchall()
            if not tables:
                raise RuntimeError("Database contains no application tables.")

            row_counts: dict[str, int] = {}
            for schema_name, table_name in tables:
                cursor.execute(
                    sql.SQL("SELECT count(*) FROM {}.{}").format(
                        sql.Identifier(schema_name),
                        sql.Identifier(table_name),
                    )
                )
                row_counts[f"{schema_name}.{table_name}"] = int(cursor.fetchone()[0])

            cursor.execute(
                """
                SELECT table_schema, table_name, column_name, ordinal_position,
                       data_type, udt_schema, udt_name, is_nullable
                FROM information_schema.columns
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_schema, table_name, ordinal_position
                """
            )
            columns = cursor.fetchall()

            cursor.execute(
                """
                SELECT constraint_schema, table_name, constraint_name,
                       constraint_type, is_deferrable, initially_deferred
                FROM information_schema.table_constraints
                WHERE constraint_schema NOT IN ('pg_catalog', 'information_schema')
                  -- PostgreSQL-generated NOT NULL labels are OID-derived, so
                  -- they legitimately differ after restoring into a new database.
                  -- Column nullability is compared separately above.
                  AND NOT (
                      constraint_type = 'CHECK'
                      AND right(constraint_name, 9) = '_not_null'
                      AND split_part(constraint_name, '_', 1) ~ '^[0-9]+'
                  )
                ORDER BY constraint_schema, table_name, constraint_name
                """
            )
            constraints = cursor.fetchall()

            if ("public", "alembic_version") not in tables:
                raise RuntimeError("Database is missing public.alembic_version.")
            cursor.execute(
                "SELECT version_num FROM public.alembic_version ORDER BY version_num"
            )
            migrations = [row[0] for row in cursor.fetchall()]
            if not migrations:
                raise RuntimeError("Alembic migration version table is empty.")

    return {
        "tables": [f"{schema}.{table}" for schema, table in tables],
        "row_counts": row_counts,
        "columns": [list(row) for row in columns],
        "constraints": [list(row) for row in constraints],
        "migrations": migrations,
    }


def verify(target: str, source_dsn: str, restored_dsn: str) -> None:
    source = inspect_database(source_dsn)
    restored = inspect_database(restored_dsn)

    checks = (
        ("table names", source["tables"], restored["tables"]),
        ("column definitions and nullability", source["columns"], restored["columns"]),
        ("primary, foreign, unique and explicit check constraints",
         source["constraints"], restored["constraints"]),
        ("Alembic migration versions", source["migrations"], restored["migrations"]),
        ("exact table row counts", source["row_counts"], restored["row_counts"]),
    )
    failures = [
        label for label, expected, actual in checks if expected != actual
    ]
    if failures:
        details: dict[str, Any] = {
            "target": target,
            "failed_checks": failures,
            "source_table_count": len(source["tables"]),
            "restored_table_count": len(restored["tables"]),
        }
        if source["row_counts"] != restored["row_counts"]:
            details["row_count_differences"] = {
                table: {
                    "source": source["row_counts"].get(table),
                    "restored": restored["row_counts"].get(table),
                }
                for table in sorted(
                    set(source["row_counts"]) | set(restored["row_counts"])
                )
                if source["row_counts"].get(table) != restored["row_counts"].get(table)
            }
        if source["constraints"] != restored["constraints"]:
            source_constraints = {tuple(row) for row in source["constraints"]}
            restored_constraints = {tuple(row) for row in restored["constraints"]}
            details["missing_restored_constraints"] = [
                list(row) for row in sorted(source_constraints - restored_constraints)
            ][:30]
            details["unexpected_restored_constraints"] = [
                list(row) for row in sorted(restored_constraints - source_constraints)
            ][:30]
        raise RuntimeError(json.dumps(details, indent=2))

    print(
        json.dumps(
            {
                "target": target,
                "result": "passed",
                "application_tables": len(source["tables"]),
                "columns_and_nullability": len(source["columns"]),
                "constraints": len(source["constraints"]),
                "alembic_versions": source["migrations"],
                "table_row_counts_match": True,
                "live_source_access": "read-only",
                "restore_destination": "temporary local PostgreSQL database",
            },
            indent=2,
        )
    )


def main() -> None:
    required = (
        "RESTORE_TARGET",
        "NEON_SOURCE_DATABASE_URL",
        "RESTORED_DATABASE_URL",
    )
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")

    verify(
        os.environ["RESTORE_TARGET"],
        os.environ["NEON_SOURCE_DATABASE_URL"],
        os.environ["RESTORED_DATABASE_URL"],
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Restore verification failed: {exc}", file=sys.stderr)
        raise
