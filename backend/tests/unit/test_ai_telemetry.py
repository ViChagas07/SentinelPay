import os

import pytest

from paysentineliq.infrastructure.ai.telemetry import configure_ai_telemetry

pytestmark = pytest.mark.unit


def test_configure_ai_telemetry_disables_known_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    configure_ai_telemetry()

    assert "OTEL_SDK_DISABLED" not in os.environ
    assert os.environ["CREWAI_DISABLE_TELEMETRY"] == "true"
    assert os.environ["CREWAI_DISABLE_TRACKING"] == "true"
    assert os.environ["CREWAI_TRACING_ENABLED"] == "false"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "false"
    assert os.environ["LANGCHAIN_TRACING"] == "false"
    assert os.environ["LANGSMITH_TRACING"] == "false"
    assert os.environ["ANONYMIZED_TELEMETRY"] == "false"
