import argparse
import asyncio
import hashlib
import json
import os
import sys
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
sys.path.insert(0, str(ROOT / "backend"))

from tests.support.boleto_factory import build_boleto  # noqa: E402
from tests.support.payslip_factory import SyntheticPayslip  # noqa: E402
from tests.support.receipt_factory import build_receipt  # noqa: E402
from tests.support.regulatory_factory import synthetic_regulatory_tables  # noqa: E402

from paysentineliq.domain.boleto.analysis import analyze_boleto  # noqa: E402
from paysentineliq.domain.boleto.bank_directory import load_bank_directory  # noqa: E402
from paysentineliq.domain.boleto.extraction import extract_boleto_fields  # noqa: E402
from paysentineliq.domain.payslip.analysis import analyze_payslip  # noqa: E402
from paysentineliq.domain.payslip.extraction import extract_payslip_fields  # noqa: E402
from paysentineliq.domain.receipt.analysis import analyze_receipt  # noqa: E402
from paysentineliq.domain.receipt.extraction import extract_receipt_fields  # noqa: E402
from paysentineliq.infrastructure.config import Settings  # noqa: E402
from paysentineliq.infrastructure.db.engine import (  # noqa: E402
    build_engine,
    build_session_factory,
)
from paysentineliq.infrastructure.db.uow import SqlAlchemyUnitOfWork  # noqa: E402
from paysentineliq.infrastructure.rag.cli_env import (  # noqa: E402
    load_env_file,
    local_database_url,
)
from paysentineliq.infrastructure.security.jwt import JwtAccessTokenService  # noqa: E402

DEMO_GOOGLE_SUB = "sentinelpay-demo-local"
DEMO_EMAIL = "demo@sentinelpay.local"
DEMO_NAME = "SentinelPay Demo"
_DEMO_REFERENCE_DATE = date(2024, 6, 1)
_DEMO_TOKEN_TTL_MINUTES = 60


@dataclass(frozen=True, slots=True)
class DemoDocument:
    slug: str
    filename: str
    analysis_kind: str
    scenario: str
    expected_band: str
    deterministic_subscore: int
    text: str


def _band(subscore: int) -> str:
    if subscore <= 39:
        return "low"
    if subscore <= 69:
        return "attention"
    return "high"


def _deterministic_subscore(kind: str, text: str) -> int:
    if kind == "boleto":
        directory = load_bank_directory()
        fields = extract_boleto_fields(text, bank_directory=directory)
        return analyze_boleto(fields, bank_directory=directory).subscore
    if kind == "payslip":
        return analyze_payslip(
            extract_payslip_fields(text),
            regulatory=synthetic_regulatory_tables(),
            reference_date=_DEMO_REFERENCE_DATE,
        ).subscore
    if kind == "receipt":
        return analyze_receipt(extract_receipt_fields(text)).subscore
    raise ValueError(f"unsupported demo kind: {kind}")


def _demo_documents() -> list[DemoDocument]:
    valid_boleto = build_boleto(factor=9999, amount_cents=18475)
    tampered_line = (
        valid_boleto.line[:9] + str((int(valid_boleto.line[9]) + 1) % 10) + valid_boleto.line[10:]
    )
    tampered_boleto = replace(valid_boleto, line=tampered_line)
    valid_payslip = SyntheticPayslip()
    tampered_payslip = SyntheticPayslip(net="2.200,00")
    attention_receipt = build_receipt(amount=None, due_date=None)

    specs = (
        DemoDocument(
            slug="boleto-valid",
            filename="boleto_valid.pdf",
            analysis_kind="boleto",
            scenario="Valid synthetic boleto. The line, barcode and amount are coherent.",
            expected_band="low",
            deterministic_subscore=-1,
            text=valid_boleto.ocr_text(),
        ),
        DemoDocument(
            slug="boleto-tampered",
            filename="boleto_tampered.pdf",
            analysis_kind="boleto",
            scenario="Synthetic boleto with a changed check digit in the digitable line.",
            expected_band="high",
            deterministic_subscore=-1,
            text=tampered_boleto.ocr_text(),
        ),
        DemoDocument(
            slug="payslip-valid",
            filename="payslip_valid.pdf",
            analysis_kind="payslip",
            scenario="Valid synthetic payslip. Totals, deductions and net pay are coherent.",
            expected_band="low",
            deterministic_subscore=-1,
            text=valid_payslip.ocr_text(),
        ),
        DemoDocument(
            slug="payslip-tampered",
            filename="payslip_tampered.pdf",
            analysis_kind="payslip",
            scenario="Synthetic payslip whose net pay is higher than total earnings.",
            expected_band="high",
            deterministic_subscore=-1,
            text=tampered_payslip.ocr_text(),
        ),
        DemoDocument(
            slug="utility-attention",
            filename="utility_attention.pdf",
            analysis_kind="receipt",
            scenario=(
                "Synthetic utility bill with missing amount and due date. "
                "The issuer, reference, line and barcode are present, but the missing "
                "financial fields are medium signals, so the expected band is attention."
            ),
            expected_band="attention",
            deterministic_subscore=-1,
            text=attention_receipt.ocr_text(),
        ),
    )
    documents: list[DemoDocument] = []
    for spec in specs:
        subscore = _deterministic_subscore(spec.analysis_kind, spec.text)
        band = _band(subscore)
        if band != spec.expected_band:
            raise RuntimeError(
                f"demo {spec.slug} produced band {band} ({subscore}); "
                f"expected {spec.expected_band}",
            )
        documents.append(replace(spec, deterministic_subscore=subscore))
    return documents


