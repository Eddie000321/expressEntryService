# Express Entry Data Fetching Approaches

This document summarizes the differences between the original HTML scraping approach and the newer JSON endpoint workflow for collecting Express Entry draw data from IRCC.

## Legacy (HTML table scraping)
- **Mechanism**: Downloaded the rounds table page and parsed rows from the rendered HTML.
- **Dependencies**: Required BeautifulSoup to locate table rows and extract fields.
- **Challenges**:
  - Page changes (e.g., switching to GCWeb `data-wb-json`) broke parsing and required maintenance.
  - Extracting numeric values and dates from text demanded additional cleaning.
  - Multiple tables or pagination required extra logic to ensure completeness.

## Current (JSON endpoint)
- **Mechanism**: Reads the `data-wb-json` configuration embedded on the rounds page to discover the latest `ee_rounds_###_en.json` file, then downloads it directly.
- **Benefits**:
  - Fields arrive pre-structured (`drawNumber`, `drawDate`, `drawSize`, `drawCRS`, etc.), eliminating fragile string parsing.
  - Schema changes are surfaced in a single JSON response, making adjustments easier to track.
  - Avoids coupling to page layout or frontend plugins; only the JSON file path needs to be resolved.
  - Faster and more reliable for scheduled updates or automated pipelines.

## Migration notes
1. Use `requests` to fetch the rounds page and inspect any element with a `data-wb-json` attribute.
2. Parse the JSON configuration (after converting HTML entities) and select the entry whose URL contains `ee_rounds`.
3. Download the referenced JSON file and iterate the `rounds` array.
4. Continue storing draw records via `insert_draw_data` (guarding for optional fields such as `drawText2`).

The tests in `tests/rounds_fetch/test_fetch_rounds.py` exercise the production
JSON discovery, empty-payload handling, normalization, and SQLite persistence
paths without making live network requests.

Before persistence, the production fetch path now checks payload structure,
types, duplicate draw numbers, numeric null rates, row count, and freshness.
Accepted payloads are written in one SQLite transaction so a row-level failure
rolls the entire refresh back.
See [the data-quality contract](data-quality.md) for thresholds, blocking
behavior, and an offline JSON/SQLite reporting command.

## Deterministic empty-database fallback

On a clean deployment, schema initialization checks whether `express_entry` is
empty. Only then does it read the exact bundled IRCC response in
`data/bootstrap/ircc-ee-rounds-2026-07-09.json`, verify its recorded SHA-256,
and run the same quality contract with the snapshot's fixed 2026-07-09
evaluation date. Accepted rows and provenance are inserted in one SQLite
transaction. A concurrent or pre-existing row causes the fallback to skip, and
any row-level failure rolls the full bootstrap back.

This path makes the public dashboard useful without a startup network call or
admin token. It does not present the snapshot as live data: every rendered page
shows its exact through-date, record count, official source, and non-endorsement
notice. See [`../data/bootstrap/README.md`](../data/bootstrap/README.md) for
source attribution and reproduction terms.
