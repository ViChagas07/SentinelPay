import hashlib
import json
import random
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Literal

from paysentineliq.application.queries.fraud_features import (
    FEATURE_NAMES,
    build_feature_vector,
)
from paysentineliq.domain.ingestion import VisualSignal
from paysentineliq.domain.scoring import (
    DeterministicSummary,
    EvidenceSummary,
    SeverityLevel,
)

FRAUD_MUTATIONS = frozenset(
    {
        "value_changed",
        "dv_invalid",
        "bank_unknown",
        "invalid_beneficiary_tax_id",
        "sum_mismatch",
        "net_mismatch",
        "duplicated_item",
        "invalid_employer_cnpj",
        "invalid_employee_cpf",
        "pasted_region",
    },
)

_MUTATIONS: dict[str, tuple[str, ...]] = {
    "boleto": (
        "value_changed",
        "dv_invalid",
        "bank_unknown",
        "invalid_beneficiary_tax_id",
        "pasted_region",
        "missing_table",
        "unknown_layout",
        "low_confidence",
    ),
    "payslip": (
        "sum_mismatch",
        "net_mismatch",
        "duplicated_item",
        "invalid_employer_cnpj",
        "invalid_employee_cpf",
        "pasted_region",
        "missing_table",
        "unknown_layout",
        "low_confidence",
    ),
}

_RULES: dict[str, tuple[str, SeverityLevel, int]] = {
    "value_changed": ("amount_mismatch", SeverityLevel.CRITICAL, 70),
    "dv_invalid": ("dv_invalid", SeverityLevel.CRITICAL, 70),
    "bank_unknown": ("bank_code_unknown", SeverityLevel.HIGH, 20),
    "invalid_beneficiary_tax_id": ("tax_id_invalid", SeverityLevel.HIGH, 25),
    "sum_mismatch": ("earnings_total_mismatch", SeverityLevel.HIGH, 25),
    "net_mismatch": ("net_mismatch", SeverityLevel.HIGH, 30),
    "duplicated_item": ("duplicate_item", SeverityLevel.HIGH, 25),
    "invalid_employer_cnpj": ("employer_cnpj_invalid", SeverityLevel.HIGH, 25),
    "invalid_employee_cpf": ("employee_cpf_invalid", SeverityLevel.HIGH, 25),
}

_VISUAL_NAMES = (
    "image_resolution",
    "image_blur",
    "image_noise",
    "ela_recompression",
    "noise_variance_blocks",
    "copy_move_orb",
    "pdf_producer",
    "pdf_dates",
    "pdf_incremental_updates",
    "pdf_overlaid_layers",
)


@dataclass(frozen=True, slots=True)
class SyntheticDatasetConfig:
    seed: int = 42
    base_documents: int = 60
    variants_per_base: int = 3

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError("seed must be non-negative")
        if self.base_documents <= 0:
            raise ValueError("base_documents must be positive")
        if not 1 <= self.variants_per_base <= 9:
            raise ValueError("variants_per_base must be between 1 and 9")


@dataclass(frozen=True, slots=True)
class DatasetRow:
    base_id: str
    document_type: Literal["boleto", "payslip"]
    mutation: str
    label: int
    features: tuple[float, ...]
    synthetic: bool = True

    def __post_init__(self) -> None:
        if not self.base_id.strip():
            raise ValueError("base_id is required")
        if self.document_type not in ("boleto", "payslip"):
            raise ValueError("document_type must be boleto or payslip")
        if self.label not in (0, 1):
            raise ValueError("label must be 0 or 1")
        if len(self.features) != len(FEATURE_NAMES):
            raise ValueError("features must match FEATURE_NAMES")


@dataclass(frozen=True, slots=True)
class SyntheticDataset:
    rows: tuple[DatasetRow, ...]
    hash: str
    description: str
    seed: int
    config: SyntheticDatasetConfig
    synthetic: bool = True


@dataclass(frozen=True, slots=True)
class DatasetSplit:
    train: tuple[DatasetRow, ...]
    validation: tuple[DatasetRow, ...]
    test: tuple[DatasetRow, ...]
    train_base_ids: tuple[str, ...]
    validation_base_ids: tuple[str, ...]
    test_base_ids: tuple[str, ...]


