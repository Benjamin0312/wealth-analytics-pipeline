-- Purpose: Governed semantic views for Power BI and stakeholder reporting

USE wealth_dw;


-- VIEW 1: Assets Under Management (AUM) & Book Performance by Advisor & Risk Tier

CREATE OR REPLACE VIEW vw_aum_by_advisor_and_risk AS
SELECT
    a.advisor_id,
    a.advisor_name,
    a.region,
    a.branch,
    a.seniority_tier,
    c.risk_profile,
    c.client_segment,
    COUNT(DISTINCT c.client_key) AS active_clients,
    COUNT(f.transaction_key) AS total_transactions,
    ROUND(SUM(CASE WHEN f.transaction_type IN ('BUY', 'DIVIDEND') THEN f.gross_amount ELSE 0 END), 2) AS total_inflows_zar,
    ROUND(SUM(CASE WHEN f.transaction_type = 'SELL' THEN f.gross_amount ELSE 0 END), 2) AS total_outflows_zar,
    ROUND(SUM(
        CASE
            WHEN f.transaction_type IN ('BUY', 'DIVIDEND') THEN f.gross_amount
            WHEN f.transaction_type = 'SELL' THEN -f.gross_amount
            ELSE 0
        END
    ), 2) AS net_aum_zar,
    ROUND(SUM(f.fee_amount), 2) AS total_fees_generated_zar
FROM fact_transactions f
JOIN dim_advisor a ON f.advisor_key = a.advisor_key
JOIN dim_client c ON f.client_key = c.client_key
GROUP BY
    a.advisor_id,
    a.advisor_name,
    a.region,
    a.branch,
    a.seniority_tier,
    c.risk_profile,
    c.client_segment;



-- VIEW 2: Monthly Net Cash Flows & Cumulative AUM Trend

CREATE OR REPLACE VIEW vw_monthly_net_flows AS
WITH monthly_summary AS (
    SELECT
        d.year_num,
        d.month_num,
        d.month_name,
        DATE_FORMAT(d.full_date, '%Y-%m') AS year_month_label,
        ROUND(SUM(CASE WHEN f.transaction_type = 'BUY' THEN f.gross_amount ELSE 0 END), 2) AS gross_inflows_zar,
        ROUND(SUM(CASE WHEN f.transaction_type = 'SELL' THEN f.gross_amount ELSE 0 END), 2) AS gross_outflows_zar,
        ROUND(SUM(CASE WHEN f.transaction_type = 'DIVIDEND' THEN f.gross_amount ELSE 0 END), 2) AS reinvested_dividends_zar,
        ROUND(SUM(
            CASE
                WHEN f.transaction_type IN ('BUY', 'DIVIDEND') THEN f.gross_amount
                WHEN f.transaction_type = 'SELL' THEN -f.gross_amount
                ELSE 0
            END
        ), 2) AS net_cash_flow_zar,
        ROUND(SUM(f.fee_amount), 2) AS monthly_fee_revenue_zar
    FROM fact_transactions f
    JOIN dim_date d ON f.date_key = d.date_key
    GROUP BY d.year_num, d.month_num, d.month_name, DATE_FORMAT(d.full_date, '%Y-%m')
)
SELECT
    year_num,
    month_num,
    month_name,
    year_month_label,
    gross_inflows_zar,
    gross_outflows_zar,
    reinvested_dividends_zar,
    net_cash_flow_zar,
    monthly_fee_revenue_zar,
    ROUND(SUM(net_cash_flow_zar) OVER (ORDER BY year_num, month_num), 2) AS cumulative_aum_zar
FROM monthly_summary
ORDER BY year_num, month_num;

-- VIEW 3: Fee Revenue & Trading Volume Breakdown by Asset Class

CREATE OR REPLACE VIEW vw_fee_revenue_by_asset_class AS
SELECT
    ast.asset_class,
    ast.asset_name,
    ast.risk_rating,
    ast.annual_fee_pct,
    COUNT(f.transaction_key) AS transaction_count,
    ROUND(SUM(f.units), 4) AS total_units_traded,
    ROUND(SUM(f.gross_amount), 2) AS gross_volume_zar,
    ROUND(SUM(f.fee_amount), 2) AS total_fee_revenue_zar,
    ROUND(
        (SUM(f.fee_amount) / NULLIF(SUM(SUM(f.fee_amount)) OVER (), 0)) * 100,
        2
    ) AS pct_of_total_fees
FROM fact_transactions f
JOIN dim_asset ast ON f.asset_key = ast.asset_key
GROUP BY
    ast.asset_class,
    ast.asset_name,
    ast.risk_rating,
    ast.annual_fee_pct
ORDER BY total_fee_revenue_zar DESC;



---VIEW 4: Identifies high risk churn signals

CREATE OR REPLACE VIEW vw_client_churn_and_anomaly_flags AS
WITH client_activity AS (
    SELECT
        c.client_id,
        c.full_name AS client_name,
        c.risk_profile,
        c.client_segment,
        a.advisor_name,
        a.region,
        ROUND(SUM(CASE WHEN f.transaction_type = 'BUY' THEN f.gross_amount ELSE 0 END), 2) AS total_bought_zar,
        ROUND(SUM(CASE WHEN f.transaction_type = 'SELL' THEN f.gross_amount ELSE 0 END), 2) AS total_sold_zar,
        MAX(d.full_date) AS last_transaction_date
    FROM dim_client c
    JOIN dim_advisor a ON c.advisor_id = a.advisor_id
    LEFT JOIN fact_transactions f ON c.client_key = f.client_key
    LEFT JOIN dim_date d ON f.date_key = d.date_key
    GROUP BY
        c.client_id,
        c.full_name,
        c.risk_profile,
        c.client_segment,
        a.advisor_name,
        a.region
)
SELECT
    client_id,
    client_name,
    risk_profile,
    client_segment,
    advisor_name,
    region,
    total_bought_zar,
    total_sold_zar,
    (total_bought_zar - total_sold_zar) AS net_position_zar,
    last_transaction_date,
    CASE
        WHEN total_sold_zar > total_bought_zar THEN 'HIGH CHURN RISK - Net Outflow'
        WHEN total_bought_zar > 0 AND (total_sold_zar / total_bought_zar) >= 0.50 THEN 'MODERATE CHURN RISK - >50% Redeemed'
        WHEN risk_profile = 'Unassigned' THEN 'GOVERNANCE FLAG - Missing KYC Risk Profile'
        ELSE 'HEALTHY'
    END AS status_flag
FROM client_activity
ORDER BY total_sold_zar DESC;