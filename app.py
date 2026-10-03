"""Streamlit dashboard for the first Cadence Focus KPI pack."""

import pandas as pd
import plotly.express as px
import streamlit as st

from analysis.calculate_kpis import (
    COMPANY_SQL_FILES,
    DEFAULT_COMPANY,
    add_calculated_kpis,
    latest_comparison,
    load_reporting_data,
)


st.set_page_config(page_title="Cadence Focus", layout="wide")


def pounds_value(value: float) -> str:
    """Format GBP at a useful scale, using parentheses for negative values."""
    if pd.isna(value):
        return "N/A"
    amount = abs(value)
    if amount >= 1_000_000:
        formatted = f"£{amount / 1_000_000:.2f}m"
    elif amount >= 1_000:
        formatted = f"£{amount / 1_000:.1f}k"
    else:
        formatted = f"£{amount:,.0f}"
    return f"({formatted})" if value < 0 else formatted


def money_delta(current: float, prior: float) -> str | None:
    """Format the absolute movement from the prior period."""
    if pd.isna(current) or pd.isna(prior):
        return None
    change = current - prior
    sign = "+" if change >= 0 else "-"
    return f"{sign}{pounds_value(abs(change))} vs prior year"


def ratio_value(value: float) -> str:
    """Format a ratio without presenting a missing value as a number."""
    return "N/A" if pd.isna(value) else f"{value:.2f}x"


def ratio_delta(current: float, prior: float) -> str | None:
    """Describe a ratio movement only when both periods are available."""
    if pd.isna(current) or pd.isna(prior):
        return None
    return f"{current - prior:+.2f}x vs prior year"


def movement(current: float, prior: float) -> str:
    """Return a plain-English direction for two reported values."""
    if current > prior:
        return "increased"
    if current < prior:
        return "decreased"
    return "was unchanged"


def interpretation(latest: pd.Series, prior: pd.Series) -> str:
    """Build commentary from reported facts without inventing missing figures."""
    observations = []

    if pd.notna(latest["cash"]) and pd.notna(prior["cash"]):
        observations.append(f"Cash {movement(latest['cash'], prior['cash'])}.")

    if pd.notna(latest["current_assets"]) and pd.notna(prior["current_assets"]):
        observations.append(
            f"Current assets {movement(latest['current_assets'], prior['current_assets'])}."
        )

    if pd.notna(latest["net_current_assets"]) and pd.notna(prior["net_current_assets"]):
        if latest["net_current_assets"] < 0 <= prior["net_current_assets"]:
            observations.append(
                "The company moved from a positive net current position to net current liabilities."
            )
        else:
            observations.append(
                "The net current position "
                f"{movement(latest['net_current_assets'], prior['net_current_assets'])}."
            )

    if pd.notna(latest["net_assets"]) and pd.notna(prior["net_assets"]):
        observations.append(
            f"Net assets {movement(latest['net_assets'], prior['net_assets'])}."
        )

    unavailable = [
        label
        for label, column in (("Profit / (loss)", "profit_loss"), ("Debtors", "debtors"))
        if pd.isna(latest[column]) or pd.isna(prior[column])
    ]
    if unavailable:
        observations.append(
            f"{' and '.join(unavailable)} were not reported as verified facts, "
            "so no conclusion is drawn for those measures."
        )

    observations.append(
        "The filing shows these movements but does not establish their causes."
    )
    return " ".join(observations)


def unavailable_metrics(dataframe: pd.DataFrame) -> list[str]:
    """List measures that cannot be supported across both comparison periods."""
    unavailable = [
        label
        for label, column in (
            ("profit / (loss)", "profit_loss"),
            ("debtors", "debtors"),
        )
        if dataframe[column].isna().any()
    ]
    return unavailable + ["revenue", "EBITDA"]


@st.cache_data
def get_data(company_name: str) -> pd.DataFrame:
    """Load and calculate the reporting data without modifying the database."""
    return add_calculated_kpis(load_reporting_data(company_name=company_name))


