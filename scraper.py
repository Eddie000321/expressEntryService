import sqlite3
import json

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
    
    programs = json.dumps([prog.strip() for prog in draw_data['drawText2'].split(',')])
    
    cursor.execute('''
        INSERT OR REPLACE INTO express_entry 
        (draw_number, draw_date, draw_name, invitations, crs_cut_off, programs)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        draw_data['drawNumber'],
        draw_data['drawDate'],
        draw_data['drawName'],
        int(draw_data['drawSize']),
        int(draw_data['drawCRS']),
        programs
    ))
    
    conn.commit()
    conn.close()