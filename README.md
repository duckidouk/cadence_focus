# Cadence Focus

Cadence Focus is a simple financial-analysis dashboard for UK private companies. It reads company filing data from a SQLite database, calculates useful KPIs, and displays the results in a Streamlit web app.

## How it works

```text
SQLite database
      ↓
SQL selects and organises the financial facts
      ↓
Python calculates additional KPIs
      ↓
Plotly creates the charts
      ↓
Streamlit displays the dashboard
```

## How Companies House data enters the project

The project uses the official Companies House APIs rather than copying information from webpages. The API key is stored as `COMPANIES_HOUSE_API_KEY` in the project-root `.env` file and must never be committed to Git.

### Financial accounts importer

`cf_financial_facts.py` supplies the dashboard data. It:

1. Finds the selected company's latest filed accounts.
2. Downloads the structured XHTML/iXBRL accounts from Companies House.
3. Extracts tagged numeric facts, dates, units and source information.
4. Checks that the accounts belong to the selected company.
5. Backs up the existing database.
6. Saves the facts into the `financial_facts` table in `data/database/cf.db`.

Preview an import without changing the database:

```bash
.venv/bin/python cf_financial_facts.py --company 04144664 --dry-run
```

Import the same 4 Fibre accounts into the database:

```bash
.venv/bin/python cf_financial_facts.py --company 04144664
```

The importer handles structured accounts only. If Companies House provides only a PDF, it stops without writing figures rather than guessing their values.

### 1. Database

`data/database/cf.db` stores the financial facts collected from company filings. The dashboard only reads this database; running the app does not change it.

### 2. SQL

The files in `sql/` select the facts needed for each company and turn them into one reporting row per financial period.

The app's company selector currently supports nine controlled datasets:

| Dashboard name | Legal company | Company number | Profit | Revenue |
|---|---|---:|---|---|
| 4 Fibre | 4 FIBRE LIMITED | `04144664` | Not reported | Not reported |
| Airwave Europe | AIRWAVE EUROPE LTD. | `03000768` | Reported | Reported |
| Alphatrack Systems | ALPHATRACK SYSTEMS LIMITED | `02863196` | Reported | Reported |
| Cable Television Services | CABLE TELEVISION SERVICES LIMITED | `02070618` | Not reported | Not reported |
| Interphone | INTERPHONE LIMITED | `00692333` | Not reported | Not reported |
| Radio Data Networks | RADIO DATA NETWORKS LIMITED | `02984975` | Not reported | Not reported |
| SCCI Alphatrack | SCCI ALPHATRACK LTD | `02760731` | Reported | Reported |
| SCCI Group | SCCI GROUP LIMITED | `06089974` | Reported | Not reported |
| SCS Technologies | SCS TECHNOLOGIES LTD | `03505057` | Not reported | Not reported |

Each company has a controlled query because XBRL concept names can differ between
filings. Selecting a company changes the query; it does not change the database. Missing
facts are returned as `NULL` and displayed as `N/A`, never replaced with zero.

Legacy **SCCI LIMITED** (`05150526`) is not included because its stored facts lack
reporting dates and cannot support a reliable two-period comparison without a clean re-import.

### 3. Python and Pandas

`analysis/calculate_kpis.py` runs the SQL query and loads the result into a Pandas DataFrame. It then calculates additional measures, including:

- Current liabilities
- Current ratio
- Cash as a share of current assets
- Debtors as a share of current assets
- Cash coverage of current liabilities

These calculations exist temporarily in the DataFrame and are not written back to the database.

### 4. Plotly and Streamlit

`app.py` compares the latest reporting period with the previous period. It displays:

- Seven headline KPI cards, including revenue when reported
- Current-asset and profit/loss charts
- A short interpretation
- Data-quality warnings
- Filing dates and source links

Plotly creates the charts, while Streamlit arranges everything on the webpage.

### 5. Theme

`.streamlit/config.toml` controls the colours, fonts, borders, and other visual settings. The corresponding font files are stored in `static/`.

Changing the theme changes how the app looks, not how its KPIs are calculated.

## Project structure

```text
Cadence_Focus/
├── .streamlit/
│   └── config.toml
├── analysis/
│   └── calculate_kpis.py
├── data/
│   └── database/
│       └── cf.db
├── documentation/
│   └── KPI_dictionary.xlsx
├── sql/
│   ├── 4fibre_kpis.sql
│   ├── airwave_europe_kpis.sql
│   ├── alphatrack_systems_kpis.sql
│   ├── cable_television_services_kpis.sql
│   ├── interphone_kpis.sql
│   ├── radio_data_networks_kpis.sql
│   ├── scci_alphatrack_kpis.sql
│   ├── scci_kpis.sql
│   └── scs_technologies_kpis.sql
├── static/
│   └── font files
├── cf_financial_facts.py
└── app.py
```

## Run the dashboard

From the main `Cadence_Focus` folder:

```bash
source .venv/bin/activate
streamlit run app.py
```

Streamlit runs `app.py`, loads the database data, calculates the KPIs, creates the charts, and opens the dashboard at `http://localhost:8501`.

Use the **Company** control in the sidebar to switch between the supported companies.

To stop the app, click inside the terminal and press `Control + C`.

Run the automated importer, calculation, SQL and dashboard checks with:

```bash
.venv/bin/python -m unittest -v
```

## Important data limitation

Verified revenue is currently available for Airwave Europe, Alphatrack Systems and
SCCI Alphatrack. It remains unavailable for the other supported companies. Verified
EBITDA is not currently available, so EBITDA margins, cash conversion and leverage
KPIs remain unavailable rather than being treated as zero.

Some companies also omit tagged profit or debtors facts. The app displays those
measures as **Not reported**, suppresses unsupported charts, and preserves the
missing values instead of replacing them with zero.

SCS Technologies' stored employee facts currently evaluate to `0.62` and `0.64`
because the filing supplies a negative scale. Employee count is not displayed as a KPI;
the source value is retained pending separate validation rather than silently corrected.
