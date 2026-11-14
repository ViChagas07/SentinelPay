import asyncio
import subprocess
from pathlib import Path
from urllib.parse import quote

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.docker]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PAYLOADS = [
    "1' OR '1'='1",
    "1; DROP TABLE alembic_version; --",
    "' UNION SELECT NULL --",
    "<script>alert(1)<script>",
]


async def test_sqli_and_xss_payloads_are_rejected_without_schema_change() -> None:
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=5.0) as client:
        for payload in _PAYLOADS:
            response = await client.get(f"/api/v1/example/{quote(payload, safe='')}")

            assert response.status_code == 422
            assert response.headers["content-type"].startswith("application/problem+json")
            body = response.json()
            assert body["code"] == "validation_error"
            assert payload not in response.text

    result = await asyncio.to_thread(
        subprocess.run,
        [
            "docker",
            "compose",
            "--env-file",
            ".env.example",
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "sentinel",
            "-d",
            "paysentineliq",
            "-tAc",
            "SELECT COUNT(*) FROM alembic_version",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "1"
