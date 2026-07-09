# Express Entry Draw Data-Quality Contract

The ingestion path evaluates every downloaded IRCC `rounds` array before it
writes to SQLite. The report is deterministic when `--as-of` is supplied and
does not require network access.

## Signals and defaults

| Signal | Default contract | Persistence behavior |
| --- | --- | --- |
| Row count | At least 100 draws | Blocks a likely truncated feed |
| Schema | `drawNumber`, `drawDate`, `drawName`, `drawSize`, and `drawCRS` on every row | Missing fields or non-object rows block |
| Types | Positive draw identity with an optional letter suffix, exact `YYYY-MM-DD` date, non-empty name, and non-negative plain or comma-formatted integers | Invalid identity/date blocks; numeric failures follow the null-rate limit |
| Duplicate identity | No repeated draw number | Blocks |
| Numeric null rate | At most 2% for invitations and CRS | Above the limit blocks; a smaller non-zero rate warns |
| Freshness | Warn after 45 days; fail after 120 days | Visible in the report but does not block, because IRCC may pause draws |
| Future date | At most one day ahead of the evaluation date | Blocks an implausible payload |

The report separates `status` from `ingestion_allowed`. For example, old
authoritative data can have `status: "fail"` because it is stale while still
being safe to persist. Structural failures and likely corruption set
`ingestion_allowed: false` and stop writes.

## Atomic persistence

The complete payload is validated before SQLite is opened for data changes. An
accepted payload is then persisted in one transaction. If any draw fails, the
transaction rolls back, the refresh raises an error, and the admin endpoint
returns a generic non-success response. The local database itself is still a
hosted-storage concern: without a persistent disk, a platform restart or
redeploy can discard SQLite updates.

## Offline CLI

Evaluate the local database:

```bash
python data_quality.py \
  --db data/express_entry.db \
  --as-of 2026-07-09 \
  --minimum-rows 100 \
  --strict
```

Evaluate a previously downloaded IRCC payload instead:

```bash
python data_quality.py \
  --json path/to/ee_rounds_fixture.json \
  --as-of 2026-07-09
```

The CLI writes JSON to standard output. Exit code `0` means the payload is safe
to ingest; `1` means the contract blocked it. With `--strict`, warnings and
freshness failures also return `1`. Input and database errors return `2`.

## Scope and use boundary

This contract verifies the integrity of historical draw records. It does not
establish eligibility, calculate a complete CRS profile, predict future draws,
or provide immigration or legal advice. Policies and eligibility must be
verified with [IRCC](https://www.canada.ca/en/services/immigration-citizenship.html)
or an authorized professional.
