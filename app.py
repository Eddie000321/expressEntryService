from flask import Flask, render_template, request, jsonify
import hmac
import sqlite3
from datetime import datetime
import re
import os
from scraper import (
    fetch_and_store_rounds,
    initialize_db,
    read_data_provenance,
    scrape_canada_news,
)


app = Flask(__name__)

VERSION_PATTERN = re.compile(r'^(?P<base>.*?)(?:\s*\((?P<version>Version\s*\d+)\))?$')


def split_program_version(raw_name):
    if not raw_name:
        return raw_name, None
    match = VERSION_PATTERN.match(raw_name.strip())
    if match and match.group('version'):
        return match.group('base').strip(), match.group('version').strip()
    return raw_name.strip(), None


def parse_iso_date(value):
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

def get_db_connection():
    initialize_db()
    conn = sqlite3.connect('data/express_entry.db')
    conn.row_factory = sqlite3.Row
    return conn


@app.context_processor
def inject_data_provenance():
    return {"data_provenance": read_data_provenance()}

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

    min_dt = parse_iso_date(min_date)
    max_dt = parse_iso_date(max_date)
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

    start_dt = parse_iso_date(raw_start) or min_dt
    end_dt = parse_iso_date(raw_end) or max_dt

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
    program_bases = set()
    for row in score_data:
        parsed_date = parse_iso_date(row['draw_date'])
        draw_date = parsed_date.isoformat() if parsed_date else str(row['draw_date'])
        base_name, version_tag = split_program_version(row['draw_name'])
        program_bases.add(base_name)
        scores_by_date.setdefault(draw_date, {})[base_name] = {
            'score': row['crs_cut_off'],
            'version': version_tag,
            'original_name': row['draw_name']
        }

    ordered_dates = sorted(scores_by_date.keys())
    program_series = []
    for program in sorted(program_bases):
        series_scores = []
        series_versions = []
        series_labels = []
        for date in ordered_dates:
            entry = scores_by_date.get(date, {}).get(program)
            if entry:
                series_scores.append(entry['score'])
                series_versions.append(entry['version'])
                series_labels.append(entry['original_name'])
            else:
                series_scores.append(None)
                series_versions.append(None)
                series_labels.append(None)
        program_series.append({
            'name': program,
            'scores': series_scores,
            'versions': series_versions,
            'labels': series_labels
        })

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


@app.route('/my-score')
def my_score():
    user_score = request.args.get('score', type=int)
    selected_program = request.args.get('program') or 'ALL'

    conn = get_db_connection()
    rows = conn.execute('''
        SELECT
            date(draw_date) as draw_date,
            draw_name,
            crs_cut_off,
            invitations
        FROM express_entry
        ORDER BY draw_date
    ''').fetchall()
    conn.close()

    processed_rows = []
    program_set = set()
    for row in rows:
        base_name, version_tag = split_program_version(row['draw_name'])
        if not base_name:
            continue
        program_set.add(base_name)
        processed_rows.append({
            'date': row['draw_date'],
            'base_name': base_name,
            'version': version_tag,
            'full_name': row['draw_name'],
            'crs': row['crs_cut_off'],
            'invitations': row['invitations']
        })

    program_options = sorted(program_set)
    if selected_program != 'ALL' and selected_program not in program_set:
        selected_program = 'ALL'

    if selected_program == 'ALL':
        filtered_rows = processed_rows
    else:
        filtered_rows = [row for row in processed_rows if row['base_name'] == selected_program]

    chart_data = None
    summary = None

    if filtered_rows:
        dates = [row['date'] for row in filtered_rows]
        cutoffs = [row['crs'] for row in filtered_rows]
        labels = [row['full_name'] for row in filtered_rows]
        versions = [row['version'] for row in filtered_rows]

        if user_score is not None:
            statuses = []
            for row in filtered_rows:
                if row['crs'] is None:
                    statuses.append('missing')
                elif user_score >= row['crs']:
                    statuses.append('win')
                else:
                    statuses.append('miss')
        else:
            statuses = ['neutral'] * len(filtered_rows)

        chart_data = {
            'dates': dates,
            'cutoffs': cutoffs,
            'statuses': statuses,
            'labels': labels,
            'versions': versions,
            'score': user_score,
            'program': selected_program
        }

        completed_draws = [row for row in filtered_rows if row['crs'] is not None]
        if user_score is not None and completed_draws:
            eligible = [row for row in completed_draws if user_score >= row['crs']]
            not_met = [row for row in completed_draws if user_score < row['crs']]

            best_match = eligible[-1] if eligible else None
            next_target = None

            if best_match:
                try:
                    best_idx = filtered_rows.index(best_match)
                except ValueError:
                    best_idx = -1
                for row in filtered_rows[best_idx + 1:]:
                    if row['crs'] is not None and user_score < row['crs']:
                        next_target = row
                        break
            if next_target is None and not_met:
                next_target = not_met[-1]

            summary = {
                'eligible_count': len(eligible),
                'total_draws': len(completed_draws),
                'coverage_pct': round(len(eligible) / len(completed_draws) * 100, 1) if completed_draws else 0,
                'best_match': best_match,
                'next_target': next_target
            }

    else:
        chart_data = {
            'dates': [],
            'cutoffs': [],
            'statuses': [],
            'labels': [],
            'versions': [],
            'score': user_score,
            'program': selected_program
        }

    return render_template(
        'my_score.html',
        program_options=program_options,
        selected_program=selected_program,
        user_score=user_score,
        chart_data=chart_data,
        summary=summary
    )


@app.route('/news')
def news():
    news_items = scrape_canada_news()
    return render_template('news.html', news_items=news_items)


@app.route('/admin/update', methods=['POST'])
def admin_update():
    expected_token = os.environ.get('ADMIN_UPDATE_TOKEN')
    if not expected_token:
        return jsonify({'error': 'Update token not configured'}), 503

    provided_token = request.headers.get('X-Admin-Token')
    if not provided_token or not hmac.compare_digest(provided_token, expected_token):
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        result = fetch_and_store_rounds()
        return jsonify({'status': 'ok', **result})
    except Exception:
        app.logger.exception("IRCC draw refresh failed")
        return jsonify({'error': 'Data refresh failed'}), 500


if __name__ == '__main__':
    app.run(debug=True)
