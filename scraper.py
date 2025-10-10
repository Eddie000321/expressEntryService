import sqlite3
import json
import requests
from html import unescape
from urllib.parse import urljoin
from bs4 import BeautifulSoup



def initialize_db():
    conn = sqlite3.connect('data/express_entry.db')
    cursor = conn.cursor()
    
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

    # Ensure schema stays in sync with latest code expectations
    cursor.execute("PRAGMA table_info(express_entry)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if 'programs' not in existing_columns:
        cursor.execute("ALTER TABLE express_entry ADD COLUMN programs TEXT")
    if 'invitations' not in existing_columns:
        cursor.execute("ALTER TABLE express_entry ADD COLUMN invitations INTEGER")
    if 'crs_cut_off' not in existing_columns:
        cursor.execute("ALTER TABLE express_entry ADD COLUMN crs_cut_off INTEGER")
    
    conn.commit()
    conn.close()


BASE_URL = "https://www.canada.ca"
ROUNDS_PAGE = (
    "/en/immigration-refugees-citizenship/"
    "services/immigrate-canada/express-entry/rounds-invitations.html"
)


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


def fetch_and_store_rounds():
    """Fetch the latest Express Entry rounds JSON and store records in SQLite."""
    json_url = _resolve_rounds_json_url()
    response = requests.get(json_url, timeout=30)
    response.raise_for_status()

    payload = response.json()
    rounds = payload.get("rounds", [])
    if not rounds:
        raise RuntimeError("Express Entry rounds payload did not contain any entries.")

    processed = 0
    for draw in rounds:
        # Ensure programs/program types map into expected field
        draw.setdefault("drawText2", draw.get("drawName", ""))
        try:
            insert_draw_data(draw)
            processed += 1
        except Exception as exc:
            # Continue processing but surface problematic entries
            print(
                f"[WARN] Failed to persist draw #{draw.get('drawNumber')}: {exc}",
                flush=True,
            )

    return {"json_url": json_url, "total_rounds": len(rounds), "stored": processed}

def insert_draw_data(draw_data):
    conn = sqlite3.connect('data/express_entry.db')
    cursor = conn.cursor()
    
    raw_programs = draw_data.get('drawText2') or ''
    program_list = [prog.strip() for prog in raw_programs.split(',') if prog.strip()]
    programs = json.dumps(program_list)

    def _safe_int(value):
        try:
            if isinstance(value, str):
                cleaned = value.replace(',', '').strip()
                if cleaned == '':
                    return None
                return int(cleaned)
            return int(value)
        except (TypeError, ValueError):
            return None
    
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
    
    conn.commit()
    conn.close()

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
