import difflib
import json
from pathlib import Path
from typing import Any

import pytest

from paysentineliq.infrastructure.config import Settings
from paysentineliq.interface.api.main import create_app

pytestmark = pytest.mark.unit

_SNAPSHOT_PATH = Path(__file__).resolve().parents[1] / "contracts" / "openapi.json"


def _load_snapshot() -> dict[str, Any]:
    assert _SNAPSHOT_PATH.exists(), "snapshot OpenAPI ausente; rode `make openapi` e revise o diff"
    payload: object = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_openapi_matches_snapshot() -> None:
    snapshot = _load_snapshot()
    current = create_app(Settings(app_env="local")).openapi()

    if current != snapshot:
        expected = json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
        actual = json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
        diff = list(
            difflib.unified_diff(
                expected,
                actual,
                fromfile="tests/contracts/openapi.json",
                tofile="openapi atual",
                lineterm="",
                n=2,
            ),
        )
        pytest.fail(
            "Contrato OpenAPI mudou. Revise a mudanca e rode `make openapi` no mesmo commit.\n"
            + "\n".join(diff[:80]),
        )


def test_docs_openapi_matches_contract_snapshot() -> None:
    docs_path = Path(__file__).resolve().parents[3] / "docs" / "api" / "openapi.json"
    assert docs_path.exists(), "docs/api/openapi.json ausente; rode `make openapi`"
    docs_schema = json.loads(docs_path.read_text(encoding="utf-8"))
    assert docs_schema == _load_snapshot()
