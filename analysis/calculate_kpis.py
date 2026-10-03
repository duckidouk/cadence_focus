"""Load a controlled company dataset and calculate reusable financial KPIs."""

from pathlib import Path
import sqlite3

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "database" / "cf.db"
COMPANY_SQL_FILES = {
    "4 Fibre": PROJECT_ROOT / "sql" / "4fibre_kpis.sql",
    "SCCI Group": PROJECT_ROOT / "sql" / "scci_kpis.sql",
}
DEFAULT_COMPANY = "4 Fibre"
REQUIRED_REPORTING_COLUMNS = {
    "company_name",
    "company_number",
    "reporting_date",
    "cash",
    "current_assets",
    "debtors",
    "profit_loss",
    "net_current_assets",
    "net_assets",
}


def load_reporting_data(
    database_path: Path = DEFAULT_DATABASE,
    company_name: str = DEFAULT_COMPANY,
) -> pd.DataFrame:
    """Run the reporting query and return one row per reporting period."""
    try:
        sql_file = COMPANY_SQL_FILES[company_name]
    except KeyError as error:
        choices = ", ".join(COMPANY_SQL_FILES)
        raise ValueError(f"Unknown company {company_name!r}. Choose from: {choices}.") from error

    sql = sql_file.read_text(encoding="utf-8")

    with sqlite3.connect(database_path) as connection:
        dataframe = pd.read_sql_query(sql, connection)

    missing_columns = REQUIRED_REPORTING_COLUMNS.difference(dataframe.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"The reporting query is missing required columns: {missing}.")

    dataframe["reporting_date"] = pd.to_datetime(dataframe["reporting_date"])
    return dataframe.sort_values("reporting_date").reset_index(drop=True)


def add_calculated_kpis(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Add transparent liquidity and asset-mix calculations."""
    result = dataframe.copy()
    source_columns = [
        "cash",
        "current_assets",
        "debtors",
        "profit_loss",
        "net_current_assets",
        "net_assets",
    ]
    result[source_columns] = result[source_columns].apply(
        pd.to_numeric, errors="coerce"
    )

    # Net current assets = current assets - current liabilities.
    result["current_liabilities"] = (
        result["current_assets"] - result["net_current_assets"]
    )
    nonzero_current_liabilities = result["current_liabilities"].where(
        result["current_liabilities"].ne(0)
    )
    nonzero_current_assets = result["current_assets"].where(
        result["current_assets"].ne(0)
    )

    result["current_ratio"] = (
        result["current_assets"] / nonzero_current_liabilities
    )
    result["cash_share_current_assets"] = (
        result["cash"] / nonzero_current_assets
    )
    result["debtors_share_current_assets"] = (
        result["debtors"] / nonzero_current_assets
    )
    result["cash_coverage_current_liabilities"] = (
        result["cash"] / nonzero_current_liabilities
    )

    return result


def latest_comparison(dataframe: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Return the latest and immediately preceding reporting periods."""
    if len(dataframe) < 2:
        raise ValueError("At least two reporting periods are required for comparison.")

    ordered = dataframe.sort_values("reporting_date")
    return ordered.iloc[-1], ordered.iloc[-2]


def create_kpi_summary(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Create a numeric prior-period KPI comparison table."""
    current, prior = latest_comparison(dataframe)

    metrics = [
        ("Cash", "cash", "GBP"),
        ("Profit / (loss)", "profit_loss", "GBP"),
        (
            "Net current position",
            "net_current_assets",
            "GBP",
        ),
        ("Current ratio", "current_ratio", "x"),
        ("Debtors", "debtors", "GBP"),
        ("Net assets", "net_assets", "GBP"),
    ]

    rows = []

    for kpi_name, column_name, unit in metrics:
        prior_value = prior[column_name]
        current_value = current[column_name]
        change = (
            current_value - prior_value
            if pd.notna(current_value) and pd.notna(prior_value)
            else float("nan")
        )

        rows.append(
            {
                "kpi": kpi_name,
                "prior": prior_value,
                "current": current_value,
                "change": change,
                "unit": unit,
            }
        )

    return pd.DataFrame(rows)

def main(company_name: str = DEFAULT_COMPANY) -> None:
    """Print the calculated KPI summary for a manual check."""
    reporting_data = load_reporting_data(company_name=company_name)
    calculated_data = add_calculated_kpis(reporting_data)
    summary = create_kpi_summary(calculated_data)

    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
