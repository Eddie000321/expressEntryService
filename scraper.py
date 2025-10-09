import sqlite3
import json
import requests
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
    
    conn.commit()
    conn.close()

def insert_draw_data(draw_data):
    conn = sqlite3.connect('data/express_entry.db')
    cursor = conn.cursor()
    
    raw_programs = draw_data.get('drawText2') or ''
    program_list = [prog.strip() for prog in raw_programs.split(',') if prog.strip()]
    programs = json.dumps(program_list)

    def _safe_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    
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
