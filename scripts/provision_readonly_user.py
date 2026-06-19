from __future__ import annotations

import argparse
import json
import secrets
import string
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.connection import (  # noqa: E402
    DEFAULT_ROLE_NAME,
    build_readonly_url,
    redact_database_url,
)

SYSTEM_SCHEMAS = frozenset(
    {"pg_catalog", "information_schema", "pg_toast", "pg_temp_1"}
)
PASSWORD_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*-_"


def generate_password(length: int = 24) -> str:
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(length))


def discover_user_schemas(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT LIKE 'pg_%'
              AND schema_name <> 'information_schema'
            ORDER BY schema_name
            """
        )
        return [row[0] for row in cur.fetchall()]


def discover_owner_role(conn) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT current_user")
        row = cur.fetchone()
        if not row:
            raise RuntimeError("Could not determine current database role")
        return row[0]


def role_exists(conn, role_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role_name,))
        return cur.fetchone() is not None


def grant_schema_readonly(
    conn,
    *,
    schema_name: str,
    role_name: str,
    owner_role: str,
) -> None:
    statements = [
        sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
            sql.Identifier(schema_name),
            sql.Identifier(role_name),
        ),
        sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {}").format(
            sql.Identifier(schema_name),
            sql.Identifier(role_name),
        ),
        sql.SQL("GRANT SELECT ON ALL SEQUENCES IN SCHEMA {} TO {}").format(
            sql.Identifier(schema_name),
            sql.Identifier(role_name),
        ),
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} "
            "GRANT SELECT ON TABLES TO {}"
        ).format(
            sql.Identifier(owner_role),
            sql.Identifier(schema_name),
            sql.Identifier(role_name),
        ),
    ]
    with conn.cursor() as cur:
        for statement in statements:
            cur.execute(statement)


def provision_readonly_user(
    admin_url: str,
    *,
    role_name: str,
    password: str | None,
    schemas: list[str] | None,
    rotate: bool,
) -> tuple[str, bool, list[str]]:
    generated_password = password or generate_password()
    created = False

    with psycopg2.connect(admin_url) as conn:
        conn.autocommit = True
        owner_role = discover_owner_role(conn)
        target_schemas = schemas or discover_user_schemas(conn)
        target_schemas = [s for s in target_schemas if s not in SYSTEM_SCHEMAS]
        granted_schemas = list(target_schemas)

        if not target_schemas:
            raise RuntimeError("No user schemas found to grant access")

        exists = role_exists(conn, role_name)
        if exists and not rotate:
            raise RuntimeError(
                f"Role {role_name!r} already exists. "
                "Use --rotate-password to update its password and refresh grants."
            )

        with conn.cursor() as cur:
            if exists:
                cur.execute(
                    sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD %s").format(
                        sql.Identifier(role_name)
                    ),
                    (generated_password,),
                )
            else:
                cur.execute(
                    sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD %s").format(
                        sql.Identifier(role_name)
                    ),
                    (generated_password,),
                )
                created = True

            cur.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(conn.info.dbname),
                    sql.Identifier(role_name),
                )
            )
            cur.execute(
                sql.SQL("GRANT pg_read_all_data TO {}").format(
                    sql.Identifier(role_name)
                )
            )

        for schema_name in target_schemas:
            grant_schema_readonly(
                conn,
                schema_name=schema_name,
                role_name=role_name,
                owner_role=owner_role,
            )

    readonly_url = build_readonly_url(
        admin_url,
        role_name=role_name,
        password=generated_password,
    )
    return readonly_url, created, granted_schemas


def validate_readonly(readonly_url: str) -> None:
    with psycopg2.connect(readonly_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.execute(
                """
                SELECT has_table_privilege(current_user, 'pg_catalog.pg_class', 'INSERT')
                """
            )
            can_insert_catalog = cur.fetchone()[0]
            if can_insert_catalog:
                raise RuntimeError(
                    "Readonly validation failed: role appears to have write access"
                )


def write_config(readonly_url: str, config_path: Path) -> None:
    config_path.write_text(
        json.dumps({"database_url": readonly_url}, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create or rotate a readonly Neon/Postgres export user. "
            "Requires a read-write owner connection string."
        )
    )
    parser.add_argument(
        "--database-url",
        help="Read-write owner connection string (or set DATABASE_URL env var)",
    )
    parser.add_argument(
        "--role-name",
        default=DEFAULT_ROLE_NAME,
        help=f"Readonly role name (default: {DEFAULT_ROLE_NAME})",
    )
    parser.add_argument(
        "--password",
        help="Explicit password for the readonly role (default: generate securely)",
    )
    parser.add_argument(
        "--schemas",
        help="Comma-separated schema list (default: auto-discover user schemas)",
    )
    parser.add_argument(
        "--rotate-password",
        action="store_true",
        help="Rotate password and refresh grants for an existing readonly role",
    )
    parser.add_argument(
        "--write-config",
        type=Path,
        metavar="PATH",
        help="Write readonly connection string to config.json at PATH",
    )
    parser.add_argument(
        "--print-connection-string",
        action="store_true",
        help="Print the readonly connection string to stdout",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    admin_url = args.database_url
    if not admin_url:
        import os

        admin_url = os.environ.get("DATABASE_URL")
    if not admin_url:
        print(
            "Error: provide --database-url or set DATABASE_URL to an owner connection string.",
            file=sys.stderr,
        )
        sys.exit(1)

    schemas = None
    if args.schemas:
        schemas = [s.strip() for s in args.schemas.split(",") if s.strip()]

    try:
        readonly_url, created, granted_schemas = provision_readonly_user(
            admin_url,
            role_name=args.role_name,
            password=args.password,
            schemas=schemas,
            rotate=args.rotate_password,
        )
        validate_readonly(readonly_url)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    action = "Created" if created else "Updated"
    print(f"{action} readonly role {args.role_name!r}.")
    print(f"Granted schemas: {', '.join(granted_schemas)}")
    print(f"Readonly host: {redact_database_url(readonly_url)}")

    if args.write_config:
        write_config(readonly_url, args.write_config)
        print(f"Wrote {args.write_config}")

    if args.print_connection_string:
        print(readonly_url)
    else:
        print(
            "Connection string not printed. Use --print-connection-string to output it, "
            "or --write-config to save config.json for the export app."
        )


if __name__ == "__main__":
    main()
