#!/usr/bin/env python3
"""Build a deterministic manifest of CBS RMT source artifacts.

The manifest records path, size, and SHA-256 for every configured source file.
Execution timestamps are intentionally excluded so identical inputs yield identical
manifest output.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data" / "source-manifest.json"
OUTPUT_PATH = ROOT / "data" / "normalized" / "source-manifest.lock.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    artifacts = []

    for item in sorted(config["artifacts"], key=lambda value: value["path"]):
        relative_path = Path(item["path"])
        source_path = ROOT / relative_path
        if not source_path.is_file():
            raise FileNotFoundError(f"Configured source artifact does not exist: {relative_path}")

        artifacts.append(
            {
                "path": relative_path.as_posix(),
                "artifact_type": item["artifact_type"],
                "role": item["role"],
                "size_bytes": source_path.stat().st_size,
                "sha256": sha256_file(source_path),
            }
        )

    payload = {
        "manifest_version": config["manifest_version"],
        "artifacts": artifacts,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT_PATH.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
