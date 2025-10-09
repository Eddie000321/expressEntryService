![Dashboard Preview](static/dashboard-preview.png)

# Express Entry Dashboard

Express Entry Dashboard is a Flask-based analytics app that ingests draws from Immigration, Refugees and Citizenship Canada (IRCC) and turns them into digestible insights for Express Entry applicants. Track recent draws, program mix, CRS cut-off swings, and cumulative progress in one place.

## Features
- **Latest Draws**: View the 10 most recent draws with draw number, date, program, invitations issued, and CRS cut-off.
- **Yearly & Monthly Stats**: Compare the cadence of draws across years and months to spot seasonal patterns.
- **Program Distribution**: Examine draw counts and invitation share by program each year.
- **Cut-off Trends**: Follow CRS cut-offs, a 5-draw moving average, and invitation volume on a dual-axis chart.
- **Cumulative Momentum**: Watch cumulative draw count and total invitations grow throughout the year.
- **Immigration News**: Read the latest IRCC headlines scraped directly from Canada.ca.

## Tech Stack
- **Backend**: Python, Flask, SQLite
- **Frontend**: HTML, CSS, Chart.js
- **Data Sources**: IRCC Express Entry API, Canada.ca News (HTTP scraping)

## Getting Started

### Prerequisites
- Python 3.10+
- Virtual environment recommended (e.g., `python3 -m venv venv`)

### Installation
```bash
git clone <your-repo-url>
cd expressEntryService
python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# (Optional) Initialize the SQLite schema on first run
python -c "from scraper import initialize_db; initialize_db()"

# Run the Flask app
export FLASK_APP=app.py    # On Windows PowerShell: $env:FLASK_APP = 'app.py'
flask run
```
Browse to `http://127.0.0.1:5000` to explore the dashboard.

### Updating Data
The repository ships with helper functions for database setup and draw insertion (`scraper.py`). Implement the upstream IRCC API call, then feed records into `insert_draw_data()` to refresh `data/express_entry.db`.

## Routes
- `/` – Recent draw table
- `/summary` – Aggregated metrics, cut-off trends, and cumulative charts
- `/score-changes` – Filterable program-specific cut-off history
- `/news` – Latest IRCC newsroom articles

## Visualizations
- **Yearly Draws (Bar)** – Total draws per year
- **Monthly Draw Distribution (Grouped Bar)** – Monthly counts split by year
- **Program Distribution (Stacked Bar)** – Draw count by program and year
- **Program Mix Share (Area)** – Share of invitations per program by year
- **Cut-off & Invitations Trend (Combo)** – CRS cut-offs, moving average, and invitations on one chart
- **Cumulative Draw Momentum (Dual Line)** – Cumulative draws vs. cumulative invitations
- **Score Changes (Line)** – Program-by-program CRS timeline with date filters

## Project Structure
```
expressEntryService/
├── app.py                 # Flask routes and aggregation logic
├── scraper.py             # DB init and draw ingestion helpers
├── requirements.txt       # Python dependencies
├── data/
│   └── express_entry.db   # SQLite database (created after initialization)
├── static/
│   ├── charts.js          # Chart.js helper functions
│   └── style.css          # Global styles
├── templates/
│   ├── index.html         # Recent draw page
│   ├── summary.html       # Analytics dashboard
│   ├── score_changes.html # Program cut-off trends
│   └── news.html          # News feed
├── read_before_use.rtf
└── venv/                  # Optional local virtual environment
```

> **Heads-up**: `static/dashboard-preview.png` is a placeholder for a dashboard screenshot. Run the app, take a snapshot, and drop it in that path to dress up the README.

## License
No explicit license is bundled. If you plan to redistribute, add a LICENSE file that reflects your usage terms.
