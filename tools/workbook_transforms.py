#!/usr/bin/env python3
"""Deterministic transformation functions for approved workbook mappings."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable


class TransformError(ValueError):
    pass


def identity(value: Any) -> Any:
    return value


def trim(value: Any) -> Any:
    if value is None:
        return None
    return str(value).strip()


def integer(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise TransformError("boolean cannot be converted to integer")
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise TransformError(f"invalid integer: {value!r}") from exc
    if number != number.to_integral_value():
        raise TransformError(f"non-integral numeric value: {value!r}")
    return int(number)


def decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise TransformError("boolean cannot be converted to decimal")
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise TransformError(f"invalid decimal: {value!r}") from exc


def date_value(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for parser in (
        lambda s: date.fromisoformat(s),
        lambda s: datetime.strptime(s, "%m/%d/%Y").date(),
        lambda s: datetime.strptime(s, "%m/%d/%y").date(),
    ):
        try:
            return parser(text)
        except ValueError:
            continue
    raise TransformError(f"invalid date: {value!r}")


def datetime_value(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise TransformError(f"invalid datetime: {value!r}") from exc


def boolean(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "yes", "y", "1"}:
        return True
    if normalized in {"false", "no", "n", "0"}:
        return False
    raise TransformError(f"invalid boolean: {value!r}")


def normalize_name(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return " ".join(str(value).strip().split())


def split_names(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    text = str(value)
    delimiter = ";" if ";" in text else ","
    return [normalize_name(part) for part in text.split(delimiter) if normalize_name(part)]


TRANSFORMS: dict[str, Callable[[Any], Any]] = {
    "identity": identity,
    "trim": trim,
    "integer": integer,
    "decimal": decimal,
    "date": date_value,
    "datetime": datetime_value,
    "boolean": boolean,
    "normalize_name": normalize_name,
    "split_names": split_names,
}


def apply_transform(name: str, value: Any) -> Any:
    try:
        transform = TRANSFORMS[name]
    except KeyError as exc:
        raise TransformError(f"unknown transform: {name}") from exc
    return transform(value)
