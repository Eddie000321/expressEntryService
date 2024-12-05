import requests
import sqlite3

# API URL
API_URL = "https://www.canada.ca/content/dam/ircc/documents/json/ee_rounds_123_en.json"

# draw_number를 정렬하기 위한 함수
def parse_draw_number(draw_number):
    """
    draw_number를 숫자와 알파벳 부분으로 분리하여 정렬 가능하도록 반환.
    예: "91b" -> (91, "b")
    """
    numeric_part = ''.join(filter(str.isdigit, draw_number))  # 숫자 부분 추출
    alpha_part = ''.join(filter(str.isalpha, draw_number))   # 알파벳 부분 추출
    return int(numeric_part), alpha_part

# 데이터베이스 초기화 함수
def initialize_db():
    conn = sqlite3.connect('data/express_entry.db')
    cursor = conn.cursor()
    # 기존 테이블 삭제 후 다시 생성
    cursor.execute('DROP TABLE IF EXISTS express_entry')
    cursor.execute('''
        CREATE TABLE express_entry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw_number TEXT,
            draw_date TEXT,
            draw_name TEXT,
            invitations INTEGER,
            crs_cut_off INTEGER
        )
    ''')
    conn.commit()
    conn.close()

# API 호출 및 데이터 저장 함수
def fetch_and_store_data():
    # API 호출
    response = requests.get(API_URL)
    if response.status_code != 200:
        print("Failed to fetch data from API.")
        return

    # JSON 데이터 파싱
    data = response.json()
    rounds = data.get('rounds', [])

    # 정렬 기준 적용
    sorted_rounds = sorted(rounds, key=lambda draw: parse_draw_number(draw['drawNumber']))

    # 데이터베이스 저장
    conn = sqlite3.connect('data/express_entry.db')
    cursor = conn.cursor()

    for draw in sorted_rounds:
        try:
            draw_number, alpha_part = parse_draw_number(draw['drawNumber'])
        except ValueError:
            print(f"Invalid drawNumber: {draw['drawNumber']}")
            continue

        draw_date = draw['drawDate']
        draw_name = draw['drawName']
        invitations = int(draw['drawSize'].replace(',', ''))
        crs_cut_off = int(draw['drawCRS'])

        cursor.execute('''
            INSERT INTO express_entry (draw_number, draw_date, draw_name, invitations, crs_cut_off)
            VALUES (?, ?, ?, ?, ?)
        ''', (f"{draw_number}{alpha_part}", draw_date, draw_name, invitations, crs_cut_off))

    conn.commit()
    conn.close()
    print("Data successfully fetched and stored.")

if __name__ == '__main__':
    initialize_db()
    fetch_and_store_data()