st.title("Cadence Focus")
selected_company = st.sidebar.selectbox(
    "Company",
    options=list(COMPANY_SQL_FILES),
    index=list(COMPANY_SQL_FILES).index(DEFAULT_COMPANY),
)
st.sidebar.caption("Select a company to run its controlled reporting query.")

try:
    data = get_data(selected_company)
    latest, prior = latest_comparison(data)
except (FileNotFoundError, ValueError, pd.errors.DatabaseError) as error:
    st.error(f"The KPI data could not be loaded: {error}")
    st.stop()

st.caption(
    f"{latest['company_name']} | Company number "
    f"{latest['company_number']} | Public filing data"
)

st.subheader("Headline KPIs")
first_row = st.columns(2)
first_row[0].metric(
    "Cash", pounds_value(latest["cash"]), money_delta(latest["cash"], prior["cash"])
)
first_row[1].metric(
    "Profit / (loss)",
    pounds_value(latest["profit_loss"]),
    money_delta(latest["profit_loss"], prior["profit_loss"]),
)

second_row = st.columns(2)
second_row[0].metric(
    "Net current position",
    pounds_value(latest["net_current_assets"]),
    money_delta(latest["net_current_assets"], prior["net_current_assets"]),
)
second_row[1].metric(
    "Current ratio",
    ratio_value(latest["current_ratio"]),
    ratio_delta(latest["current_ratio"], prior["current_ratio"]),
)

third_row = st.columns(2)
third_row[0].metric(
    "Debtors",
    pounds_value(latest["debtors"]),
    money_delta(latest["debtors"], prior["debtors"]),
)
third_row[1].metric(
    "Net assets",
    pounds_value(latest["net_assets"]),
    money_delta(latest["net_assets"], prior["net_assets"]),
)

asset_data = data.melt(
    id_vars="reporting_date",
    value_vars=["cash", "current_assets", "debtors"],
    var_name="metric",
    value_name="value",
)
asset_data["metric"] = asset_data["metric"].map(
    {"cash": "Cash", "current_assets": "Current assets", "debtors": "Debtors"}
)
asset_data = asset_data.dropna(subset=["value"])

asset_chart = px.bar(
    asset_data,
    x="reporting_date",
    y="value",
    color="metric",
    barmode="group",
    title="Current asset composition",
    labels={"reporting_date": "Reporting date", "value": "GBP", "metric": "Metric"},
)
asset_chart.update_yaxes(tickprefix="£", tickformat=",.0f")

st.plotly_chart(asset_chart, width="stretch")

if data["profit_loss"].notna().any():
    profit_data = data.dropna(subset=["profit_loss"])
    profit_chart = px.bar(
        profit_data,
        x="reporting_date",
        y="profit_loss",
        title="Profit / (loss)",
        labels={"reporting_date": "Reporting date", "profit_loss": "GBP"},
        color=profit_data["profit_loss"] >= 0,
        color_discrete_map={True: "#2E7D32", False: "#B42318"},
    )
    profit_chart.update_layout(showlegend=False)
    profit_chart.update_yaxes(tickprefix="£", tickformat=",.0f", zeroline=True)
    st.plotly_chart(profit_chart, width="stretch")
else:
    st.subheader("Profit / (loss)")
    st.info("Not reported as a verified fact in the available accounts.")

st.subheader("Interpretation")
st.write(interpretation(latest, prior))

st.subheader("Data quality and evidence")
unavailable = unavailable_metrics(data)
st.warning(
    f"Verified {', '.join(unavailable)} facts are not available across both reporting "
    "periods for this company. Related KPIs remain unavailable rather than zero."
)

evidence_columns = [
    "company_name",
    "reporting_date",
    "filing_date",
    "accounts_date",
    "company_number",
    "source_url",
]
st.dataframe(data[evidence_columns], width="stretch", hide_index=True)
