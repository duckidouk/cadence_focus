#Load the controlled SQL dataset and calculate SCCI Group KPIs

from pathlib import Path
import sqlite3

import pandas as pd

company = {
    "4fibre":"4fibre",
    "SCCI": "scci",
    "Airwave Europe":"airwave_europe"
}
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "database" / "cf.db"
SQL_FILE = PROJECT_ROOT / "sql" / f"{company["4fibre"]}_kpis.sql"


def load_reporting_data(database_path: Path = DEFAULT_DATABASE) -> pd.DataFrame:
    """Run the reporting query and return one row per reporting period."""
    sql = SQL_FILE.read_text(encoding="utf-8")

    with sqlite3.connect(database_path) as connection:
        dataframe = pd.read_sql_query(sql, connection)

    dataframe["reporting_date"] = pd.to_datetime(dataframe["reporting_date"])
    return dataframe.sort_values("reporting_date").reset_index(drop=True)


def add_calculated_kpis(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Add transparent liquidity and asset-mix calculations."""
    result = dataframe.copy()

    # Net current assets = current assets - current liabilities.
    result["current_liabilities"] = (
        result["current_assets"] - result["net_current_assets"]
    )

    result["current_ratio"] = (
        result["current_assets"] / result["current_liabilities"]
    )
    result["cash_share_current_assets"] = (
        result["cash"] / result["current_assets"]
    )
    result["debtors_share_current_assets"] = (
        result["debtors"] / result["current_assets"]
    )
    result["cash_coverage_current_liabilities"] = (
        result["cash"] / result["current_liabilities"]
    )

    return result


def latest_comparison(dataframe: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Return the latest and immediately preceding reporting periods."""
    if len(dataframe) < 2:
        raise ValueError("At least two reporting periods are required for comparison.")

    ordered = dataframe.sort_values("reporting_date")
    return ordered.iloc[-1], ordered.iloc[-2]


#creating kpis for streamlit

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

        rows.append(
            {
                "kpi": kpi_name,
                "prior": prior_value,
                "current": current_value,
                "change": current_value - prior_value,
                "unit": unit,
            }
        )

    return pd.DataFrame(rows)

def main() -> None:
    """Print the calculated KPI summary for a manual check."""
    reporting_data = load_reporting_data()
    calculated_data = add_calculated_kpis(reporting_data)
    summary = create_kpi_summary(calculated_data)

    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
