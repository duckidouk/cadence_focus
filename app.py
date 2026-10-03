"""Streamlit dashboard for the first Cadence Focus KPI pack."""

import pandas as pd
import plotly.express as px
import streamlit as st

from analysis.calculate_kpis import (
    add_calculated_kpis,
    latest_comparison,
    load_reporting_data,
)


st.set_page_config(page_title="Cadence Focus", layout="wide")


def pounds_millions(value: float) -> str:
    """Format a GBP value in millions, using parentheses for negatives."""
    amount = abs(value) / 1_000_000
    return f"£({amount:.2f})m" if value < 0 else f"£{amount:.2f}m"


def money_delta(current: float, prior: float) -> str:
    """Format the absolute movement from the prior period."""
    change = current - prior
    sign = "+" if change >= 0 else "−"
    return f"{sign}£{abs(change) / 1_000_000:.2f}m vs prior year"


@st.cache_data
def get_data() -> pd.DataFrame:
    """Load and calculate the reporting data without modifying the database."""
    return add_calculated_kpis(load_reporting_data())


st.title("Cadence Focus")

try:
    data = get_data()
    latest, prior = latest_comparison(data)
except (FileNotFoundError, ValueError, pd.errors.DatabaseError) as error:
    st.error(f"The KPI data could not be loaded: {error}")
    st.stop()

st.caption(
    f"{latest['company_name'].title()} | Company number "
    f"{latest['company_number']} | Public filing data"
)

st.subheader("Headline KPIs")
first_row = st.columns(3)
first_row[0].metric("Cash", pounds_millions(latest["cash"]), money_delta(latest["cash"], prior["cash"]))
first_row[1].metric("Profit / (loss)", pounds_millions(latest["profit_loss"]), money_delta(latest["profit_loss"], prior["profit_loss"]))
first_row[2].metric("Net current position", pounds_millions(latest["net_current_assets"]), money_delta(latest["net_current_assets"], prior["net_current_assets"]))

second_row = st.columns(3)
second_row[0].metric("Current ratio", f"{latest['current_ratio']:.2f}x", f"{latest['current_ratio'] - prior['current_ratio']:+.2f}x vs prior year")
second_row[1].metric("Debtors", pounds_millions(latest["debtors"]), money_delta(latest["debtors"], prior["debtors"]))
second_row[2].metric("Net assets", pounds_millions(latest["net_assets"]), money_delta(latest["net_assets"], prior["net_assets"]))

asset_data = data.melt(
    id_vars="reporting_date",
    value_vars=["cash", "current_assets", "debtors"],
    var_name="metric",
    value_name="value",
)
asset_data["metric"] = asset_data["metric"].map(
    {"cash": "Cash", "current_assets": "Current assets", "debtors": "Debtors"}
)

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

profit_chart = px.bar(
    data,
    x="reporting_date",
    y="profit_loss",
    title="Profit / (loss)",
    labels={"reporting_date": "Reporting date", "profit_loss": "GBP"},
    color=data["profit_loss"] >= 0,
    color_discrete_map={True: "#2E7D32", False: "#B42318"},
)
profit_chart.update_layout(showlegend=False)
profit_chart.update_yaxes(tickprefix="£", tickformat=",.0f", zeroline=True)

left_chart, right_chart = st.columns(2)
left_chart.plotly_chart(asset_chart, width="stretch")
right_chart.plotly_chart(profit_chart, width="stretch")

st.subheader("Interpretation")
st.write(
    "Cash and current assets increased, but reported profit moved to a loss. "
    "The net current liability position deepened and net assets declined. "
    "The filing identifies these movements but does not establish their causes."
)

st.subheader("Data quality and evidence")
st.warning(
    "Verified revenue and EBITDA facts are not currently available. Revenue growth, "
    "margins, cash conversion and leverage KPIs must remain unavailable rather than zero."
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
