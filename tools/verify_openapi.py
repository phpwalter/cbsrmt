#!/usr/bin/env python3
"""Verify that the FastAPI implementation matches the authoritative OpenAPI contract."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml

from app.main import app

SPEC_PATH = Path("api/openapi.yaml")
HTTP_METHODS = {"get", "put", "post", "delete", "patch", "head", "options", "trace"}


def normalize_path(path: str) -> str:
    return (
        path.replace("{episode_id}", "{episodeId}")
        .replace("{broadcast_id}", "{broadcastId}")
    )


def normalize_parameter_name(name: str) -> str:
    aliases = {
        "episode_id": "episodeId",
        "broadcast_id": "broadcastId",
        "show_number": "showNumber",
        "otrw_number": "otrwNumber",
        "broadcast_type": "type",
    }
    return aliases.get(name, name)


def operations(spec: dict[str, Any], normalize_generated: bool = False) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for path, path_item in spec.get("paths", {}).items():
        key_path = normalize_path(path) if normalize_generated else path
        for method, operation in path_item.items():
            if method.lower() in HTTP_METHODS:
                result[(key_path, method.lower())] = operation
    return result


def resolve_parameter(parameter: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    ref = parameter.get("$ref")
    if not ref:
        return parameter
    prefix = "#/components/parameters/"
    if not ref.startswith(prefix):
        raise ValueError(f"unsupported parameter reference: {ref}")
    name = ref[len(prefix):]
    return root["components"]["parameters"][name]


def parameter_names(operation: dict[str, Any], root: dict[str, Any], normalize: bool = False) -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    for parameter in operation.get("parameters", []):
        resolved = resolve_parameter(parameter, root)
        name = resolved.get("name", "")
        if normalize:
            name = normalize_parameter_name(name)
        result.add((resolved.get("in", ""), name))
    return result


def main() -> int:
    contract = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    generated = app.openapi()

    expected = operations(contract)
    actual = operations(generated, normalize_generated=True)
    errors: list[str] = []

    for path, method in sorted(set(expected) - set(actual)):
        errors.append(f"missing implemented operation: {method.upper()} {path}")
    for path, method in sorted(set(actual) - set(expected)):
        errors.append(f"undocumented implemented operation: {method.upper()} {path}")

    for key in sorted(set(expected) & set(actual)):
        expected_params = parameter_names(expected[key], contract)
        actual_params = parameter_names(actual[key], generated, normalize=True)

        for location, name in sorted(expected_params - actual_params):
            errors.append(f"{key[1].upper()} {key[0]} missing parameter: {location} {name}")
        for location, name in sorted(actual_params - expected_params):
            errors.append(f"{key[1].upper()} {key[0]} undocumented parameter: {location} {name}")

        expected_responses = set(expected[key].get("responses", {}))
        actual_responses = set(actual[key].get("responses", {}))
        for status in sorted(expected_responses - actual_responses):
            errors.append(f"{key[1].upper()} {key[0]} missing documented response: {status}")

    if errors:
        print("OPENAPI DRIFT: FAIL")
        for error in errors:
            print(f" - {error}")
        return 1

    print(f"OPENAPI DRIFT: PASS ({len(expected)} operations verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
