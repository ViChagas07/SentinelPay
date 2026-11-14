from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from tests.support.synthetic import write_fixtures  # noqa: E402


def main() -> int:
    target = ROOT / "backend" / "tests" / "fixtures" / "generated"
    written = write_fixtures(target)
    for path in written:
        print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
