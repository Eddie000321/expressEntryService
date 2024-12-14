from flask import Flask, render_template
import sqlite3
from datetime import datetime

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('data/express_entry.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    conn = get_db_connection()
    recent_draws = conn.execute('''
        SELECT 
            draw_number,
            date(draw_date) as draw_date,
            draw_name,
            invitations,
            crs_cut_off
        FROM express_entry 
        ORDER BY draw_date DESC 
        LIMIT 10
    ''').fetchall()
    conn.close()
    return render_template('index.html', recent_draws=recent_draws)

@app.route('/summary')
def summary():
    conn = get_db_connection()
    
    # Yearly draw counts
    yearly_draws = conn.execute('''
        SELECT strftime('%Y', draw_date) as year, COUNT(*) as count
        FROM express_entry
        GROUP BY year
        ORDER BY year
    ''').fetchall()
    
    # Monthly draws by year
    monthly_draws = conn.execute('''
        SELECT 
            strftime('%m', draw_date) as month,
            strftime('%Y', draw_date) as year,
            COUNT(*) as count
        FROM express_entry
        GROUP BY month, year
        ORDER BY month, year
    ''').fetchall()
    
    # Program type counts by year
    program_types = conn.execute('''
        SELECT 
            strftime('%Y', draw_date) as year,
            draw_name,
            COUNT(*) as count
        FROM express_entry
        GROUP BY year, draw_name
        ORDER BY year, draw_name
    ''').fetchall()
    
    conn.close()
    
    years = sorted(list(set([row['year'] for row in yearly_draws])))
    months = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']
    
    monthly_data = {month: {year: 0 for year in years} for month in months}
    for row in monthly_draws:
        monthly_data[row['month']][row['year']] = row['count']
    
    program_data = {}
    for row in program_types:
        if row['year'] not in program_data:
            program_data[row['year']] = {}
        program_data[row['year']][row['draw_name']] = row['count']
    
    return render_template('summary.html',
                         yearly_draws=yearly_draws,
                         monthly_data=monthly_data,
                         program_data=program_data,
                         years=years)

@app.route('/score-changes')
def score_changes():
    return render_template('score_changes.html')

if __name__ == '__main__':
    app.run(debug=True)
