from flask import Flask, render_template, request
import sqlite3
from datetime import datetime
from scraper import scrape_canada_news


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

    # Program invitations by year (for mix analysis)
    program_invites = conn.execute('''
        SELECT
            strftime('%Y', draw_date) as year,
            draw_name,
            SUM(invitations) as invitations
        FROM express_entry
        GROUP BY year, draw_name
        ORDER BY year, draw_name
    ''').fetchall()

    # Draw timeline for cut-off and cadence insights
    draw_timeline = conn.execute('''
        SELECT
            date(draw_date) as draw_date,
            draw_name,
            invitations,
            crs_cut_off
        FROM express_entry
        WHERE crs_cut_off IS NOT NULL
        ORDER BY draw_date
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

    program_invite_data = {}
    for row in program_invites:
        year = row['year']
        program_invite_data.setdefault(year, {})
        program_invite_data[year][row['draw_name']] = row['invitations']

    cutoff_series = []
    cumulative_series = []
    moving_window = []
    cumulative_draws = 0
    cumulative_invites = 0
    timeline_years = set()

    for row in draw_timeline:
        draw_date = row['draw_date']
        cutoff = row['crs_cut_off']
        invitations = row['invitations'] or 0
        year = draw_date[:4] if draw_date else None
        cumulative_draws += 1
        cumulative_invites += invitations
        moving_window.append(cutoff)
        if len(moving_window) > 5:
            moving_window.pop(0)
        rolling_avg = round(sum(moving_window) / len(moving_window), 2) if moving_window else None
        if year:
            timeline_years.add(year)
        cutoff_series.append({
            'date': draw_date,
            'year': year,
            'crs': cutoff,
            'draw_name': row['draw_name'],
            'invitations': invitations,
            'rolling_avg': rolling_avg
        })
        cumulative_series.append({
            'date': draw_date,
            'year': year,
            'draws': cumulative_draws,
            'invitations': cumulative_invites
        })
    
    timeline_years = sorted(timeline_years)
    
    return render_template('summary.html',
                         yearly_draws=yearly_draws,
                         monthly_data=monthly_data,
                         program_data=program_data,
                         years=years,
                         program_invite_data=program_invite_data,
                         cutoff_series=cutoff_series,
                         cumulative_series=cumulative_series,
                         timeline_years=timeline_years)

@app.route('/score-changes')
def score_changes():
    conn = get_db_connection()
    
    # Get min and max dates from database
    date_range = conn.execute('''
        SELECT 
            MIN(draw_date) as min_date,
            MAX(draw_date) as max_date
        FROM express_entry
    ''').fetchone()
    
    min_date = date_range['min_date']
    max_date = date_range['max_date']
    if not min_date or not max_date:
        conn.close()
        empty_payload = {'dates': [], 'programs': []}
        return render_template(
            'score_changes.html',
            min_date=None,
            max_date=None,
            start_date=None,
            end_date=None,
            score_data=empty_payload
        )

    raw_start = request.args.get('start')
    raw_end = request.args.get('end')

    def _parse_iso_date(value):
        if not value:
            return None
        cleaned = value.strip().replace('Z', '')
        try:
            return datetime.fromisoformat(cleaned).date()
        except ValueError:
            pass
        try:
            base = cleaned.split(' ')[0][:10]
            return datetime.strptime(base, '%Y-%m-%d').date()
        except (ValueError, IndexError):
            return None

    min_dt = _parse_iso_date(min_date)
    max_dt = _parse_iso_date(max_date)
    # Safety check in case stored dates are not strict ISO format
    if not min_dt or not max_dt:
        conn.close()
        empty_payload = {'dates': [], 'programs': []}
        return render_template(
            'score_changes.html',
            min_date=min_date,
            max_date=max_date,
            start_date=min_date,
            end_date=max_date,
            score_data=empty_payload
        )

    start_dt = _parse_iso_date(raw_start) or min_dt
    end_dt = _parse_iso_date(raw_end) or max_dt

    start_dt = max(start_dt, min_dt)
    end_dt = min(end_dt, max_dt)

    if start_dt > end_dt:
        start_dt = min_dt
        end_dt = max_dt

    sanitized_start = start_dt.isoformat()
    sanitized_end = end_dt.isoformat()
    normalized_min = min_dt.isoformat()
    normalized_max = max_dt.isoformat()
    
    # Get score data and convert Row objects to dictionaries
    score_data = conn.execute('''
        SELECT 
            draw_date,
            draw_name,
            crs_cut_off
        FROM express_entry 
        WHERE draw_date BETWEEN ? AND ?
        ORDER BY draw_date
    ''', (sanitized_start, sanitized_end)).fetchall()
    
    conn.close()

    scores_by_date = {}
    program_names = set()
    for row in score_data:
        parsed_date = _parse_iso_date(row['draw_date'])
        draw_date = parsed_date.isoformat() if parsed_date else str(row['draw_date'])
        draw_name = row['draw_name']
        program_names.add(draw_name)
        scores_by_date.setdefault(draw_date, {})[draw_name] = row['crs_cut_off']

    ordered_dates = sorted(scores_by_date.keys())
    program_series = []
    for program in sorted(program_names):
        series = [scores_by_date[date].get(program) for date in ordered_dates]
        program_series.append({'name': program, 'scores': series})

    chart_payload = {
        'dates': ordered_dates,
        'programs': program_series
    }
    
    return render_template('score_changes.html',
                         min_date=normalized_min,
                         max_date=normalized_max,
                         start_date=sanitized_start,
                         end_date=sanitized_end,
                         score_data=chart_payload)




@app.route('/news')
def news():
    news_items = scrape_canada_news()
    return render_template('news.html', news_items=news_items)


if __name__ == '__main__':
    app.run(debug=True)
