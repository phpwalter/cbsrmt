#!/usr/bin/env python3
"""Explicit canonical entity handlers for approved workbook mappings.

Handlers are intentionally registered by canonical entity name. Unknown entity
names fail closed; there is no generic table-name interpolation path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable


class HandlerError(ValueError):
    pass


@dataclass(frozen=True)
class HandlerContext:
    source_id: str
    import_batch_id: str
    workbook_id: str
    sheet_name: str
    row_number: int


Handler = Callable[[Any, HandlerContext, dict[str, Any], dict[str, Any]], str | None]


def not_implemented(entity: str) -> Handler:
    def handler(cur, context: HandlerContext, values: dict[str, Any], provenance: dict[str, Any]) -> str | None:
        raise HandlerError(
            f"canonical handler for {entity!r} is not enabled until an evidence-backed mapping is approved"
        )

    return handler


# Registry is explicit by design. Handlers become real only when the historical
# workbook has been inspected and the target semantics are known.
HANDLERS: dict[str, Handler] = {
    "episode": not_implemented("episode"),
    "broadcast": not_implemented("broadcast"),
    "person": not_implemented("person"),
    "episode_credit": not_implemented("episode_credit"),
    "work": not_implemented("work"),
    "adaptation": not_implemented("adaptation"),
    "recording": not_implemented("recording"),
}

# Keep readiness separate from callability so dry-run planning can describe
# future canonical writes without allowing execution to reach disabled handlers.
ENABLED_HANDLERS: set[str] = set()


def get_handler(entity: str) -> Handler:
    try:
        return HANDLERS[entity]
    except KeyError as exc:
        raise HandlerError(f"unsupported canonical entity handler: {entity!r}") from exc


def require_enabled_handlers(entities: Iterable[str]) -> None:
    requested = sorted(set(entities))
    unsupported = [entity for entity in requested if entity not in HANDLERS]
    if unsupported:
        raise HandlerError(
            "unsupported canonical entity handler(s): " + ", ".join(repr(entity) for entity in unsupported)
        )

    disabled = [entity for entity in requested if entity not in ENABLED_HANDLERS]
    if disabled:
        raise HandlerError(
            "canonical handler(s) not enabled: " + ", ".join(repr(entity) for entity in disabled)
        )
