from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "backend" / "migrations" / "versions"
_PATTERN = re.compile(r"^(\d{4})_")


def main() -> int:
    numbers = [
        int(match.group(1))
        for path in VERSIONS.glob("*.py")
        if (match := _PATTERN.match(path.name)) is not None
    ]
    print(f"{max(numbers, default=0) + 1:04d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
