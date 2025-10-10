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
- **Personal Benchmarking**: Enter your CRS score to see where you land against historic cut-offs, with per-program filtering.

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
Run the JSON-based fetch helper shipped in `scraper.py`:
```bash
python -c "from scraper import initialize_db, fetch_and_store_rounds; initialize_db(); print(fetch_and_store_rounds())"
```
This routine resolves IRCC’s latest `ee_rounds_*.json` endpoint, loads every draw, and persists them via `insert_draw_data()`. See `docs/data-fetching.md` for background on the migration from legacy HTML scraping to the JSON workflow.

#### Remote refresh (for hosted environments)
Set an `ADMIN_UPDATE_TOKEN` environment variable (Render: Dashboard → Environment → Add Variable). Then trigger a refresh with:
```bash
curl -X POST https://<your-service>.onrender.com/admin/update \
     -H "X-Admin-Token: $ADMIN_UPDATE_TOKEN"
```
The endpoint returns the JSON fetch summary when the token matches. Rotate the token periodically and avoid embedding it in client-side code.

## Routes
- `/` – Recent draw table
- `/summary` – Aggregated metrics, cut-off trends, and cumulative charts
- `/score-changes` – Filterable program-specific cut-off history
- `/my-score` – Compare your CRS score against historic cut-offs
- `/news` – Latest IRCC newsroom articles
- `/admin/update` – (POST, token-protected) Refreshes draw data from IRCC

## Visualizations
- **Yearly Draws (Bar)** – Total draws per year
- **Monthly Draw Distribution (Grouped Bar)** – Monthly counts split by year
- **Program Distribution (Stacked Bar)** – Draw count by program and year
- **Program Mix Share (Area)** – Share of invitations per program by year
- **Cut-off & Invitations Trend (Combo)** – CRS cut-offs, moving average, and invitations on one chart
- **Cumulative Draw Momentum (Dual Line)** – Cumulative draws vs. cumulative invitations
- **Score Changes (Line)** – Program-by-program CRS timeline with date filters
- **Personal Score Benchmark (Combo)** – Historic cut-offs with your score overlay and version-aware colouring

## Project Structure
```
expressEntryService/
├── app.py                 # Flask routes and aggregation logic
├── scraper.py             # DB init, JSON fetch, and draw ingestion helpers
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
├── docs/
│   └── data-fetching.md   # Notes on legacy vs. JSON data collection
├── read_before_use.rtf
└── venv/                  # Optional local virtual environment
```

> **Heads-up**: `static/dashboard-preview.png` is a placeholder for a dashboard screenshot. Run the app, take a snapshot, and drop it in that path to dress up the README.

## License
No explicit license is bundled. If you plan to redistribute, add a LICENSE file that reflects your usage terms.
