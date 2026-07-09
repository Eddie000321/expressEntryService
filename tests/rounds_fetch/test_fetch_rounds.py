import json
import sqlite3

import pytest

import scraper


class FakeResponse:
    def __init__(self, *, text="", payload=None):
        self.text = text
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_resolve_rounds_json_url_uses_current_ircc_configuration(monkeypatch):
    page = """
        <div data-wb-json="not-json"></div>
        <div data-wb-json='{&quot;url&quot;: "/content/dam/ircc/ee_rounds_999_en.json#data"}'></div>
    """
    monkeypatch.setattr(
        scraper.requests,
        "get",
        lambda url, timeout: FakeResponse(text=page),
    )

    assert scraper._resolve_rounds_json_url() == (
        "https://www.canada.ca/content/dam/ircc/ee_rounds_999_en.json"
    )


def test_resolve_rounds_json_url_fails_when_configuration_is_missing(monkeypatch):
    monkeypatch.setattr(
        scraper.requests,
        "get",
        lambda url, timeout: FakeResponse(text="<main>No rounds configuration</main>"),
    )

    with pytest.raises(RuntimeError, match="Could not locate"):
        scraper._resolve_rounds_json_url()


def test_fetch_and_store_rounds_returns_counts_and_normalizes_programs(monkeypatch):
    json_url = "https://www.canada.ca/content/dam/ircc/ee_rounds_999_en.json"
    rounds = [
        {
            "drawNumber": "999",
            "drawDate": "2026-07-09",
            "drawName": "Canadian Experience Class",
            "drawSize": "3,000",
            "drawCRS": "510",
        }
    ]
    stored = []

    monkeypatch.setattr(scraper, "_resolve_rounds_json_url", lambda: json_url)
    monkeypatch.setattr(
        scraper.requests,
        "get",
        lambda url, timeout: FakeResponse(payload={"rounds": rounds}),
    )
    monkeypatch.setattr(
        scraper,
        "persist_draw_batch",
        lambda draws: stored.extend(draw.copy() for draw in draws),
    )

    result = scraper.fetch_and_store_rounds(
        as_of="2026-07-09",
        minimum_rows=1,
    )
    assert result["json_url"] == json_url
    assert result["total_rounds"] == 1
    assert result["stored"] == 1
    assert result["quality"]["status"] == "pass"
    assert result["quality"]["signals"]["persistence"] == {
        "attempted": 1,
        "stored": 1,
        "failed": 0,
        "atomic": True,
        "status": "pass",
    }
    assert stored[0]["drawText2"] == "Canadian Experience Class"


def test_fetch_and_store_rounds_blocks_truncated_feed_before_writes(monkeypatch):
    rounds = [
        {
            "drawNumber": "999",
            "drawDate": "2026-07-09",
            "drawName": "Canadian Experience Class",
            "drawSize": "3,000",
            "drawCRS": "510",
        }
    ]
    stored = []

    monkeypatch.setattr(
        scraper,
        "_resolve_rounds_json_url",
        lambda: "https://example.test/rounds.json",
    )
    monkeypatch.setattr(
        scraper.requests,
        "get",
        lambda url, timeout: FakeResponse(payload={"rounds": rounds}),
    )
    monkeypatch.setattr(scraper, "persist_draw_batch", stored.extend)

    with pytest.raises(RuntimeError, match="row_count_below_minimum:1<100"):
        scraper.fetch_and_store_rounds(as_of="2026-07-09")

    assert stored == []


def test_fetch_and_store_rounds_rejects_empty_payload(monkeypatch):
    monkeypatch.setattr(scraper, "_resolve_rounds_json_url", lambda: "https://example.test/rounds.json")
    monkeypatch.setattr(
        scraper.requests,
        "get",
        lambda url, timeout: FakeResponse(payload={"rounds": []}),
    )

    with pytest.raises(RuntimeError, match="did not contain any entries"):
        scraper.fetch_and_store_rounds()


def test_fetch_and_store_rounds_surfaces_atomic_persistence_failure(monkeypatch):
    rounds = [
        {
            "drawNumber": "999",
            "drawDate": "2026-07-09",
            "drawName": "Canadian Experience Class",
            "drawSize": "3,000",
            "drawCRS": "510",
        }
    ]
    monkeypatch.setattr(
        scraper,
        "_resolve_rounds_json_url",
        lambda: "https://example.test/rounds.json",
    )
    monkeypatch.setattr(
        scraper.requests,
        "get",
        lambda url, timeout: FakeResponse(payload={"rounds": rounds}),
    )

    def fail_batch(_draws):
        raise sqlite3.OperationalError("simulated write failure")

    monkeypatch.setattr(scraper, "persist_draw_batch", fail_batch)

    with pytest.raises(RuntimeError, match="Failed to persist IRCC rounds atomically"):
        scraper.fetch_and_store_rounds(as_of="2026-07-09", minimum_rows=1)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (5000, 5000),
        ("5,000", 5000),
        (" 420 ", 420),
        ("", None),
        (None, None),
        ("5,00", None),
        ("-1", None),
        (-1, None),
        ("+420", None),
        ("unknown", None),
        (5.5, None),
        (True, None),
    ],
)
def test_safe_int_accepts_only_supported_ircc_integer_formats(value, expected):
    assert scraper._safe_int(value) == expected


def test_insert_draw_data_replaces_existing_draw(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    scraper.initialize_db()

    first = {
        "drawNumber": "999",
        "drawDate": "2026-07-09",
        "drawName": "Canadian Experience Class",
        "drawSize": "3000",
        "drawCRS": "510",
        "drawText2": "Canadian Experience Class, Provincial Nominee Program",
    }
    replacement = {**first, "drawSize": "5,000", "drawCRS": "508"}

    scraper.insert_draw_data(first)
    scraper.insert_draw_data(replacement)

    with sqlite3.connect(tmp_path / "data" / "express_entry.db") as connection:
        row = connection.execute(
            "SELECT draw_number, invitations, crs_cut_off, programs FROM express_entry"
        ).fetchone()
        count = connection.execute("SELECT COUNT(*) FROM express_entry").fetchone()[0]

    assert count == 1
    assert row == (
        "999",
        5000,
        508,
        json.dumps(["Canadian Experience Class", "Provincial Nominee Program"]),
    )


def test_persist_draw_batch_rolls_back_every_draw_on_failure(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    original = {
        "drawNumber": "999",
        "drawDate": "2026-07-09",
        "drawName": "Canadian Experience Class",
        "drawSize": "3,000",
        "drawCRS": "510",
        "drawText2": "Canadian Experience Class",
    }
    replacement = {**original, "drawSize": "5,000"}
    malformed = {key: value for key, value in original.items() if key != "drawNumber"}
    scraper.insert_draw_data(original)

    with pytest.raises(KeyError, match="drawNumber"):
        scraper.persist_draw_batch([replacement, malformed])

    with sqlite3.connect(tmp_path / "data" / "express_entry.db") as connection:
        rows = connection.execute(
            "SELECT draw_number, invitations FROM express_entry"
        ).fetchall()

    assert rows == [("999", 3000)]
