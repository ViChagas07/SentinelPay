import argparse
import json
from pathlib import Path

from paysentineliq.infrastructure.ml.synthetic import (
    SyntheticDatasetConfig,
    generate_synthetic_dataset,
)
from paysentineliq.infrastructure.ml.training import TrainingConfig, train_fraud_model


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train the synthetic fraud model.")
    parser.add_argument("--output-dir", type=Path, default=Path("../models/artifacts"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--bases", type=int, default=60)
    parser.add_argument("--variants", type=int, default=3)
    parser.add_argument("--model-version", default="fraud-risk-v1")
    parser.add_argument("--calibration-cv", type=int, default=3)
    args = parser.parse_args(argv)

    dataset = generate_synthetic_dataset(
        SyntheticDatasetConfig(
            seed=args.seed,
            base_documents=args.bases,
            variants_per_base=args.variants,
        ),
    )
    result = train_fraud_model(
        dataset,
        args.output_dir,
        TrainingConfig(
            model_version=args.model_version,
            seed=args.seed,
            calibration_cv=args.calibration_cv,
        ),
    )
    print("SYNTHETIC DATA - not real-world performance")
    print(f"dataset_hash={result.dataset_hash}")
    print(f"dataset_description={dataset.description}")
    print(f"artifact={result.artifact_path}")
    print(f"sha256={result.artifact_sha256}")
    print(json.dumps(result.metrics, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
