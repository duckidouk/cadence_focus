# Cadence Focus

Cadence Focus is a Python and SQL prototype for acquisition and portfolio analysis.

## KPI workflow

1. Define the business question.
2. Agree the KPI definitions in `documentation/KPI_dictionary.xlsx`.
3. Produce the controlled reporting dataset with `sql/scci_kpis.sql`.
4. Calculate and validate KPIs in `analysis/calculate_kpis.py`.
5. Build charts with Plotly.
6. Present the tested results in `app.py` with Streamlit.
7. Write conclusions that separate facts, interpretation, and missing information.

## Project structure

```text
Cadence_Focus/
├── documentation/
│   └── KPI_dictionary.xlsx
├── data/
│   └── database/
│       ├── cf.db
│       └── backups/
├── sql/
│   └── scci_kpis.sql
├── analysis/
│   └── calculate_kpis.py
└── app.py
```

## Run the checks

```bash
source .venv/bin/activate
python analysis/calculate_kpis.py
```

## Run the dashboard

```bash
source .venv/bin/activate
streamlit run app.py
```

The first KPI pack covers SCCI GROUP LIMITED, company number `06089974`.
Revenue and EBITDA KPIs remain unavailable until verified source data is added.

The SQLite database lives at `data/database/cf.db`. Timestamped backups are
stored in `data/database/backups` and excluded from Git.
