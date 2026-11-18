import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pymupdf
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

_spec = importlib.util.spec_from_file_location(
    "seed_demo",
    ROOT / "scripts" / "seed_demo.py",
)
assert _spec is not None and _spec.loader is not None
seed_demo: Any = importlib.util.module_from_spec(_spec)
sys.modules["seed_demo"] = seed_demo
_spec.loader.exec_module(seed_demo)

pytestmark = pytest.mark.unit


def test_generate_documents_covers_low_attention_and_high(tmp_path: Path) -> None:
    manifest = seed_demo.generate_documents(tmp_path)

    assert manifest["synthetic"] is True
    documents = manifest["documents"]
    assert len(documents) == 5
    assert {document["expected_band"] for document in documents} == {
        "low",
        "attention",
        "high",
    }
    for document in documents:
        path = tmp_path / document["file"]
        assert path.exists()
        assert len(document["sha256"]) == 64
        with pymupdf.open(path) as pdf:
            text = "\n".join(page.get_text() for page in pdf)
        assert "SYNTHETIC DEMO DOCUMENT" in text
        assert document["deterministic_subscore"] >= 0


def test_demo_band_thresholds() -> None:
    assert seed_demo._band(0) == "low"
    assert seed_demo._band(39) == "low"
    assert seed_demo._band(40) == "attention"
    assert seed_demo._band(69) == "attention"
    assert seed_demo._band(70) == "high"


def test_manifest_is_json_serializable(tmp_path: Path) -> None:
    manifest = seed_demo.generate_documents(tmp_path)

    payload = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))

    assert payload == manifest
    assert payload["documents"][0]["file"].endswith(".pdf")
