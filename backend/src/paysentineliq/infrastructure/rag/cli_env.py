import os
from pathlib import Path
from urllib.parse import quote


def load_env_file(path: Path) -> None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def local_database_url() -> str:
    user = quote(os.environ.get("POSTGRES_USER", "sentinel"), safe="")
    password = quote(os.environ.get("POSTGRES_PASSWORD", "CHANGE_ME"), safe="")
    database = quote(os.environ.get("POSTGRES_DB", "paysentineliq"), safe="")
    port = os.environ.get("POSTGRES_PORT", "55432")
    return f"postgresql+asyncpg://{user}:{password}@localhost:{port}/{database}"
