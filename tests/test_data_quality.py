import json
import sqlite3

import data_quality
import pytest


def make_round(number, draw_date="2026-07-09", size="3,000", crs="510"):
    return {
        "drawNumber": str(number),
        "drawDate": draw_date,
        "drawName": "Canadian Experience Class",
        "drawSize": size,
        "drawCRS": crs,
    }


def test_quality_report_passes_valid_payload_deterministically():
    report = data_quality.build_rounds_quality_report(
        [make_round(999)],
        as_of="2026-07-09",
        minimum_rows=1,
    )

    assert report["status"] == "pass"
    assert report["ingestion_allowed"] is True
    assert report["signals"]["row_count"] == {
        "value": 1,
        "minimum": 1,
        "status": "pass",
    }
    assert report["signals"]["freshness"]["age_days"] == 0
    assert report["signals"]["null_rates"]["invitations"]["rate"] == 0.0
    assert report["usage_boundary"]["not_legal_advice"] is True


def test_quality_report_blocks_truncated_payload():
    report = data_quality.build_rounds_quality_report(
        [make_round(999)],
        as_of="2026-07-09",
        minimum_rows=100,
    )

    assert report["status"] == "fail"
    assert report["ingestion_allowed"] is False
    assert report["blocking_reasons"] == ["row_count_below_minimum:1<100"]


def test_quality_report_blocks_date_prefix_with_malformed_suffix():
    report = data_quality.build_rounds_quality_report(
        [make_round(999, draw_date="2026-07-09garbage")],
        as_of="2026-07-09",
        minimum_rows=1,
    )

    assert report["ingestion_allowed"] is False
    assert report["signals"]["types"]["invalid_value_counts"]["drawDate"] == 1
    assert "invalid_identity_or_date:drawDate=1" in report["blocking_reasons"]


@pytest.mark.parametrize(
    ("field", "kwargs"),
    [
        ("drawSize", {"size": "-1"}),
        ("drawCRS", {"crs": "-510"}),
        ("drawSize", {"size": -1}),
        ("drawCRS", {"crs": -510}),
    ],
)
def test_quality_report_blocks_negative_numeric_values(field, kwargs):
    report = data_quality.build_rounds_quality_report(
        [make_round(999, **kwargs)],
        as_of="2026-07-09",
        minimum_rows=1,
    )

    assert report["ingestion_allowed"] is False
    assert report["signals"]["types"]["invalid_value_counts"][field] == 1
    assert any(
        reason.startswith("numeric_null_rate_above_limit:")
        for reason in report["blocking_reasons"]
    )


@pytest.mark.parametrize("draw_number", ["draw-999", "999ab", "0", "-999", ""])
def test_quality_report_blocks_non_positive_or_arbitrary_draw_identity(draw_number):
    report = data_quality.build_rounds_quality_report(
        [make_round(draw_number)],
        as_of="2026-07-09",
        minimum_rows=1,
    )

    assert report["ingestion_allowed"] is False
    assert report["signals"]["types"]["invalid_value_counts"]["drawNumber"] == 1
    assert "invalid_identity_or_date:drawNumber=1" in report["blocking_reasons"]


def test_quality_report_accepts_official_letter_suffixed_draw_identities():
    report = data_quality.build_rounds_quality_report(
        [make_round("91a"), make_round("91b")],
        as_of="2026-07-09",
        minimum_rows=2,
    )

    assert report["ingestion_allowed"] is True
    assert report["signals"]["types"]["invalid_value_counts"]["drawNumber"] == 0


def test_quality_report_canonicalizes_zero_padded_duplicate_draw_identity():
    report = data_quality.build_rounds_quality_report(
        [make_round("0999"), make_round("999")],
        as_of="2026-07-09",
        minimum_rows=2,
    )

    assert report["ingestion_allowed"] is False
    assert report["signals"]["duplicates"]["draw_numbers"] == ["999"]
    assert "duplicate_draw_numbers:999" in report["blocking_reasons"]


def test_null_rate_threshold_uses_unrounded_value_for_status():
    signal = data_quality._rate_signal(nulls=201, total=10049, maximum=0.02)

    assert signal["rate"] == 0.02
    assert signal["status"] == "fail"


def test_quality_report_blocks_schema_identity_duplicate_and_future_errors():
    rounds = [
        make_round(999, draw_date="2026-07-20"),
        make_round(999, draw_date="not-a-date"),
        {
            "drawNumber": "1000",
            "drawDate": "2026-07-09",
            "drawName": "",
            "drawSize": "3,000",
        },
    ]
    report = data_quality.build_rounds_quality_report(
        rounds,
        as_of="2026-07-09",
        minimum_rows=3,
        maximum_numeric_null_rate=0.5,
    )

    assert report["ingestion_allowed"] is False
    assert report["signals"]["schema"]["missing_field_counts"]["drawCRS"] == 1
    assert report["signals"]["types"]["invalid_value_counts"]["drawDate"] == 1
    assert report["signals"]["duplicates"]["draw_numbers"] == ["999"]
    assert any(
        reason.startswith("latest_draw_date_is_in_future:")
        for reason in report["blocking_reasons"]
    )


def test_small_numeric_null_rate_warns_without_blocking():
    rounds = [make_round(number) for number in range(1, 101)]
    rounds[0]["drawCRS"] = "not available"

    report = data_quality.build_rounds_quality_report(
        rounds,
        as_of="2026-07-09",
        minimum_rows=100,
        maximum_numeric_null_rate=0.02,
    )

    assert report["status"] == "warn"
    assert report["ingestion_allowed"] is True
    assert report["signals"]["null_rates"]["crs_cut_off"] == {
        "nulls": 1,
        "rate": 0.01,
        "maximum_rate": 0.02,
        "status": "warn",
    }


def test_stale_authoritative_data_is_visible_but_not_rejected():
    report = data_quality.build_rounds_quality_report(
        [make_round(999, draw_date="2025-01-01")],
        as_of="2026-07-09",
        minimum_rows=1,
    )

    assert report["status"] == "fail"
    assert report["ingestion_allowed"] is True
    assert report["signals"]["freshness"]["age_days"] == 554
    assert report["warnings"] == ["source_data_stale:554_days"]


def test_sqlite_cli_prints_report_without_network(tmp_path, capsys):
    db_path = tmp_path / "draws.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE express_entry (
                draw_number TEXT,
                draw_date TEXT,
                draw_name TEXT,
                invitations INTEGER,
                crs_cut_off INTEGER
            )
            """
        )
        connection.execute(
            "INSERT INTO express_entry VALUES (?, ?, ?, ?, ?)",
            ("999", "2026-07-09", "Canadian Experience Class", 3000, 510),
        )

    exit_code = data_quality.main(
        [
            "--db",
            str(db_path),
            "--as-of",
            "2026-07-09",
            "--minimum-rows",
            "1",
            "--strict",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["status"] == "pass"
    assert output["signals"]["row_count"]["value"] == 1
