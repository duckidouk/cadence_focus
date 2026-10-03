import unittest

import pandas as pd
from streamlit.testing.v1 import AppTest

from analysis.calculate_kpis import (
    COMPANY_SQL_FILES,
    DEFAULT_COMPANY,
    add_calculated_kpis,
    create_kpi_summary,
    load_reporting_data,
)


class KpiCalculationTests(unittest.TestCase):
    EXPECTED_COMPANY_NUMBERS = {
        "4 Fibre": "04144664",
        "Airwave Europe": "03000768",
        "Alphatrack Systems": "02863196",
        "Cable Television Services": "02070618",
        "Interphone": "00692333",
        "Radio Data Networks": "02984975",
        "SCCI Alphatrack": "02760731",
        "SCCI Group": "06089974",
        "SCS Technologies": "03505057",
    }

    def sample_data(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "reporting_date": pd.to_datetime(["2024-05-31", "2025-05-31"]),
                "cash": [1_000_000, 1_200_000],
                "current_assets": [4_000_000, 5_000_000],
                "debtors": [None, None],
                "profit_loss": [None, None],
                "revenue": [None, None],
                "net_current_assets": [500_000, -100_000],
                "net_assets": [3_000_000, 2_900_000],
            }
        )

    def test_missing_facts_remain_missing_in_summary(self):
        calculated = add_calculated_kpis(self.sample_data())
        summary = create_kpi_summary(calculated).set_index("kpi")

        self.assertTrue(pd.isna(summary.loc["Profit / (loss)", "current"]))
        self.assertTrue(pd.isna(summary.loc["Profit / (loss)", "change"]))
        self.assertTrue(pd.isna(summary.loc["Revenue", "change"]))
        self.assertTrue(pd.isna(summary.loc["Debtors", "change"]))
        self.assertAlmostEqual(calculated.loc[1, "current_ratio"], 5_000_000 / 5_100_000)

    def test_zero_denominators_do_not_create_infinite_kpis(self):
        data = self.sample_data()
        data.loc[0, "current_assets"] = 0
        data.loc[0, "net_current_assets"] = 0

        calculated = add_calculated_kpis(data)

        self.assertTrue(pd.isna(calculated.loc[0, "current_ratio"]))
        self.assertTrue(pd.isna(calculated.loc[0, "cash_share_current_assets"]))

    def test_unknown_company_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown company"):
            load_reporting_data(company_name="Unknown Company")

    def test_all_controlled_company_queries_return_two_periods(self):
        self.assertEqual(set(COMPANY_SQL_FILES), set(self.EXPECTED_COMPANY_NUMBERS))

        for company_name, company_number in self.EXPECTED_COMPANY_NUMBERS.items():
            with self.subTest(company_name=company_name):
                data = load_reporting_data(company_name=company_name)
                self.assertEqual(len(data), 2)
                self.assertEqual(data["company_name"].nunique(), 1)
                self.assertEqual(
                    data["company_number"].astype(str).unique().tolist(),
                    [company_number],
                )
                self.assertFalse(data["reporting_date"].duplicated().any())
                self.assertTrue(
                    data[
                        ["cash", "current_assets", "net_current_assets", "net_assets"]
                    ].notna().all().all()
                )

    def test_only_supported_companies_report_revenue(self):
        companies_with_revenue = {
            company_name
            for company_name in COMPANY_SQL_FILES
            if load_reporting_data(company_name=company_name)["revenue"].notna().all()
        }

        self.assertEqual(
            companies_with_revenue,
            {"Airwave Europe", "Alphatrack Systems", "SCCI Alphatrack"},
        )

    def test_reported_profit_and_debtors_match_available_facts(self):
        companies_with_profit = {
            company_name
            for company_name in COMPANY_SQL_FILES
            if load_reporting_data(company_name=company_name)["profit_loss"].notna().all()
        }
        companies_with_debtors = {
            company_name
            for company_name in COMPANY_SQL_FILES
            if load_reporting_data(company_name=company_name)["debtors"].notna().all()
        }

        self.assertEqual(
            companies_with_profit,
            {
                "Airwave Europe",
                "Alphatrack Systems",
                "SCCI Alphatrack",
                "SCCI Group",
            },
        )
        self.assertEqual(companies_with_debtors, set(COMPANY_SQL_FILES) - {"4 Fibre"})

    def test_excluded_or_unusable_companies_are_not_registered(self):
        unsupported = {
            "3000 Years",
            "Lucky Number",
            "Cadence Equity",
            "JLAS",
            "SCCI Limited",
        }

        self.assertTrue(unsupported.isdisjoint(COMPANY_SQL_FILES))

    def test_airwave_revenue_is_reported(self):
        data = load_reporting_data(company_name="Airwave Europe")

        self.assertTrue(data["revenue"].notna().all())
        self.assertEqual(data.iloc[-1]["revenue"], 15_597_888)


class DashboardSmokeTests(unittest.TestCase):
    def test_dashboard_starts_and_switches_company(self):
        app = AppTest.from_file("app.py", default_timeout=15).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox[0].value, DEFAULT_COMPANY)

        for company_name in COMPANY_SQL_FILES:
            with self.subTest(company_name=company_name):
                app.selectbox[0].select(company_name).run()
                self.assertFalse(app.exception)
                self.assertEqual(app.selectbox[0].value, company_name)

        app.selectbox[0].select("Airwave Europe").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox[0].value, "Airwave Europe")
        metrics = {metric.label: metric.value for metric in app.metric}
        self.assertEqual(metrics["Revenue"], "£15.60m")
        self.assertNotIn("revenue", app.warning[0].value.lower())
        self.assertIn("EBITDA", app.warning[0].value)


if __name__ == "__main__":
    unittest.main()
