# Bundled IRCC fallback snapshot

`ircc-ee-rounds-2026-07-09.json` is an exact, byte-for-byte copy of the
Government of Canada JSON response recorded below. It is bundled so a clean,
network-isolated deployment can render historical draw evidence instead of an
empty dashboard.

## Provenance

- Complete source title: **Express Entry: Rounds of invitations**
- Author organization: **Immigration, Refugees and Citizenship Canada (IRCC)**
- Original JSON URL:
  <https://www.canada.ca/content/dam/ircc/documents/json/ee_rounds_123_en.json>
- Official source page:
  <https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/rounds-invitations.html>
- Retrieved: **2026-07-09**
- Upstream `Last-Modified`: **2026-07-09 14:04:58 GMT**
- Latest draw date in the response: **2026-07-09**
- Draw records: **426**
- SHA-256:
  `db435d0d3b45e23149111851bfd74201e74e42cd6a0ffb83d6aac6215d74f5b2`

The snapshot passes this project's ingestion contract with 426 rows, no
blocking reasons, no warnings, and a `pass` freshness result when evaluated as
of 2026-07-09. The application checks both the recorded checksum and the same
fail-closed contract before inserting any bundled row.

## Reproduction notice

IRCC's [terms and conditions](https://www.canada.ca/en/immigration-refugees-citizenship/corporate/terms-conditions.html)
permit non-commercial reproduction without further permission when due
diligence is used, the complete title and author are identified, and the
original URL is provided. This repository uses the snapshot for a
non-commercial portfolio demonstration and preserves the downloaded response
without alteration.

This reproduction was not produced in affiliation with, or with the
endorsement of, IRCC or the Government of Canada. The snapshot is not covered
by any licence that may apply to the surrounding source code. Commercial
redistribution requires the permission described in IRCC's terms. No official
Government of Canada symbols are reproduced here.

## Runtime boundary

The fallback is considered only when `express_entry` has zero rows. The
application rechecks emptiness while holding a SQLite write transaction, loads
all accepted rows and provenance atomically, and rolls everything back on any
failure. Existing rows are never replaced by the bootstrap path. A later
authenticated live refresh updates the provenance label in the same data
transaction.
