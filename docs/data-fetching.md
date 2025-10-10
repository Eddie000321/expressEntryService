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

The test harness in `tests/rounds_fetch/test_fetch_rounds.py` provides a reference implementation that can be adapted for the production scraper.
