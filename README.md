# Express Entry Dashboard

**A Flask and SQLite public-data dashboard for reviewing IRCC Express Entry
draw history, program mix, CRS cut-offs, and personal score context.**

[![Quality](https://github.com/Eddie000321/expressEntryService/actions/workflows/quality.yml/badge.svg)](https://github.com/Eddie000321/expressEntryService/actions/workflows/quality.yml)
[![Live demo](https://img.shields.io/badge/Live_Demo-Render-006f9c)](https://expressentryservice.onrender.com/)
[![Portfolio entry](https://img.shields.io/badge/Portfolio-Project_Entry-587812)](https://eddie000321.github.io/#project-express-entry-service)
![Tests](https://img.shields.io/badge/tests-61_offline-587812)
![Bootstrap](https://img.shields.io/badge/bootstrap-426_verified_records-6b5cff)

<p align="center">
  <img width="920" alt="Express Entry score comparison dashboard with historical cut-off context" src="https://github.com/user-attachments/assets/e8a946a9-f256-48c5-bc33-1e733ae5ba44" />
</p>

Express Entry Dashboard ingests public draw records from Immigration, Refugees
and Citizenship Canada (IRCC) and turns them into reviewable trends. A
checksum-pinned 426-row historical snapshot can bootstrap an empty deployment
without network access or an administrator token.

## At a glance

| Area | Evidence |
| --- | --- |
| Data | Official IRCC draw records with source attribution and through-date visibility |
| Reliability | Fail-closed schema, type, duplicate, row-count, null-rate, and freshness checks |
| Verification | 61 deterministic offline tests isolated from the live API and production database |
| Delivery | Flask, SQLite, Chart.js, and an optional authenticated live refresh path |
| Boundary | Educational analytics only; not eligibility, legal advice, or invitation prediction |

<details>
<summary><strong>More dashboard views</strong></summary>

### Draw cadence and yearly summary

<img width="920" alt="Express Entry yearly and monthly draw statistics" src="https://github.com/user-attachments/assets/3bd00fd1-9436-4851-b05f-959ae82752fc" />

### Program distribution

<img width="920" alt="Express Entry program distribution and yearly program share" src="https://github.com/user-attachments/assets/0081425b-e6f4-4063-b96b-0366a39c8094" />

### Cut-off and invitation trends

<img width="920" alt="CRS cut-off, rolling average, invitation, and cumulative trend charts" src="https://github.com/user-attachments/assets/597c005e-5881-4c0f-b0f0-df5060de7537" />

### Stream-specific score comparison

<img width="920" alt="Healthcare stream score comparison with the next historical target" src="https://github.com/user-attachments/assets/2fe345ae-dbe0-42c6-a400-1233acaea2ca" />

</details>

> **Use boundary:** This educational dashboard summarizes public IRCC
> information, including historical draw data and current news. It does not
> determine eligibility, predict invitations, or provide
> immigration or legal advice. Verify current rules with
> [IRCC](https://www.canada.ca/en/services/immigration-citizenship.html) or an
> authorized professional.

## Features
- **Latest Draws**: View the 10 most recent draws with draw number, date, program, invitations issued, and CRS cut-off.
- **Yearly & Monthly Stats**: Compare the cadence of draws across years and months to spot seasonal patterns.
- **Program Distribution**: Examine draw counts and invitation share by program each year.
- **Cut-off Trends**: Follow CRS cut-offs, a 5-draw moving average, and invitation volume on a dual-axis chart.
- **Cumulative Momentum**: Watch cumulative draw count and total invitations grow throughout the year.
- **Immigration News**: Read the latest IRCC headlines scraped directly from Canada.ca.
- **Personal Benchmarking**: Enter your CRS score to see where you land against historic cut-offs, with per-program filtering.
- **Fail-closed Ingestion**: Check schema, types, duplicates, row count, numeric null rates, and freshness before downloaded draws reach SQLite.
- **Offline-safe Bootstrap**: Populate an empty deployment from a checksum-pinned, source-attributed 426-row IRCC snapshot without requiring a token or network request.

## Tech Stack
- **Backend**: Python, Flask, SQLite
- **Frontend**: HTML, CSS, Chart.js
- **Data Sources**: IRCC Express Entry API, Canada.ca News (HTTP scraping)

## Getting Started

### Prerequisites
- Python 3.10+
- Virtual environment recommended (e.g., `python3 -m venv .venv`)

### Installation
```bash
git clone <your-repo-url>
cd expressEntryService
python3 -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Initialize the SQLite schema and, when empty, the bundled historical snapshot
python -c "from scraper import initialize_db; initialize_db()"

# Run the Flask app
export FLASK_APP=app.py    # On Windows PowerShell: $env:FLASK_APP = 'app.py'
flask run
```
Browse to `http://127.0.0.1:5000` to explore the dashboard.

### Tests

Create the virtual environment locally instead of copying an existing `venv/`
or `.venv/` directory; virtual environments contain machine-specific Python
paths and are intentionally ignored by Git.

```bash
python3 -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The test suite is offline and deterministic: HTTP responses and the SQLite
database are isolated, so running it does not alter `data/express_entry.db`.

Run the data-quality report against a local database without contacting IRCC:

```bash
python data_quality.py --db data/express_entry.db --minimum-rows 100 --strict
```

Use `--as-of YYYY-MM-DD` for a reproducible freshness result. The full contract
and exit-code behavior are documented in [`docs/data-quality.md`](docs/data-quality.md).

### Empty-database bootstrap

A clean deployment validates and loads the bundled IRCC snapshot only when the
`express_entry` table has zero rows. The bootstrap is deterministic, requires
no admin token or network access, and writes all draw rows plus their provenance
in one SQLite transaction. It never replaces an existing database. The UI
shows the exact historical through-date, row count, source, and non-endorsement
notice so bundled evidence cannot be mistaken for a live prediction or an
official IRCC service.

The unchanged 426-row source response, checksum, attribution, and reproduction
boundary are recorded in [`data/bootstrap/README.md`](data/bootstrap/README.md).

### Updating Data
Run the JSON-based fetch helper shipped in `scraper.py`:
```bash
python -c "from scraper import initialize_db, fetch_and_store_rounds; initialize_db(); print(fetch_and_store_rounds())"
```
This routine resolves IRCC’s latest `ee_rounds_*.json` endpoint, loads every draw, and persists them via `insert_draw_data()`. See `docs/data-fetching.md` for background on the migration from legacy HTML scraping to the JSON workflow.

## Engineering Case Study

- **Problem** — A page-layout change broke the original HTML scraper, while
  formatted values such as `5,000` could silently become `NULL` and distort
  invitation totals.
- **Decision** — Discover IRCC's structured JSON feed, normalize only documented
  integer forms, gate writes with a machine-readable quality contract, and apply
  each accepted payload in one SQLite transaction. A checksum-pinned official
  snapshot provides the same validated evidence when a clean hosted database
  starts without network access.
- **Verification** — Offline fixtures exercise endpoint discovery, schema and
  type errors, truncation, duplicates, null-rate thresholds, freshness, and
  isolated SQLite replacement behavior. The same checks are available through a
  JSON CLI for operational review.
- **Limits** — Freshness can identify old data but cannot explain an IRCC pause;
  historical cut-offs do not predict a future invitation or establish a user's
  eligibility. Live refreshes still depend on IRCC availability, and SQLite data
  survives a hosted restart only when the service provides persistent storage.
- **Learning** — Reliable data products need explicit contracts at their input
  boundary. Rejecting unsafe evidence and surfacing uncertainty matters as much
  as rendering the charts.

#### Remote refresh (for hosted environments)
Set an `ADMIN_UPDATE_TOKEN` environment variable (Render: Dashboard → Environment → Add Variable). Then trigger a refresh with:
```bash
curl -X POST https://<your-service>.onrender.com/admin/update \
     -H "X-Admin-Token: $ADMIN_UPDATE_TOKEN"
```
The endpoint returns the JSON fetch summary when the token matches. Rotate the token periodically and avoid embedding it in client-side code.
Only the `X-Admin-Token` header is accepted; URL and form tokens are rejected so
credentials are less likely to enter browser history or access logs. On Render,
attach a persistent disk for `data/express_entry.db` or expect SQLite updates to
be lost when the instance is replaced or redeployed.

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
├── data_quality.py        # Offline ingestion contract and JSON report CLI
├── scraper.py             # DB init, JSON fetch, and draw ingestion helpers
├── requirements.txt       # Python dependencies
├── requirements-dev.txt   # Runtime plus test dependencies
├── data/
│   ├── bootstrap/         # Exact, attributed IRCC fallback snapshot
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
│   ├── data-fetching.md   # Notes on legacy vs. JSON data collection
│   └── data-quality.md    # Quality signals, thresholds, and CLI usage
├── read_before_use.rtf
└── .venv/                 # Optional local virtual environment (ignored)
```

## License
No explicit source-code license is bundled. The IRCC snapshot is separately
governed by the reproduction boundary documented in
[`data/bootstrap/README.md`](data/bootstrap/README.md); it is not implicitly
licensed with the surrounding code. Commercial redistribution requires the
permission described in IRCC's terms.
