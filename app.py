from flask import Flask, render_template
import sqlite3

app = Flask(__name__)

# 데이터베이스에서 데이터 가져오기 함수
def fetch_data():
    conn = sqlite3.connect('data/express_entry.db')
    cursor = conn.cursor()
    cursor.execute('SELECT draw_number, draw_date, draw_name, invitations, crs_cut_off FROM express_entry ORDER BY draw_date DESC')
    rows = cursor.fetchall()
    conn.close()
    return rows

# 메인 페이지
@app.route('/')
def index():
    data = fetch_data()  # 데이터베이스에서 데이터 가져오기
    return render_template('index.html', data=data)

if __name__ == '__main__':
    app.run(debug=True)
