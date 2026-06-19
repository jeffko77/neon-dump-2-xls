from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, urlunparse

from dotenv import load_dotenv

DEFAULT_ROLE_NAME = "neon_export_reader"


class ConfigError(Exception):
    pass


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def app_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def project_root() -> Path:
    return app_dir()


def config_path() -> Path:
    return app_dir() / "config.json"


def load_database_url() -> str:
    load_dotenv(app_dir() / ".env", override=False)

    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url.strip()

    path = config_path()
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        url = data.get("database_url")
        if not url:
            raise ConfigError("config.json exists but database_url is missing")
        return str(url).strip()

    if is_frozen():
        raise ConfigError(
            "No database configuration found. Re-run the installer and paste your "
            f"readonly connection string, or place config.json in: {app_dir()}"
        )

    raise ConfigError(
        "No database configuration found. Set DATABASE_URL, create config.json "
        "(see config.example.json), or add a .env file."
    )


def redact_database_url(database_url: str) -> str:
    parsed = urlparse(database_url)
    host = parsed.hostname or "unknown-host"
    database = parsed.path.lstrip("/") or "unknown-db"
    return f"{parsed.scheme}://{parsed.username or 'user'}:****@{host}/{database}"


def connection_host(database_url: str) -> str:
    return urlparse(database_url).hostname or "unknown-host"


def build_readonly_url(
    admin_url: str,
    *,
    role_name: str,
    password: str,
) -> str:
    parsed = urlparse(admin_url)
    if not parsed.scheme or not parsed.hostname:
        raise ValueError("Invalid database URL")

    username = quote(role_name, safe="")
    encoded_password = quote(password, safe="")
    netloc = f"{username}:{encoded_password}@{parsed.hostname}"
    if parsed.port:
        netloc += f":{parsed.port}"

    return urlunparse(
        (
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def parse_database_url(database_url: str) -> dict[str, str | int | None]:
    parsed = urlparse(database_url)
    return {
        "scheme": parsed.scheme,
        "user": unquote(parsed.username) if parsed.username else None,
        "password": unquote(parsed.password) if parsed.password else None,
        "host": parsed.hostname,
        "port": parsed.port,
        "database": parsed.path.lstrip("/") if parsed.path else None,
    }
