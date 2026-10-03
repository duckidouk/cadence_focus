import unittest

import pandas as pd
from streamlit.testing.v1 import AppTest

from analysis.calculate_kpis import (
    DEFAULT_COMPANY,
    add_calculated_kpis,
    create_kpi_summary,
    load_reporting_data,
)


class KpiCalculationTests(unittest.TestCase):
    def sample_data(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "reporting_date": pd.to_datetime(["2024-05-31", "2025-05-31"]),
                "cash": [1_000_000, 1_200_000],
                "current_assets": [4_000_000, 5_000_000],
                "debtors": [None, None],
                "profit_loss": [None, None],
                "net_current_assets": [500_000, -100_000],
                "net_assets": [3_000_000, 2_900_000],
            }
        )

    def test_missing_facts_remain_missing_in_summary(self):
        calculated = add_calculated_kpis(self.sample_data())
        summary = create_kpi_summary(calculated).set_index("kpi")

        self.assertTrue(pd.isna(summary.loc["Profit / (loss)", "current"]))
        self.assertTrue(pd.isna(summary.loc["Profit / (loss)", "change"]))
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

    def test_both_controlled_company_queries_return_two_periods(self):
        for company_name in ("4 Fibre", "SCCI Group"):
            with self.subTest(company_name=company_name):
                data = load_reporting_data(company_name=company_name)
                self.assertGreaterEqual(len(data), 2)
                self.assertEqual(data["company_name"].nunique(), 1)


class DashboardSmokeTests(unittest.TestCase):
    def test_dashboard_starts_and_switches_company(self):
        app = AppTest.from_file("app.py", default_timeout=15).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox[0].value, DEFAULT_COMPANY)

        app.selectbox[0].select("SCCI Group").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox[0].value, "SCCI Group")


if __name__ == "__main__":
    unittest.main()