def _write_pdf(path: Path, document: DemoDocument) -> None:
    pdf = pymupdf.open()
    page = pdf.new_page(width=595, height=842)
    y = 56.0
    lines = [
        *document.text.splitlines(),
        "",
        "SYNTHETIC DEMO DOCUMENT - NOT A REAL BILL, PAYSLIP OR RECEIPT",
    ]
    for line in lines:
        if y > 810:
            page = pdf.new_page(width=595, height=842)
            y = 56.0
        page.insert_text((48, y), line, fontsize=9, fontname="helv")
        y += 13
    pdf.set_metadata(
        {
            "title": f"SentinelPay synthetic demo: {document.slug}",
            "author": "SentinelPay",
            "subject": "100% synthetic demo document",
            "keywords": "synthetic,demo,no real data",
        },
    )
    pdf.save(path)
    pdf.close()


def generate_documents(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    documents = _demo_documents()
    files: list[dict[str, Any]] = []
    for document in documents:
        path = output_dir / document.filename
        _write_pdf(path, document)
        files.append(
            {
                "file": document.filename,
                "analysis_kind": document.analysis_kind,
                "scenario": document.scenario,
                "expected_band": document.expected_band,
                "deterministic_subscore": document.deterministic_subscore,
                "sha256": _sha256(path),
            },
        )
    manifest = {
        "synthetic": True,
        "warning": "All documents are synthetic and contain no real personal data.",
        "generated_at": datetime.now(UTC).isoformat(),
        "documents": files,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


async def seed_demo_user(settings: Settings, output_dir: Path) -> dict[str, Any]:
    engine = build_engine(settings)
    try:
        factory = build_session_factory(engine)
        async with factory() as session:
            uow = SqlAlchemyUnitOfWork(session)
            async with uow:
                user = await uow.users.get_by_google_sub(DEMO_GOOGLE_SUB)
                if user is None:
                    user = await uow.users.create(
                        google_sub=DEMO_GOOGLE_SUB,
                        email=DEMO_EMAIL,
                        name=DEMO_NAME,
                    )
                await uow.commit()
    finally:
        await engine.dispose()
    token = JwtAccessTokenService(
        secret=settings.jwt_secret,
        ttl_minutes=_DEMO_TOKEN_TTL_MINUTES,
    ).issue(user)
    token_path = output_dir / ".demo_token"
    token_path.write_text(token.token, encoding="utf-8")
    return {
        "user_id": str(user.id),
        "email": user.email,
        "token_file": token_path.name,
        "expires_in_minutes": _DEMO_TOKEN_TTL_MINUTES,
    }


def _write_manifest(output_dir: Path, manifest: dict[str, Any]) -> None:
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_env_value(path: Path, key: str) -> str | None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate synthetic demo documents and a local demo API token.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "demo",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=ROOT / ".env.example",
    )
    parser.add_argument(
        "--no-token",
        action="store_true",
        help="generate only the PDFs, without connecting to the local database",
    )
    args = parser.parse_args()
    if not args.env_file.is_file():
        raise SystemExit(f"env file not found: {args.env_file}")
    load_env_file(args.env_file)
    os.environ["DATABASE_URL"] = local_database_url()
    os.environ.setdefault("APP_ENV", "local")
    jwt_secret = _read_env_value(args.env_file, "JWT_SECRET")
    if jwt_secret:
        os.environ["JWT_SECRET"] = jwt_secret
    settings = Settings()
    if settings.app_env != "local":
        raise SystemExit("seed_demo only runs with APP_ENV=local")
    output_dir = args.output_dir.resolve()
    manifest = generate_documents(output_dir)
    print(f"generated {len(manifest['documents'])} synthetic documents in {output_dir}")
    if args.no_token:
        print("demo token skipped; run again without --no-token to create it")
        return 0
    try:
        demo_user = asyncio.run(seed_demo_user(settings, output_dir))
    except Exception as exc:
        print(
            "could not create the local demo user. Start the stack and run "
            f"`make migrate` first. Cause: {type(exc).__name__}",
        )
        return 1
    manifest["demo_user"] = demo_user
    _write_manifest(output_dir, manifest)
    print(f"demo user ready: {demo_user['email']}")
    print(f"token file: {output_dir / demo_user['token_file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
