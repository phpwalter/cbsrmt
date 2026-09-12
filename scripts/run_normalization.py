#!/usr/bin/env python3
"""Run the CBS RMT normalization pipeline in deterministic dependency order."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STEPS = [
    [sys.executable, str(ROOT / "scripts" / "build_source_manifest.py")],
    [sys.executable, str(ROOT / "scripts" / "inventory_legacy_sql.py")],
    [sys.executable, str(ROOT / "scripts" / "classify_legacy_sql.py")],
    [sys.executable, str(ROOT / "scripts" / "normalize_genres.py")],
    [sys.executable, str(ROOT / "scripts" / "normalize_people.py")],
    [sys.executable, str(ROOT / "scripts" / "normalize_episodes.py")],
    [sys.executable, str(ROOT / "scripts" / "validate_people.py")],
    [sys.executable, str(ROOT / "scripts" / "resolve_episode_relationships.py")],
    [sys.executable, str(ROOT / "scripts" / "extract_cast_credits.py")],
    [sys.executable, str(ROOT / "scripts" / "validate_relationships.py")],
]


def main() -> int:
    for command in STEPS:
        print(f"==> {' '.join(command)}")
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode != 0:
            print(f"FAILED ({result.returncode}): {' '.join(command)}", file=sys.stderr)
            return result.returncode
    print("Normalization pipeline completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
