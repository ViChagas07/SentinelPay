import argparse
import json
import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_OUTPUT = _REPO_ROOT / "backend" / "tests" / "contracts" / "openapi.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exporta o contrato OpenAPI local para o snapshot de testes.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help="arquivo de saida do snapshot",
    )
    args = parser.parse_args()

    os.environ["APP_ENV"] = "local"

    from paysentineliq.infrastructure.config import Settings
    from paysentineliq.interface.api.main import create_app

    schema = create_app(Settings(app_env="local")).openapi()
    output: Path = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"openapi snapshot escrito em {output}")


if __name__ == "__main__":
    main()