def _visual(rng: random.Random, value: float) -> VisualSignal:
    name = rng.choice(_VISUAL_NAMES)
    return VisualSignal(name=name, value=value, explanation="synthetic signal")


def _valid_signals(rng: random.Random) -> tuple[VisualSignal, ...]:
    return tuple(
        VisualSignal(
            name=name,
            value=rng.uniform(0.0, 0.25),
            explanation="synthetic signal",
        )
        for name in _VISUAL_NAMES
    )


def _pasted_signals(rng: random.Random) -> tuple[VisualSignal, ...]:
    return (
        _visual(rng, rng.uniform(0.85, 0.95)),
        _visual(rng, rng.uniform(0.75, 0.95)),
        _visual(rng, rng.uniform(0.6, 0.8)),
        _visual(rng, rng.uniform(0.0, 0.2)),
        _visual(rng, rng.uniform(0.0, 0.2)),
    )


def _degraded_signals(rng: random.Random) -> tuple[VisualSignal, ...]:
    return (
        _visual(rng, rng.uniform(0.6, 0.9)),
        _visual(rng, rng.uniform(0.5, 0.8)),
        _visual(rng, rng.uniform(0.1, 0.3)),
    )


def _base_summary(
    rng: random.Random,
    document_type: Literal["boleto", "payslip"],
) -> DeterministicSummary:
    confidences = tuple(rng.uniform(0.85, 0.99) for _ in range(rng.randint(5, 8)))
    if document_type == "boleto":
        return DeterministicSummary(
            document_type="boleto",
            subscore=0,
            evidence=(),
            field_confidences=confidences,
            not_validated_count=0,
            amount_cents=rng.randint(5000, 500000),
            due_factor=rng.randint(1000, 9000),
            barcode_read=rng.choice([True, False, None]),
        )

    earnings = Decimal(rng.randint(1500, 5000))
    deductions = (earnings * Decimal(str(rng.uniform(0.15, 0.35)))).quantize(
        Decimal("0.01"),
    )
    return DeterministicSummary(
        document_type="payslip",
        subscore=0,
        evidence=(),
        field_confidences=confidences,
        not_validated_count=0,
        item_count=rng.randint(3, 8),
        total_earnings=earnings,
        total_deductions=deductions,
        net=earnings - deductions,
    )


def _mutated_summary(
    base: DeterministicSummary,
    mutation: str,
    rng: random.Random,
) -> DeterministicSummary:
    if mutation in ("valid",):
        return base
    if mutation == "missing_table":
        return replace(base, not_validated_count=4)
    if mutation in ("unknown_layout", "low_confidence"):
        return replace(
            base,
            subscore=10,
            evidence=(
                EvidenceSummary(
                    rule_id="field_illegible",
                    severity=SeverityLevel.MEDIUM,
                    weight=10,
                ),
            ),
            field_confidences=tuple(rng.uniform(0.2, 0.45) for _ in base.field_confidences),
        )
    if mutation == "duplicated_item":
        return replace(
            base,
            subscore=25,
            evidence=(
                EvidenceSummary(
                    rule_id="duplicate_item",
                    severity=SeverityLevel.HIGH,
                    weight=25,
                ),
            ),
            item_count=base.item_count * 2,
        )
    if mutation == "sum_mismatch":
        deductions = base.total_deductions
        return replace(
            base,
            subscore=25,
            evidence=(
                EvidenceSummary(
                    rule_id="earnings_total_mismatch",
                    severity=SeverityLevel.HIGH,
                    weight=25,
                ),
            ),
            total_deductions=(
                deductions + Decimal("50.00") if deductions is not None else deductions
            ),
        )
    if mutation == "net_mismatch":
        return replace(
            base,
            subscore=30,
            evidence=(
                EvidenceSummary(
                    rule_id="net_mismatch",
                    severity=SeverityLevel.HIGH,
                    weight=30,
                ),
            ),
            net=base.net + Decimal("100.00") if base.net is not None else None,
        )
    if mutation == "pasted_region":
        return base
    rule_id, severity, weight = _RULES[mutation]
    subscore = 80 if severity is SeverityLevel.CRITICAL else weight
    return replace(
        base,
        subscore=subscore,
        evidence=(EvidenceSummary(rule_id, severity, weight),),
    )


