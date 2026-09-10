from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

SEVERITIES = {"INFO", "WARNING", "ERROR", "FATAL"}
RESOLUTION_STATUSES = {"open", "accepted", "corrected", "rejected", "ignored"}


@dataclass(frozen=True)
class QualityIssue:
    severity: str
    issue_code: str
    message: str
    source_line: int | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    field_name: str | None = None
    raw_value: str | None = None
    normalized_value: str | None = None

    def validate(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"unsupported severity: {self.severity}")
        if not self.issue_code.strip():
            raise ValueError("issue_code must not be empty")
        if not self.message.strip():
            raise ValueError("message must not be empty")
        if self.source_line is not None and self.source_line <= 0:
            raise ValueError("source_line must be positive")


def record_issue(cur, *, source_id: str | None, import_batch_id: str | None, issue: QualityIssue) -> str:
    issue.validate()
    cur.execute(
        """
        INSERT INTO quality.issues (
            import_batch_id, source_id, entity_type, entity_id, source_line,
            severity, issue_code, field_name, raw_value, normalized_value, message
        ) VALUES (
            %s::uuid, %s::uuid, %s, %s::uuid, %s,
            %s, %s, %s, %s, %s, %s
        )
        RETURNING issue_id::text
        """,
        (
            import_batch_id,
            source_id,
            issue.entity_type,
            issue.entity_id,
            issue.source_line,
            issue.severity,
            issue.issue_code,
            issue.field_name,
            issue.raw_value,
            issue.normalized_value,
            issue.message,
        ),
    )
    return cur.fetchone()[0]


def quarantine_record(
    cur,
    *,
    import_batch_id: str,
    source_id: str | None,
    source_line: int | None,
    record_type: str,
    issue_code: str,
    raw_record: str,
    severity: str = "ERROR",
    parsed_payload: dict[str, Any] | None = None,
) -> str:
    if severity not in {"ERROR", "FATAL"}:
        raise ValueError("quarantine severity must be ERROR or FATAL")
    if not record_type.strip():
        raise ValueError("record_type must not be empty")
    if not issue_code.strip():
        raise ValueError("issue_code must not be empty")
    if source_line is not None and source_line <= 0:
        raise ValueError("source_line must be positive")

    cur.execute(
        """
        INSERT INTO quality.quarantine (
            import_batch_id, source_id, source_line, record_type, issue_code,
            raw_record, parsed_payload, severity
        ) VALUES (
            %s::uuid, %s::uuid, %s, %s, %s, %s, %s::jsonb, %s
        )
        RETURNING quarantine_id::text
        """,
        (
            import_batch_id,
            source_id,
            source_line,
            record_type,
            issue_code,
            raw_record,
            json.dumps(parsed_payload) if parsed_payload is not None else None,
            severity,
        ),
    )
    return cur.fetchone()[0]
