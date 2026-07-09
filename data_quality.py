"""Deterministic quality checks for IRCC Express Entry draw data.

The checks in this module use only the Python standard library. They can run
against a downloaded JSON fixture or a local SQLite database without network
access, which makes the same contract usable in tests, CI, and operations.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "1.0"
REQUIRED_FIELDS = (
    "drawNumber",
    "drawDate",
    "drawName",
    "drawSize",
    "drawCRS",
)
INTEGER_PATTERN = re.compile(r"^(?:\d+|\d{1,3}(?:,\d{3})+)$")
DRAW_NUMBER_PATTERN = re.compile(r"^(?P<number>\d+)(?P<suffix>[A-Za-z]?)$")
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
USAGE_BOUNDARY = {
    "authoritative_source": "Immigration, Refugees and Citizenship Canada (IRCC)",
    "not_legal_advice": True,
    "statement": (
        "This report checks historical draw-data integrity only. It does not "
        "determine eligibility, predict invitations, or provide immigration or "
        "legal advice. Verify current rules with IRCC or an authorized professional."
    ),
}


class DataQualityError(RuntimeError):
    """Raised when a payload is unsafe to persist under the ingestion contract."""

    def __init__(self, report: dict[str, Any]):
        self.report = report
        reasons = "; ".join(report["blocking_reasons"]) or "unknown quality failure"
        super().__init__(
            f"IRCC rounds failed the ingestion quality contract: {reasons}"
        )


def parse_ircc_int(value: Any) -> int | None:
    """Parse non-negative plain or thousands-separated IRCC integer fields."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return None

    cleaned = value.strip()
    if not cleaned or not INTEGER_PATTERN.fullmatch(cleaned):
        return None
    return int(cleaned.replace(",", ""))


