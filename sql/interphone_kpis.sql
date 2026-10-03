-- Purpose: produce one controlled reporting row per period for Interphone.
-- Company: INTERPHONE LIMITED (00692333)
-- Source: financial_facts in data/database/cf.db

WITH clean_facts AS (
    SELECT
        c.company_name,
        f.company_number,
        COALESCE(f.period_end, f.instant, f.accounts_date) AS reporting_date,
        f.concept_local_name,
        CAST(f.value_numeric AS REAL) AS value,
        f.filing_date,
        f.accounts_date,
        f.source_url
    FROM financial_facts AS f
    LEFT JOIN company AS c
        ON f.company_number = c.company_number
    WHERE f.company_number = '00692333'
      AND COALESCE(f.dimensions_json, '{}') = '{}'
      AND f.concept_local_name IN (
          'CashBankOnHand',
          'CurrentAssets',
          'Debtors',
          'ProfitLoss',
          'NetCurrentAssetsLiabilities',
          'NetAssetsLiabilities',
          'TurnoverRevenue',
          'AverageNumberEmployeesDuringPeriod'
      )
)

SELECT
    company_name,
    company_number,
    reporting_date,
    MAX(CASE WHEN concept_local_name = 'CashBankOnHand' THEN value END) AS cash,
    MAX(CASE WHEN concept_local_name = 'CurrentAssets' THEN value END) AS current_assets,
    MAX(CASE WHEN concept_local_name = 'Debtors' THEN value END) AS debtors,
    MAX(CASE WHEN concept_local_name = 'ProfitLoss' THEN value END) AS profit_loss,
    MAX(CASE WHEN concept_local_name = 'TurnoverRevenue' THEN value END) AS revenue,
    MAX(CASE WHEN concept_local_name = 'NetCurrentAssetsLiabilities' THEN value END) AS net_current_assets,
    MAX(CASE WHEN concept_local_name = 'NetAssetsLiabilities' THEN value END) AS net_assets,
    MAX(CASE WHEN concept_local_name = 'AverageNumberEmployeesDuringPeriod' THEN value END) AS average_employees,
    MAX(filing_date) AS filing_date,
    MAX(accounts_date) AS accounts_date,
    MAX(source_url) AS source_url
FROM clean_facts
GROUP BY company_name, company_number, reporting_date
ORDER BY reporting_date;
