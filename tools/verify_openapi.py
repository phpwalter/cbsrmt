#!/usr/bin/env python3
"""Verify that the FastAPI implementation matches the authoritative OpenAPI contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

from app.main import app

SPEC_PATH = Path("api/openapi.yaml")
HTTP_METHODS = {"get", "put", "post", "delete", "patch", "head", "options", "trace"}


def normalize_path(path: str) -> str:
    """Normalize FastAPI snake_case path parameter names to contract camelCase names."""
    return (
        path.replace("{episode_id}", "{episodeId}")
        .replace("{broadcast_id}", "{broadcastId}")
    )


def contract_operations(spec: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    operations: dict[tuple[str, str], dict[str, Any]] = {}
    for path, path_item in spec.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.lower() in HTTP_METHODS:
                operations[(path, method.lower())] = operation
    return operations


def generated_operations(spec: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    operations: dict[tuple[str, str], dict[str, Any]] = {}
    for path, path_item in spec.get("paths", {}).items():
        normalized = normalize_path(path)
        for method, operation in path_item.items():
            if method.lower() in HTTP_METHODS:
                operations[(normalized, method.lower())] = operation
    return operations


def parameter_names(operation: dict[str, Any]) -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    for parameter in operation.get("parameters", []):
        if "$ref" in parameter:
            continue
        result.add((parameter.get("in", ""), parameter.get("name", "")))
    return result


def main() -> int:
    contract = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    generated = app.openapi()

    expected = contract_operations(contract)
    actual = generated_operations(generated)

    errors: list[str] = []

    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))

    for path, method in missing:
        errors.append(f"missing implemented operation: {method.upper()} {path}")
    for path, method in extra:
        if path in {"/docs", "/redoc", "/openapi.json"}:
            continue
        errors.append(f"undocumented implemented operation: {method.upper()} {path}")

    for key in sorted(set(expected) & set(actual)):
        expected_params = parameter_names(expected[key])
        actual_params = parameter_names(actual[key])
        missing_params = sorted(expected_params - actual_params)
        extra_params = sorted(actual_params - expected_params)
        for location, name in missing_params:
            errors.append(
                f"{key[1].upper()} {key[0]} missing parameter: {location} {name}"
            )
        for location, name in extra_params:
            errors.append(
                f"{key[1].upper()} {key[0]} undocumented parameter: {location} {name}"
            )

        expected_responses = set(expected[key].get("responses", {}))
        actual_responses = set(actual[key].get("responses", {}))
        for status in sorted(expected_responses - actual_responses):
            errors.append(
                f"{key[1].upper()} {key[0]} missing documented response: {status}"
            )

    if errors:
        print("OPENAPI DRIFT: FAIL")
        for error in errors:
            print(f" - {error}")
        return 1

    print(f"OPENAPI DRIFT: PASS ({len(expected)} operations verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
