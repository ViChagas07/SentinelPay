from datetime import date

import pytest

from paysentineliq.domain.analysis import AnalysisDocumentType
from paysentineliq.domain.document import DocumentKind
from paysentineliq.domain.payables import PayableStatus
from paysentineliq.domain.scoring import RiskBand
from tests.support.receipt_factory import build_receipt
from tests.unit.test_guardrail_graph import (
    FakeGuardedInterpreter,
    build_orchestrator,
    run_analysis,
)
from tests.unit.test_langgraph_orchestrator import FakeModel

pytestmark = pytest.mark.unit


async def test_legitimate_receipt_creates_pending_payable() -> None:
    receipt = build_receipt()
    orchestrator, analyses, _, _, _, _ = build_orchestrator(
        receipt.ocr_text(),
        kind=DocumentKind.RECEIPT,
        interpreter=FakeGuardedInterpreter(inconsistencies=()),
    )

    report = await run_analysis(orchestrator, kind=DocumentKind.RECEIPT)

    assert report.document_type is AnalysisDocumentType.RECEIPT
    assert report.band is RiskBand.LOW
    assert report.fields["issuer"]["value"] == "Energia Sul Distribuidora"
    assert report.fields["reference"]["value"] == "01/2026"
    assert analyses.completed is not None
    payables = analyses.completed["payables"]
    assert len(payables) == 1
    payable = payables[0]
    assert payable.status is PayableStatus.PENDING
    assert payable.amount_cents == 18475
    assert payable.due_date == date(2026, 1, 15)
    assert "Energia Sul" in payable.description


async def test_attention_receipt_creates_pending_confirmation() -> None:
    receipt = build_receipt().with_extra("PAGUE ATE: 20/01/2026")
    orchestrator, analyses, _, _, _, _ = build_orchestrator(
        receipt.ocr_text(),
        kind=DocumentKind.RECEIPT,
        interpreter=FakeGuardedInterpreter(inconsistencies=()),
        model=FakeModel(probability=0.9),
    )

    report = await run_analysis(orchestrator, kind=DocumentKind.RECEIPT)

    assert report.band is RiskBand.ATTENTION
    assert analyses.completed is not None
    payables = analyses.completed["payables"]
    assert len(payables) == 1
    assert payables[0].status is PayableStatus.PENDING_CONFIRMATION


async def test_high_risk_receipt_does_not_create_payable() -> None:
    receipt = build_receipt().with_tampered_dv()
    orchestrator, analyses, events, _, _, _ = build_orchestrator(
        receipt.ocr_text(),
        kind=DocumentKind.RECEIPT,
        interpreter=FakeGuardedInterpreter(inconsistencies=()),
    )

    report = await run_analysis(orchestrator, kind=DocumentKind.RECEIPT)

    assert report.band is RiskBand.HIGH
    assert "receipt_dv_invalid" in {item.rule_id for item in report.evidence}
    assert analyses.completed is not None
    assert analyses.completed["payables"] == ()
    assert any(event.rule_code == "receipt_dv_invalid" for event in events.events)
