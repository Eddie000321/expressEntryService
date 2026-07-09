import sqlite3
import json
import requests
from hashlib import sha256
from html import unescape
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from data_quality import (
    build_rounds_quality_report,
    parse_ircc_int,
    require_ingestion_quality,
)

DB_PATH = Path("data/express_entry.db")
BASE_URL = "https://www.canada.ca"
ROUNDS_PAGE = (
    "/en/immigration-refugees-citizenship/"
    "services/immigrate-canada/express-entry/rounds-invitations.html"
)
ROUNDS_PAGE_URL = urljoin(BASE_URL, ROUNDS_PAGE)
IRCC_ROUNDS_TITLE = "Express Entry: Rounds of invitations"
BUNDLED_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent
    / "data"
    / "bootstrap"
    / "ircc-ee-rounds-2026-07-09.json"
)
BUNDLED_SNAPSHOT_AS_OF = "2026-07-09"
BUNDLED_SNAPSHOT_MINIMUM_ROWS = 100
BUNDLED_SNAPSHOT_SHA256 = (
    "db435d0d3b45e23149111851bfd74201e74e42cd6a0ffb83d6aac6215d74f5b2"
)
BUNDLED_SNAPSHOT_SOURCE_URL = (
    "https://www.canada.ca/content/dam/ircc/documents/json/ee_rounds_123_en.json"
)


def _ensure_database_schema(connection):
    cursor = connection.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS express_entry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw_number TEXT,
            draw_date DATE,
            draw_name TEXT,
            invitations INTEGER,
            crs_cut_off INTEGER,
            programs TEXT
        )
    ''')

    cursor.execute("PRAGMA table_info(express_entry)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if 'programs' not in existing_columns:
        cursor.execute("ALTER TABLE express_entry ADD COLUMN programs TEXT")
    if 'invitations' not in existing_columns:
        cursor.execute("ALTER TABLE express_entry ADD COLUMN invitations INTEGER")
    if 'crs_cut_off' not in existing_columns:
        cursor.execute("ALTER TABLE express_entry ADD COLUMN crs_cut_off INTEGER")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS data_provenance (
            singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
            origin TEXT NOT NULL,
            source_title TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source_page_url TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            row_count INTEGER NOT NULL CHECK (row_count >= 0),
            source_sha256 TEXT
        )
    ''')


def _normalize_rounds(rounds):
    normalized_rounds = []
    for draw in rounds:
        normalized = dict(draw)
        normalized.setdefault("drawText2", normalized.get("drawName", ""))
        normalized_rounds.append(normalized)
    return normalized_rounds


def _load_bundled_snapshot(
    snapshot_path,
    *,
    expected_sha256,
    as_of,
    minimum_rows,
):
    raw_snapshot = Path(snapshot_path).read_bytes()
    actual_sha256 = sha256(raw_snapshot).hexdigest()
    if expected_sha256 and actual_sha256 != expected_sha256:
        raise RuntimeError(
            "Bundled IRCC snapshot checksum did not match its recorded provenance."
        )

    payload = json.loads(raw_snapshot)
    rounds = payload.get("rounds", []) if isinstance(payload, dict) else []
    report = build_rounds_quality_report(
        rounds,
        as_of=as_of,
        minimum_rows=minimum_rows,
    )
    require_ingestion_quality(report)
    return _normalize_rounds(rounds), report, actual_sha256


