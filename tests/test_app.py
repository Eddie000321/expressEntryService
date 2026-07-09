import sqlite3

import pytest

import app as dashboard
import scraper


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    scraper.initialize_db(bootstrap=False)
    monkeypatch.setattr(dashboard, "initialize_db", lambda: None)
    monkeypatch.setattr(dashboard, "read_data_provenance", lambda: None)
    dashboard.app.config.update(TESTING=True)
    return dashboard.app.test_client()


@pytest.mark.parametrize(
    ("raw_name", "expected"),
    [
        ("Canadian Experience Class (Version 2)", ("Canadian Experience Class", "Version 2")),
        ("Provincial Nominee Program", ("Provincial Nominee Program", None)),
        (None, (None, None)),
    ],
)
def test_split_program_version(raw_name, expected):
    assert dashboard.split_program_version(raw_name) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-07-09", "2026-07-09"),
        ("2026-07-09T15:30:00Z", "2026-07-09"),
        ("not-a-date", None),
        (None, None),
    ],
)
def test_parse_iso_date(value, expected):
    parsed = dashboard.parse_iso_date(value)
    assert (parsed.isoformat() if parsed else None) == expected


@pytest.mark.parametrize("path", ["/", "/summary", "/score-changes", "/my-score"])
def test_dashboard_routes_render_with_an_empty_database(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert b"Informational data only" in response.data


def test_home_initializes_schema_on_clean_checkout(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    dashboard.app.config.update(TESTING=True)

    response = dashboard.app.test_client().get("/")

    assert response.status_code == 200
    assert (tmp_path / "data" / "express_entry.db").is_file()
    assert b"Historical data through 2026-07-09" in response.data
    assert b"426 official IRCC draw records" in response.data
    assert b"Express Entry: Rounds of invitations" in response.data
    assert b"ee_rounds_123_en.json" in response.data
    assert b"not affiliated with or endorsed by the Government of Canada" in response.data
    with sqlite3.connect(tmp_path / "data" / "express_entry.db") as connection:
        assert connection.execute("SELECT COUNT(*) FROM express_entry").fetchone()[0] == 426
        assert connection.execute(
            "SELECT origin, as_of_date, row_count FROM data_provenance"
        ).fetchone() == ("bundled_ircc_snapshot", "2026-07-09", 426)


def test_admin_update_requires_configured_token(client, monkeypatch):
    monkeypatch.delenv("ADMIN_UPDATE_TOKEN", raising=False)
    response = client.post("/admin/update")
    assert response.status_code == 503
    assert response.get_json() == {"error": "Update token not configured"}


def test_admin_update_rejects_wrong_token(client, monkeypatch):
    monkeypatch.setenv("ADMIN_UPDATE_TOKEN", "expected")
    response = client.post("/admin/update", headers={"X-Admin-Token": "wrong"})
    assert response.status_code == 403
    assert response.get_json() == {"error": "Unauthorized"}


@pytest.mark.parametrize(
    ("path", "form"),
    [
        ("/admin/update?token=expected", None),
        ("/admin/update", {"token": "expected"}),
    ],
)
def test_admin_update_does_not_accept_token_in_url_or_form(client, monkeypatch, path, form):
    monkeypatch.setenv("ADMIN_UPDATE_TOKEN", "expected")

    response = client.post(path, data=form)

    assert response.status_code == 403
    assert response.get_json() == {"error": "Unauthorized"}


def test_admin_update_returns_fetch_summary(client, monkeypatch):
    monkeypatch.setenv("ADMIN_UPDATE_TOKEN", "expected")
    monkeypatch.setattr(
        dashboard,
        "fetch_and_store_rounds",
        lambda: {"json_url": "https://example.test/rounds.json", "total_rounds": 2, "stored": 2},
    )

    response = client.post("/admin/update", headers={"X-Admin-Token": "expected"})

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "json_url": "https://example.test/rounds.json",
        "total_rounds": 2,
        "stored": 2,
    }


def test_admin_update_returns_generic_error_when_atomic_refresh_fails(client, monkeypatch):
    monkeypatch.setenv("ADMIN_UPDATE_TOKEN", "expected")

    def fail_refresh():
        raise RuntimeError("sensitive persistence detail")

    monkeypatch.setattr(dashboard, "fetch_and_store_rounds", fail_refresh)

    response = client.post("/admin/update", headers={"X-Admin-Token": "expected"})

    assert response.status_code == 500
    assert response.get_json() == {"error": "Data refresh failed"}
    assert b"sensitive persistence detail" not in response.data
