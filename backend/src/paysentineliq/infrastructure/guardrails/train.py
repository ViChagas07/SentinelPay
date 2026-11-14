import argparse
import json
from pathlib import Path

from paysentineliq.infrastructure.guardrails.synthetic import (
    InjectionDatasetConfig,
    generate_injection_dataset,
)
from paysentineliq.infrastructure.guardrails.training import (
    TrainingConfig,
    train_injection_classifier,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train the synthetic injection classifier.")
    parser.add_argument("--output-dir", type=Path, default=Path("../models/artifacts"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--injection-variants", type=int, default=120)
    parser.add_argument("--benign-variants", type=int, default=120)
    parser.add_argument("--model-version", default="guardrail-injection-v1")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args(argv)

    dataset = generate_injection_dataset(
        InjectionDatasetConfig(
            seed=args.seed,
            injection_variants=args.injection_variants,
            benign_variants=args.benign_variants,
        ),
    )
    result = train_injection_classifier(
        dataset,
        args.output_dir,
        TrainingConfig(
            model_version=args.model_version,
            seed=args.seed,
            threshold=args.threshold,
        ),
    )
    print("SYNTHETIC DATA - limited coverage, not real-world performance")
    print(f"dataset_hash={result.dataset_hash}")
    print(f"artifact={result.artifact_path}")
    print(f"sha256={result.artifact_sha256}")
    print(json.dumps(result.metrics, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
