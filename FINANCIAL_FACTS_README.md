# Cadence financial accounts importer

`cf_financial_facts.py` converts the exploratory notebook into an independent,
reusable script. It defaults to **Cadence Equity Partners Limited (10238359)**.
It uses the project's existing `requests` and `python-dotenv` dependencies.

From the `Cadence_Focus` folder, preview the extraction:

```sh
.venv/bin/python cf_financial_facts.py --dry-run
```

Save the results to the existing `data/database/cf.db`:

```sh
.venv/bin/python cf_financial_facts.py
```

Other examples:

```sh
.venv/bin/python cf_financial_facts.py --company scci
.venv/bin/python cf_financial_facts.py --company jlas --dry-run
.venv/bin/python cf_financial_facts.py --company 10238359 --accounts-date 2024-06-30
```

The API key comes from `COMPANIES_HOUSE_API_KEY` in the project-root `.env`.
Paths are based on the script's location, so running it from another folder also
works. `--project-dir` and `--db` allow explicit overrides.

## Read the script in this order

1. `run()` shows the entire workflow in order.
2. `find_accounts()` finds the newest filed accounts for the selected company.
3. `download_accounts()` gets the structured document using its advertised format.
4. `parse_facts()` turns its numeric tags into a list of dictionaries.
5. `save_facts()` writes those dictionaries into `financial_facts`.

`numeric_value()` handles minus signs, decimal separators and scale. For example,
`1,321` with `scale="3"` represents **1,321,000**, not 1,321.

## What was fixed

The notebook's earlier cells fetched SCCI accounts, while its database cell loaded
Cadence's profile. That could attach SCCI figures to Cadence's company number.
The script uses one company throughout and checks the identifiers in the accounts.

The notebook also used a variable before defining it, selected a particular filing
description rather than accounts generally, assumed every document offered XHTML,
and had a final SQL query with a missing comma and an unused parameter. The script
removes the cell-order dependency and exploratory queries, adds HTTP timeouts and
errors, paginates filing history, and closes database connections reliably.

## Dates, units and database behaviour

The importer keeps **all numeric facts**, including comparative years and detailed
breakdowns. `instant` is the date of a balance-sheet amount; `period_start` and
`period_end` describe a period such as annual turnover. `dimensions_json` identifies
breakdowns, so a subsidiary or asset category is not mistaken for a total.

The original table and columns remain available. Extra columns are added for dates,
units, parsing status and provenance. `value_numeric` supports existing queries;
`value_exact` stores the exact decimal string. Existing rows receive no invented
dates. Reimporting the same document updates its facts without adding duplicates.
An existing database is backed up in `data/database/backups` before every write.
Other tables and other companies' rows are preserved.

For example, inspect Cadence's current-assets facts after importing:

```sql
SELECT concept_local_name, value_numeric, unit_measure, instant, context_ref
FROM financial_facts
WHERE company_number = '10238359'
  AND concept_local_name = 'CurrentAssets'
ORDER BY instant DESC;
```

To call it from other Cadence code:

```python
from cf_financial_facts import run

facts = run(company="cadence", dry_run=True)
```

## Supported scope and verification

This is a structured XHTML/iXBRL and basic XML/XBRL importer, not a PDF/OCR or full
XBRL validation engine. A PDF-only filing stops with an explanation and no database
write; it does not silently substitute an older year. Unknown number formats stay
as raw text with a parsing status and no numeric value. Conflicting duplicate facts
stop the import. A missing revenue tag means **no matching tagged fact was found**;
it does not establish that revenue is zero or absent from the entire document.

Verified against Cadence's live accounts dated 30 June 2025: 46 unique numeric facts,
including current assets of £933,925 for 2025 and £1,051,784 for 2024. No exact
`Revenue` or `Turnover` tag was found. Importing twice into a copy of the project's
database preserved the existing 34 SCCI rows and retained exactly 46 Cadence rows.
The original notebook and production database were not changed during verification.

Run the offline regression tests:

```sh
.venv/bin/python -m unittest test_cf_financial_facts.py -v
```

Reference specifications:
- [Companies House document metadata and available formats](https://developer-specs.company-information.service.gov.uk/document-api/resources/documentmetadata?v=latest)
- [Inline XBRL specification](https://specifications.xbrl.org/work-product-index-inline-xbrl-inline-xbrl-1.1.html)
