"""Load the controlled SQL dataset and calculate SCCI Group KPIs."""

from pathlib import Path
import sqlite3

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "database" / "cf.db"
SQL_FILE = PROJECT_ROOT / "sql" / "scci_kpis.sql"


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


def main() -> None:
    """Print the calculated reporting table for a quick manual check."""
    reporting_data = add_calculated_kpis(load_reporting_data())
    print(reporting_data.to_string(index=False))


if __name__ == "__main__":
    main()