def _write_data_provenance(cursor, provenance):
    cursor.execute(
        '''
        INSERT OR REPLACE INTO data_provenance (
            singleton,
            origin,
            source_title,
            source_url,
            source_page_url,
            as_of_date,
            row_count,
            source_sha256
        )
        VALUES (1, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            provenance["origin"],
            provenance["source_title"],
            provenance["source_url"],
            provenance["source_page_url"],
            provenance["as_of_date"],
            provenance["row_count"],
            provenance.get("source_sha256"),
        ),
    )


def bootstrap_database_if_empty(
    connection,
    *,
    snapshot_path=BUNDLED_SNAPSHOT_PATH,
    snapshot_sha256=BUNDLED_SNAPSHOT_SHA256,
    snapshot_as_of=BUNDLED_SNAPSHOT_AS_OF,
    minimum_rows=BUNDLED_SNAPSHOT_MINIMUM_ROWS,
):
    """Load the validated bundled snapshot once, without replacing existing rows."""
    existing_rows = connection.execute(
        "SELECT COUNT(*) FROM express_entry"
    ).fetchone()[0]
    if existing_rows:
        return {
            "status": "skipped",
            "reason": "database_not_empty",
            "row_count": existing_rows,
        }

    rounds, quality, actual_sha256 = _load_bundled_snapshot(
        snapshot_path,
        expected_sha256=snapshot_sha256,
        as_of=snapshot_as_of,
        minimum_rows=minimum_rows,
    )

    connection.commit()
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing_rows = connection.execute(
            "SELECT COUNT(*) FROM express_entry"
        ).fetchone()[0]
        if existing_rows:
            connection.commit()
            return {
                "status": "skipped",
                "reason": "database_populated_concurrently",
                "row_count": existing_rows,
            }

        cursor = connection.cursor()
        for draw in rounds:
            _insert_draw_data(cursor, draw)
        _write_data_provenance(
            cursor,
            {
                "origin": "bundled_ircc_snapshot",
                "source_title": IRCC_ROUNDS_TITLE,
                "source_url": BUNDLED_SNAPSHOT_SOURCE_URL,
                "source_page_url": ROUNDS_PAGE_URL,
                "as_of_date": snapshot_as_of,
                "row_count": len(rounds),
                "source_sha256": actual_sha256,
            },
        )
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()

    return {
        "status": "loaded",
        "origin": "bundled_ircc_snapshot",
        "row_count": len(rounds),
        "as_of_date": snapshot_as_of,
        "source_sha256": actual_sha256,
        "quality": quality,
    }


def initialize_db(
    *,
    bootstrap=True,
    snapshot_path=BUNDLED_SNAPSHOT_PATH,
    snapshot_sha256=BUNDLED_SNAPSHOT_SHA256,
    snapshot_as_of=BUNDLED_SNAPSHOT_AS_OF,
    minimum_rows=BUNDLED_SNAPSHOT_MINIMUM_ROWS,
):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as connection:
        _ensure_database_schema(connection)
        connection.commit()
        if not bootstrap:
            return {"status": "disabled"}
        return bootstrap_database_if_empty(
            connection,
            snapshot_path=snapshot_path,
            snapshot_sha256=snapshot_sha256,
            snapshot_as_of=snapshot_as_of,
            minimum_rows=minimum_rows,
        )


def read_data_provenance():
    """Return the origin and explicit freshness label for the current draw data."""
    initialize_db()
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            '''
            SELECT
                origin,
                source_title,
                source_url,
                source_page_url,
                as_of_date,
                row_count,
                source_sha256
            FROM data_provenance
            WHERE singleton = 1
            '''
        ).fetchone()
        if row is not None:
            return dict(row)

        count, latest_date = connection.execute(
            "SELECT COUNT(*), MAX(date(draw_date)) FROM express_entry"
        ).fetchone()
        if not count:
            return None
        return {
            "origin": "existing_database",
            "source_title": IRCC_ROUNDS_TITLE,
            "source_url": ROUNDS_PAGE_URL,
            "source_page_url": ROUNDS_PAGE_URL,
            "as_of_date": latest_date,
            "row_count": count,
            "source_sha256": None,
        }

# Compatibility alias for existing callers and parser-focused tests.
_safe_int = parse_ircc_int


def _resolve_rounds_json_url():
    """Discover the latest rounds JSON endpoint from the IRCC page."""
    response = requests.get(urljoin(BASE_URL, ROUNDS_PAGE), timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup.select("[data-wb-json]"):
        raw_config = element.get("data-wb-json")
        if not raw_config:
            continue
        try:
            data_cfg = json.loads(unescape(raw_config))
        except json.JSONDecodeError:
            continue
        url = data_cfg.get("url", "")
        if "ee_rounds" in url:
            return urljoin(BASE_URL, url.split("#", 1)[0])

    raise RuntimeError("Could not locate Express Entry rounds JSON configuration on IRCC page.")


def fetch_and_store_rounds(*, as_of=None, minimum_rows=100):
    """Fetch, quality-gate, and store the latest Express Entry rounds JSON."""
    json_url = _resolve_rounds_json_url()
    response = requests.get(json_url, timeout=30)
    response.raise_for_status()

    payload = response.json()
    rounds = payload.get("rounds", [])
    if not rounds:
        raise RuntimeError("Express Entry rounds payload did not contain any entries.")

    quality = build_rounds_quality_report(
        rounds,
        as_of=as_of,
        minimum_rows=minimum_rows,
    )
    require_ingestion_quality(quality)

    normalized_rounds = _normalize_rounds(rounds)
    latest_date = quality["signals"]["freshness"]["latest_draw_date"]

    try:
        persist_draw_batch(
            normalized_rounds,
            provenance={
                "origin": "live_ircc_refresh",
                "source_title": IRCC_ROUNDS_TITLE,
                "source_url": json_url,
                "source_page_url": ROUNDS_PAGE_URL,
                "as_of_date": latest_date,
                "row_count": len(rounds),
                "source_sha256": None,
            },
        )
    except Exception as exc:
        raise RuntimeError("Failed to persist IRCC rounds atomically.") from exc

    quality["signals"]["persistence"] = {
        "attempted": len(rounds),
        "stored": len(rounds),
        "failed": 0,
        "atomic": True,
        "status": "pass",
    }

    return {
        "json_url": json_url,
        "total_rounds": len(rounds),
        "stored": len(rounds),
        "quality": quality,
    }


def _insert_draw_data(cursor, draw_data):
    raw_programs = draw_data.get('drawText2') or ''
    program_list = [prog.strip() for prog in raw_programs.split(',') if prog.strip()]
    programs = json.dumps(program_list)

    cursor.execute('DELETE FROM express_entry WHERE draw_number = ?', (draw_data['drawNumber'],))
    
    cursor.execute('''
        INSERT OR REPLACE INTO express_entry 
        (draw_number, draw_date, draw_name, invitations, crs_cut_off, programs)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        draw_data['drawNumber'],
        draw_data['drawDate'],
        draw_data['drawName'],
        _safe_int(draw_data.get('drawSize')),
        _safe_int(draw_data.get('drawCRS')),
        programs
    ))


def persist_draw_batch(draws, *, provenance=None):
    """Persist one validated payload in a single all-or-nothing transaction."""
    initialize_db(bootstrap=False)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        for draw in draws:
            _insert_draw_data(cursor, draw)
        if provenance is not None:
            _write_data_provenance(cursor, provenance)


def insert_draw_data(draw_data):
    """Persist one draw transactionally for compatibility with existing callers."""
    persist_draw_batch([draw_data])

def scrape_canada_news():
    url = "https://www.canada.ca/en/immigration-refugees-citizenship/news.html"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    news_items = []
    main_content = soup.find('main')
    if not main_content:
        return news_items  # Return empty list if main content is not found
    
    for item in main_content.find_all('article'):
        title = item.find('h3').text.strip() if item.find('h3') else 'No Title'
        date = item.find('time')['datetime'] if item.find('time') else 'No Date'
        link = item.find('a')['href'] if item.find('a') else '#'
        news_items.append({
            'title': title,
            'date': date,
            'link': link
        })
    
    return news_items
