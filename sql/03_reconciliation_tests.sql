-- Purpose: SQL-level audit evidence for completeness, referential integrity, and financial accuracy

USE wealth_dw;

-- TEST 1: Completeness & Quarantine Audit Summary
SELECT
    'TEST 1: Warehouse vs Quarantine Counts' AS test_name,
    (SELECT COUNT(*) FROM fact_transactions) AS valid_fact_rows,
    (SELECT COUNT(*) FROM quarantine_transactions) AS quarantined_rows,
    (SELECT COUNT(*) FROM fact_transactions) + (SELECT COUNT(*) FROM quarantine_transactions) AS total_processed_rows;

-- TEST 2: Referential Integrity Check (Must ideally return 0 orphan rows)
SELECT
    'TEST 2: Orphan Foreign Keys' AS test_name,
    COUNT(*) AS failed_rows,
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS status
FROM fact_transactions f
LEFT JOIN dim_client c ON f.client_key = c.client_key
LEFT JOIN dim_advisor a ON f.advisor_key = a.advisor_key
LEFT JOIN dim_asset ast ON f.asset_key = ast.asset_key
LEFT JOIN dim_date d ON f.date_key = d.date_key
WHERE c.client_key IS NULL
   OR a.advisor_key IS NULL
   OR ast.asset_key IS NULL
   OR d.date_key IS NULL;

-- TEST 3: Financial Arithmetic Reconciliation (Gross vs Fee vs Net)
SELECT
    'TEST 3: Net Amount Arithmetic Integrity' AS test_name,
    COUNT(*) AS failed_rows,
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS status
FROM fact_transactions
WHERE (transaction_type = 'BUY' AND net_amount <> gross_amount + fee_amount)
   OR (transaction_type = 'SELL' AND net_amount <> gross_amount - fee_amount)
   OR (transaction_type = 'DIVIDEND' AND net_amount <> gross_amount);

---TEST 4: Cross-View AUM Reconciliation (Ensuring View 1 and View 2 sum to identical Net AUM)
SELECT
    'TEST 4: Cross-View Net AUM Consistency' AS test_name,
    (SELECT SUM(net_aum_zar) FROM vw_aum_by_advisor_and_risk) AS advisor_view_aum,
    (SELECT SUM(net_cash_flow_zar) FROM vw_monthly_net_flows) AS monthly_view_aum,
    CASE
        WHEN (SELECT SUM(net_aum_zar) FROM vw_aum_by_advisor_and_risk) =
             (SELECT SUM(net_cash_flow_zar) FROM vw_monthly_net_flows)
        THEN 'PASS'
        ELSE 'FAIL'
    END AS status;

-- -TEST 5: Quarantine Breakdown Report (Audit Evidence)
SELECT
    error_reason,
    COUNT(*) AS rejected_count
FROM quarantine_transactions
GROUP BY error_reason
ORDER BY rejected_count DESC;