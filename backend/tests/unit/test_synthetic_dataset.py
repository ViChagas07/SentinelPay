import pytest

from paysentineliq.application.queries.fraud_features import FEATURE_NAMES
from paysentineliq.infrastructure.ml.synthetic import (
    FRAUD_MUTATIONS,
    SyntheticDatasetConfig,
    generate_synthetic_dataset,
    split_rows_by_base,
)

pytestmark = pytest.mark.unit


def _config(seed: int = 42, bases: int = 24) -> SyntheticDatasetConfig:
    return SyntheticDatasetConfig(seed=seed, base_documents=bases, variants_per_base=2)


def test_same_seed_is_deterministic() -> None:
    first = generate_synthetic_dataset(_config())
    second = generate_synthetic_dataset(_config())

    assert first.hash == second.hash
    assert first.rows == second.rows
    assert first.description == second.description


def test_different_seed_changes_dataset() -> None:
    first = generate_synthetic_dataset(_config(seed=42))
    second = generate_synthetic_dataset(_config(seed=43))

    assert first.hash != second.hash


def test_dataset_has_both_types_labels_and_synthetic_flag() -> None:
    dataset = generate_synthetic_dataset(_config())

    assert dataset.synthetic is True
    assert {row.document_type for row in dataset.rows} == {"boleto", "payslip"}
    assert {row.label for row in dataset.rows} == {0, 1}
    assert len({row.base_id for row in dataset.rows}) == 24
    assert all(row.synthetic for row in dataset.rows)


def test_mutations_have_expected_labels() -> None:
    dataset = generate_synthetic_dataset(_config())

    for row in dataset.rows:
        expected = 1 if row.mutation in FRAUD_MUTATIONS else 0
        assert row.label == expected, row.mutation


def test_split_by_base_has_no_leakage() -> None:
    dataset = generate_synthetic_dataset(_config())

    split = split_rows_by_base(dataset.rows, seed=42)

    train_bases = {row.base_id for row in split.train}
    validation_bases = {row.base_id for row in split.validation}
    test_bases = {row.base_id for row in split.test}
    assert train_bases
    assert validation_bases
    assert test_bases
    assert not train_bases & validation_bases
    assert not train_bases & test_bases
    assert not validation_bases & test_bases
    assert len(split.train) + len(split.validation) + len(split.test) == len(dataset.rows)


def test_features_have_fixed_length_and_no_raw_text() -> None:
    dataset = generate_synthetic_dataset(_config())

    assert all(len(row.features) == len(FEATURE_NAMES) for row in dataset.rows)
    assert all(isinstance(value, float) for row in dataset.rows for value in row.features)
    assert all(not hasattr(row, "text") for row in dataset.rows)


def test_missing_table_is_label_zero_and_not_validated() -> None:
    dataset = generate_synthetic_dataset(_config(bases=40))
    rows = [row for row in dataset.rows if row.mutation == "missing_table"]

    assert rows
    for row in rows:
        values = dict(zip(FEATURE_NAMES, row.features, strict=True))
        assert row.label == 0
        assert values["not_validated_count"] > 0


def test_pasted_region_has_high_visual_signal() -> None:
    dataset = generate_synthetic_dataset(_config(bases=40))
    rows = [row for row in dataset.rows if row.mutation == "pasted_region"]

    assert rows
    for row in rows:
        values = dict(zip(FEATURE_NAMES, row.features, strict=True))
        assert row.label == 1
        assert values["visual_max"] >= 0.5


def test_config_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        SyntheticDatasetConfig(base_documents=0)
    with pytest.raises(ValueError):
        SyntheticDatasetConfig(variants_per_base=0)
    with pytest.raises(ValueError):
        SyntheticDatasetConfig(seed=-1)