def _signals_for(
    mutation: str,
    rng: random.Random,
) -> tuple[VisualSignal, ...]:
    if mutation == "pasted_region":
        return _pasted_signals(rng)
    if mutation in ("unknown_layout", "low_confidence"):
        return _degraded_signals(rng)
    return _valid_signals(rng)


def _dataset_hash(
    rows: tuple[DatasetRow, ...],
    config: SyntheticDatasetConfig,
) -> str:
    payload = {
        "seed": config.seed,
        "base_documents": config.base_documents,
        "variants_per_base": config.variants_per_base,
        "rows": [
            {
                "base_id": row.base_id,
                "document_type": row.document_type,
                "mutation": row.mutation,
                "label": row.label,
                "features": [round(value, 12) for value in row.features],
            }
            for row in rows
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def generate_synthetic_dataset(
    config: SyntheticDatasetConfig | None = None,
) -> SyntheticDataset:
    actual = config if config is not None else SyntheticDatasetConfig()
    # Deterministic synthetic dataset; PRNG is not used for security.
    rng = random.Random(actual.seed)  # nosec B311
    rows: list[DatasetRow] = []
    for index in range(actual.base_documents):
        document_type: Literal["boleto", "payslip"] = "boleto" if index % 2 == 0 else "payslip"
        base = _base_summary(rng, document_type)
        base_id = f"base-{index:04d}"
        valid_signals = _valid_signals(rng)
        rows.append(
            DatasetRow(
                base_id=base_id,
                document_type=document_type,
                mutation="valid",
                label=0,
                features=build_feature_vector(base, valid_signals),
            ),
        )
        mutations = _MUTATIONS[document_type]
        for mutation in rng.sample(mutations, k=actual.variants_per_base):
            summary = _mutated_summary(base, mutation, rng)
            signals = _signals_for(mutation, rng)
            rows.append(
                DatasetRow(
                    base_id=base_id,
                    document_type=document_type,
                    mutation=mutation,
                    label=1 if mutation in FRAUD_MUTATIONS else 0,
                    features=build_feature_vector(summary, signals),
                ),
            )

    row_tuple = tuple(rows)
    counts = {
        mutation: sum(1 for row in row_tuple if row.mutation == mutation)
        for mutation in sorted({row.mutation for row in row_tuple})
    }
    description = (
        f"synthetic feature dataset; seed={actual.seed}; "
        f"bases={actual.base_documents}; variants={actual.variants_per_base}; "
        f"rows={len(row_tuple)}; mutations={json.dumps(counts, sort_keys=True)}"
    )
    return SyntheticDataset(
        rows=row_tuple,
        hash=_dataset_hash(row_tuple, actual),
        description=description,
        seed=actual.seed,
        config=actual,
    )


def split_rows_by_base(
    rows: tuple[DatasetRow, ...],
    *,
    seed: int,
    validation_fraction: float = 0.2,
    test_fraction: float = 0.2,
) -> DatasetSplit:
    if not rows:
        raise ValueError("rows must not be empty")
    if not 0.0 < validation_fraction < 1.0 or not 0.0 < test_fraction < 1.0:
        raise ValueError("fractions must be between 0 and 1")
    if validation_fraction + test_fraction >= 1.0:
        raise ValueError("validation and test fractions must sum to less than 1")

    base_ids = sorted({row.base_id for row in rows})
    # Deterministic split; PRNG is not used for security.
    rng = random.Random(seed)  # nosec B311
    rng.shuffle(base_ids)
    test_count = max(1, round(len(base_ids) * test_fraction))
    validation_count = max(1, round(len(base_ids) * validation_fraction))
    if len(base_ids) - test_count - validation_count < 1:
        raise ValueError("not enough base documents for three splits")

    test_ids = set(base_ids[:test_count])
    validation_ids = set(base_ids[test_count : test_count + validation_count])
    train_ids = set(base_ids[test_count + validation_count :])
    return DatasetSplit(
        train=tuple(row for row in rows if row.base_id in train_ids),
        validation=tuple(row for row in rows if row.base_id in validation_ids),
        test=tuple(row for row in rows if row.base_id in test_ids),
        train_base_ids=tuple(sorted(train_ids)),
        validation_base_ids=tuple(sorted(validation_ids)),
        test_base_ids=tuple(sorted(test_ids)),
    )
