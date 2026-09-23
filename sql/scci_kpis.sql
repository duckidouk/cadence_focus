-- Purpose: produce one controlled reporting row per period for SCCI Group.
-- Company: SCCI GROUP LIMITED (06089974)
-- Source: financial_facts in data/database/cf.db

WITH clean_facts AS (
    SELECT
        company_number,
        COALESCE(period_end, instant, accounts_date) AS reporting_date,
        concept_local_name,
        CAST(value_numeric AS REAL) AS value,
        filing_date,
        accounts_date,
        source_url
    FROM financial_facts
    WHERE company_number = '06089974'
      AND COALESCE(dimensions_json, '{}') = '{}'
      AND concept_local_name IN (
          'CashCashEquivalents',
          'CurrentAssets',
          'Debtors',
          'ProfitLoss',
          'NetCurrentAssetsLiabilities',
          'NetAssetsLiabilities',
          'AverageNumberEmployeesDuringPeriod'
      )
)

SELECT
    company_number,
    reporting_date,
    MAX(CASE WHEN concept_local_name = 'CashCashEquivalents' THEN value END) AS cash,
    MAX(CASE WHEN concept_local_name = 'CurrentAssets' THEN value END) AS current_assets,
    MAX(CASE WHEN concept_local_name = 'Debtors' THEN value END) AS debtors,
    MAX(CASE WHEN concept_local_name = 'ProfitLoss' THEN value END) AS profit_loss,
    MAX(CASE WHEN concept_local_name = 'NetCurrentAssetsLiabilities' THEN value END) AS net_current_assets,
    MAX(CASE WHEN concept_local_name = 'NetAssetsLiabilities' THEN value END) AS net_assets,
    MAX(CASE WHEN concept_local_name = 'AverageNumberEmployeesDuringPeriod' THEN value END) AS average_employees,
    MAX(filing_date) AS filing_date,
    MAX(accounts_date) AS accounts_date,
    MAX(source_url) AS source_url
FROM clean_facts
GROUP BY company_number, reporting_date
ORDER BY reporting_date;
