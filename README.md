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

Two Python scripts collect different kinds of information:

### Company research

`companyhouse_scrape_company-information.py` retrieves general company information, including:

- Company profile
- Officers and their other appointments
- People with significant control
- Filing history
- Charges and insolvency information

It saves this research as a JSON file. It does **not** supply the financial figures shown in the dashboard.

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

The app's company selector currently supports:

- `sql/4fibre_kpis.sql` for **4 FIBRE LIMITED** (`04144664`)
- `sql/scci_kpis.sql` for **SCCI GROUP LIMITED** (`06089974`)

Each company has a controlled query because XBRL concept names can differ between
filings. Selecting a company changes the query; it does not change the database.

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

- Six headline KPI cards
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
│   └── scci_kpis.sql
├── static/
│   └── font files
├── cf_financial_facts.py
├── companyhouse_scrape_company-information.py
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

## Important data limitation

Verified revenue and EBITDA data are not currently available. Revenue growth, margins, cash conversion, and leverage KPIs should therefore remain unavailable rather than being treated as zero.

Some companies also omit tagged profit or debtors facts. The app displays those
measures as **Not reported**, suppresses unsupported charts, and preserves the
missing values instead of replacing them with zero.