def _parse_draw_number(value: Any) -> str | None:
    """Return a canonical positive draw identity with an optional letter suffix."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value) if value > 0 else None
    if not isinstance(value, str):
        return None

    cleaned = value.strip()
    match = DRAW_NUMBER_PATTERN.fullmatch(cleaned)
    if not match:
        return None
    number = int(match.group("number"))
    if number <= 0:
        return None
    return f"{number}{match.group('suffix').lower()}"


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None

    cleaned = value.strip()
    if not ISO_DATE_PATTERN.fullmatch(cleaned):
        return None
    try:
        return date.fromisoformat(cleaned)
    except ValueError:
        return None


def _parse_as_of(value: date | str | None) -> date:
    if value is None:
        return date.today()
    parsed = _parse_date(value)
    if parsed is None:
        raise ValueError("as_of must be an ISO date in YYYY-MM-DD format")
    return parsed


def _rate_signal(nulls: int, total: int, maximum: float) -> dict[str, Any]:
    raw_rate = nulls / total if total else 1.0
    if raw_rate > maximum:
        status = "fail"
    elif nulls:
        status = "warn"
    else:
        status = "pass"
    return {
        "nulls": nulls,
        "rate": round(raw_rate, 4),
        "maximum_rate": maximum,
        "status": status,
    }


def build_rounds_quality_report(
    rounds: Sequence[Mapping[str, Any]] | Any,
    *,
    as_of: date | str | None = None,
    minimum_rows: int = 100,
    maximum_numeric_null_rate: float = 0.02,
    freshness_warning_days: int = 45,
    freshness_failure_days: int = 120,
    future_tolerance_days: int = 1,
) -> dict[str, Any]:
    """Return a JSON-serializable quality report for an IRCC rounds payload.

    Structural failures, truncated payloads, duplicate identities, invalid
    identity/date values, excessive numeric nulls, and implausible future dates
    block persistence. Historical staleness is reported but does not block a
    refresh because IRCC may legitimately pause draws.
    """
    if minimum_rows < 1:
        raise ValueError("minimum_rows must be at least 1")
    if not 0 <= maximum_numeric_null_rate <= 1:
        raise ValueError("maximum_numeric_null_rate must be between 0 and 1")
    if not 0 <= freshness_warning_days <= freshness_failure_days:
        raise ValueError("freshness thresholds must be non-negative and ordered")
    if future_tolerance_days < 0:
        raise ValueError("future_tolerance_days must be non-negative")

    evaluated_as_of = _parse_as_of(as_of)
    payload_is_sequence = isinstance(rounds, Sequence) and not isinstance(
        rounds, (str, bytes, bytearray)
    )
    rows = list(rounds) if payload_is_sequence else []
    total = len(rows)

    missing_counts = {field: 0 for field in REQUIRED_FIELDS}
    invalid_counts = {field: 0 for field in REQUIRED_FIELDS}
    invalid_row_structures = 0
    normalized_numbers: list[str] = []
    valid_dates: list[date] = []
    numeric_nulls = {"drawSize": 0, "drawCRS": 0}

    for row in rows:
        if not isinstance(row, Mapping):
            invalid_row_structures += 1
            continue

        for field in REQUIRED_FIELDS:
            if field not in row:
                missing_counts[field] += 1

        draw_number = _parse_draw_number(row.get("drawNumber"))
        if draw_number is None:
            invalid_counts["drawNumber"] += 1
        else:
            normalized_numbers.append(draw_number)

        draw_date = _parse_date(row.get("drawDate"))
        if draw_date is None:
            invalid_counts["drawDate"] += 1
        else:
            valid_dates.append(draw_date)

        draw_name = row.get("drawName")
        if not isinstance(draw_name, str) or not draw_name.strip():
            invalid_counts["drawName"] += 1

        for field in ("drawSize", "drawCRS"):
            if parse_ircc_int(row.get(field)) is None:
                invalid_counts[field] += 1
                numeric_nulls[field] += 1

    duplicate_numbers = sorted(
        number
        for number in set(normalized_numbers)
        if normalized_numbers.count(number) > 1
    )
    missing_nonzero = {field: count for field, count in missing_counts.items() if count}
    blocking_reasons: list[str] = []
    warnings: list[str] = []
    if not payload_is_sequence:
        blocking_reasons.append("payload_must_be_an_array")
    if total < minimum_rows:
        blocking_reasons.append(f"row_count_below_minimum:{total}<{minimum_rows}")
    if invalid_row_structures:
        blocking_reasons.append(f"invalid_row_structures:{invalid_row_structures}")
    if missing_nonzero:
        detail = ",".join(
            f"{field}={count}" for field, count in missing_nonzero.items()
        )
        blocking_reasons.append(f"missing_required_fields:{detail}")

    identity_invalid = {
        field: invalid_counts[field]
        for field in ("drawNumber", "drawDate", "drawName")
        if invalid_counts[field]
    }
    if identity_invalid:
        detail = ",".join(
            f"{field}={count}" for field, count in identity_invalid.items()
        )
        blocking_reasons.append(f"invalid_identity_or_date:{detail}")
    if duplicate_numbers:
        blocking_reasons.append(
            "duplicate_draw_numbers:" + ",".join(duplicate_numbers[:10])
        )

    null_rate_signals = {
        "invitations": _rate_signal(
            numeric_nulls["drawSize"], total, maximum_numeric_null_rate
        ),
        "crs_cut_off": _rate_signal(
            numeric_nulls["drawCRS"], total, maximum_numeric_null_rate
        ),
    }
    for field, signal in null_rate_signals.items():
        if signal["status"] == "fail":
            blocking_reasons.append(
                f"numeric_null_rate_above_limit:{field}={signal['rate']}"
            )
        elif signal["status"] == "warn":
            warnings.append(f"numeric_nulls_present:{field}={signal['nulls']}")

    latest_date = max(valid_dates) if valid_dates else None
    age_days = (evaluated_as_of - latest_date).days if latest_date else None
    if age_days is None:
        freshness_status = "fail"
    elif age_days < -future_tolerance_days:
        freshness_status = "fail"
        blocking_reasons.append(
            f"latest_draw_date_is_in_future:{latest_date.isoformat()}"
        )
    elif age_days > freshness_failure_days:
        freshness_status = "fail"
        warnings.append(f"source_data_stale:{age_days}_days")
    elif age_days > freshness_warning_days:
        freshness_status = "warn"
        warnings.append(f"source_data_aging:{age_days}_days")
    else:
        freshness_status = "pass"

    schema_status = (
        "fail"
        if invalid_row_structures or missing_nonzero or not payload_is_sequence
        else "pass"
    )
    if identity_invalid:
        types_status = "fail"
    elif invalid_counts["drawSize"] or invalid_counts["drawCRS"]:
        types_status = (
            "fail"
            if any(signal["status"] == "fail" for signal in null_rate_signals.values())
            else "warn"
        )
    else:
        types_status = "pass"

    signal_statuses = [
        "fail" if total < minimum_rows else "pass",
        schema_status,
        types_status,
        "fail" if duplicate_numbers else "pass",
        freshness_status,
        *(signal["status"] for signal in null_rate_signals.values()),
    ]
    if "fail" in signal_statuses:
        overall_status = "fail"
    elif "warn" in signal_statuses:
        overall_status = "warn"
    else:
        overall_status = "pass"

    return {
        "contract_version": CONTRACT_VERSION,
        "evaluated_as_of": evaluated_as_of.isoformat(),
        "status": overall_status,
        "ingestion_allowed": not blocking_reasons,
        "blocking_reasons": blocking_reasons,
        "warnings": warnings,
        "signals": {
            "row_count": {
                "value": total,
                "minimum": minimum_rows,
                "status": "pass" if total >= minimum_rows else "fail",
            },
            "schema": {
                "required_fields": list(REQUIRED_FIELDS),
                "invalid_row_structures": invalid_row_structures,
                "missing_field_counts": missing_counts,
                "status": schema_status,
            },
            "types": {
                "invalid_value_counts": invalid_counts,
                "status": types_status,
            },
            "duplicates": {
                "draw_numbers": duplicate_numbers,
                "status": "fail" if duplicate_numbers else "pass",
            },
            "null_rates": null_rate_signals,
            "freshness": {
                "latest_draw_date": latest_date.isoformat() if latest_date else None,
                "age_days": age_days,
                "warning_after_days": freshness_warning_days,
                "failure_after_days": freshness_failure_days,
                "future_tolerance_days": future_tolerance_days,
                "status": freshness_status,
            },
        },
        "usage_boundary": USAGE_BOUNDARY,
    }


def require_ingestion_quality(report: dict[str, Any]) -> None:
    """Raise when a quality report says the payload is unsafe to persist."""
    if not report["ingestion_allowed"]:
        raise DataQualityError(report)


def _load_json_rounds(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, Mapping):
        return payload.get("rounds")
    return payload


def _load_sqlite_rounds(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"SQLite database not found: {path}")
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            """
            SELECT
                draw_number AS drawNumber,
                draw_date AS drawDate,
                draw_name AS drawName,
                invitations AS drawSize,
                crs_cut_off AS drawCRS
            FROM express_entry
            ORDER BY draw_date, draw_number
            """
        ).fetchall()
    return [dict(zip(REQUIRED_FIELDS, row, strict=True)) for row in rows]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate an offline IRCC draw payload or SQLite database."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--json", type=Path, help="IRCC JSON payload or rounds array")
    source.add_argument("--db", type=Path, help="Local Express Entry SQLite database")
    parser.add_argument("--as-of", help="Deterministic evaluation date (YYYY-MM-DD)")
    parser.add_argument("--minimum-rows", type=int, default=100)
    parser.add_argument("--maximum-numeric-null-rate", type=float, default=0.02)
    parser.add_argument("--freshness-warning-days", type=int, default=45)
    parser.add_argument("--freshness-failure-days", type=int, default=120)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return a non-zero exit code for warnings or freshness failures too.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        rounds = (
            _load_json_rounds(args.json)
            if args.json is not None
            else _load_sqlite_rounds(args.db)
        )
        report = build_rounds_quality_report(
            rounds,
            as_of=args.as_of,
            minimum_rows=args.minimum_rows,
            maximum_numeric_null_rate=args.maximum_numeric_null_rate,
            freshness_warning_days=args.freshness_warning_days,
            freshness_failure_days=args.freshness_failure_days,
        )
    except (FileNotFoundError, json.JSONDecodeError, sqlite3.Error, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 2

    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["ingestion_allowed"]:
        return 1
    if args.strict and report["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
