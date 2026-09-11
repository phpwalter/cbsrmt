from datetime import date, datetime
from decimal import Decimal

import pytest

from tools.import_workbook import mapped_entities
from tools.workbook_handlers import HandlerError, get_handler, require_enabled_handlers
from tools.workbook_transforms import TransformError, apply_transform


def test_integer_transform_accepts_integral_values():
    assert apply_transform("integer", "1273") == 1273
    assert apply_transform("integer", 1273.0) == 1273


def test_integer_transform_rejects_fractional_values():
    with pytest.raises(TransformError, match="non-integral"):
        apply_transform("integer", "12.5")


def test_decimal_transform_is_decimal_not_float():
    assert apply_transform("decimal", "12.50") == Decimal("12.50")


def test_date_transform_supports_iso_and_us_dates():
    assert apply_transform("date", "1982-01-04") == date(1982, 1, 4)
    assert apply_transform("date", "01/04/1982") == date(1982, 1, 4)


def test_datetime_transform_supports_iso_datetime():
    assert apply_transform("datetime", "1982-01-04T20:00:00") == datetime(1982, 1, 4, 20, 0)


def test_boolean_transform_is_explicit():
    assert apply_transform("boolean", "yes") is True
    assert apply_transform("boolean", "0") is False
    with pytest.raises(TransformError, match="invalid boolean"):
        apply_transform("boolean", "sometimes")


def test_normalize_name_collapses_whitespace_only():
    assert apply_transform("normalize_name", "  Tammy   Grimes ") == "Tammy Grimes"


def test_split_names_is_deterministic():
    assert apply_transform("split_names", "A; B ;C") == ["A", "B", "C"]


def test_unknown_transform_fails_closed():
    with pytest.raises(TransformError, match="unknown transform"):
        apply_transform("guess", "value")


def test_known_handler_is_registered_but_disabled():
    handler = get_handler("episode")
    with pytest.raises(HandlerError, match="not enabled"):
        handler(None, None, {}, {})


def test_unknown_handler_fails_closed():
    with pytest.raises(HandlerError, match="unsupported canonical entity"):
        get_handler("mystery_entity")


def test_handler_preflight_rejects_disabled_handlers_before_execution():
    with pytest.raises(HandlerError, match="not enabled"):
        require_enabled_handlers({"episode", "broadcast"})


def test_handler_preflight_rejects_unknown_handlers():
    with pytest.raises(HandlerError, match="unsupported canonical entity handler"):
        require_enabled_handlers({"mystery_entity"})


def test_mapped_entities_only_uses_approved_sheets():
    mapping = {
        "sheets": [
            {
                "status": "APPROVED",
                "columns": [
                    {"target": {"entity": "episode", "field": "title"}},
                    {"target": {"entity": "broadcast", "field": "broadcast_date"}},
                ],
            },
            {
                "status": "REVIEW_REQUIRED",
                "columns": [
                    {"target": {"entity": "person", "field": "display_name"}},
                ],
            },
        ]
    }
    assert mapped_entities(mapping) == {"episode", "broadcast"}
