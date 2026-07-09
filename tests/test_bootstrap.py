import json
import sqlite3

import pytest

import scraper


def make_round(number):
    return {
        "drawNumber": str(number),
        "drawDate": "2026-07-09",
        "drawName": "Canadian Experience Class",
        "drawSize": "3,000",
        "drawCRS": "510",
    }


def test_empty_database_loads_the_verified_official_snapshot(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    result = scraper.initialize_db()

    assert result["status"] == "loaded"
    assert result["row_count"] == 426
    assert result["as_of_date"] == "2026-07-09"
    assert result["source_sha256"] == scraper.BUNDLED_SNAPSHOT_SHA256
    assert result["quality"]["status"] == "pass"
    assert result["quality"]["ingestion_allowed"] is True

    with sqlite3.connect(tmp_path / "data" / "express_entry.db") as connection:
        assert connection.execute(
            "SELECT COUNT(*), MIN(draw_date), MAX(draw_date) FROM express_entry"
        ).fetchone() == (426, "2015-01-31", "2026-07-09")
        assert connection.execute(
            '''
            SELECT origin, source_title, as_of_date, row_count, source_sha256
            FROM data_provenance
            WHERE singleton = 1
            '''
        ).fetchone() == (
            "bundled_ircc_snapshot",
            scraper.IRCC_ROUNDS_TITLE,
            "2026-07-09",
            426,
            scraper.BUNDLED_SNAPSHOT_SHA256,
        )


def test_bootstrap_does_not_overwrite_a_non_empty_database(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    scraper.initialize_db(bootstrap=False)
    with sqlite3.connect(tmp_path / "data" / "express_entry.db") as connection:
        connection.execute(
            '''
            INSERT INTO express_entry (
                draw_number, draw_date, draw_name, invitations, crs_cut_off, programs
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            ("local", "2020-01-01", "Existing row", 1, 1, "[]"),
        )

    result = scraper.initialize_db()

    assert result == {
        "status": "skipped",
        "reason": "database_not_empty",
        "row_count": 1,
    }
    with sqlite3.connect(tmp_path / "data" / "express_entry.db") as connection:
        assert connection.execute(
            "SELECT draw_number, draw_name FROM express_entry"
        ).fetchall() == [("local", "Existing row")]
        assert connection.execute(
            "SELECT COUNT(*) FROM data_provenance"
        ).fetchone()[0] == 0


def test_bootstrap_rolls_back_rows_and_provenance_on_insert_failure(
    monkeypatch,
    tmp_path,
):
    monkeypatch.chdir(tmp_path)
    snapshot_path = tmp_path / "fixture.json"
    snapshot_path.write_text(
        json.dumps({"rounds": [make_round(1), make_round(2)]}),
        encoding="utf-8",
    )
    scraper.initialize_db(bootstrap=False)

    real_insert = scraper._insert_draw_data
    calls = 0

    def fail_on_second_insert(cursor, draw):
        nonlocal calls
        calls += 1
        real_insert(cursor, draw)
        if calls == 2:
            raise sqlite3.OperationalError("simulated bootstrap failure")

    monkeypatch.setattr(scraper, "_insert_draw_data", fail_on_second_insert)

    with sqlite3.connect(tmp_path / "data" / "express_entry.db") as connection:
        with pytest.raises(sqlite3.OperationalError, match="simulated bootstrap failure"):
            scraper.bootstrap_database_if_empty(
                connection,
                snapshot_path=snapshot_path,
                snapshot_sha256=None,
                snapshot_as_of="2026-07-09",
                minimum_rows=2,
            )

    with sqlite3.connect(tmp_path / "data" / "express_entry.db") as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM express_entry"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM data_provenance"
        ).fetchone()[0] == 0


def test_bootstrap_rejects_a_snapshot_with_the_wrong_checksum(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    scraper.initialize_db(bootstrap=False)

    with sqlite3.connect(tmp_path / "data" / "express_entry.db") as connection:
        with pytest.raises(RuntimeError, match="checksum"):
            scraper.bootstrap_database_if_empty(
                connection,
                snapshot_path=scraper.BUNDLED_SNAPSHOT_PATH,
                snapshot_sha256="0" * 64,
                snapshot_as_of="2026-07-09",
                minimum_rows=100,
            )

        assert connection.execute(
            "SELECT COUNT(*) FROM express_entry"
        ).fetchone()[0] == 0
