import csv
import os
from decimal import Decimal
import mysql.connector
from etl_pipeline import DB_CONFIG, RAW_DIR


def get_raw_metrics():
    with open(os.path.join(RAW_DIR, "transactions.csv"), mode="r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return len(rows)


def run_quality_checks():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    raw_tx_count = get_raw_metrics()

    cursor.execute("SELECT COUNT(*) FROM fact_transactions;")
    loaded_tx_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM quarantine_transactions;")
    quarantined_tx_count = cursor.fetchone()[0]

    # Check 1: Row-count reconciliation (Zero silent data loss)
    reconciled_total = loaded_tx_count + quarantined_tx_count
    assert raw_tx_count == reconciled_total, (
        f"Row count mismatch! Raw={raw_tx_count}, Loaded+Quarantined={reconciled_total}"
    )

    # Check 2: No duplicate transaction_ids in fact table
    cursor.execute("""
        SELECT COUNT(*) FROM (
            SELECT transaction_id FROM fact_transactions GROUP BY transaction_id HAVING COUNT(*) > 1
        ) dups;
    """)
    dup_count = cursor.fetchone()[0]
    assert dup_count == 0, f"Found {dup_count} duplicate transaction_ids in fact_transactions!"

    # Check 3: No negative or zero units/prices in fact table
    cursor.execute("SELECT COUNT(*) FROM fact_transactions WHERE units <= 0 OR unit_price <= 0;")
    invalid_num_count = cursor.fetchone()[0]
    assert invalid_num_count == 0, f"Found {invalid_num_count} non-positive values in fact_transactions!"

    # Check 4: Gross vs Net arithmetic integrity
    cursor.execute("""
        SELECT COUNT(*) FROM fact_transactions
        WHERE (transaction_type = 'BUY' AND net_amount != gross_amount + fee_amount)
           OR (transaction_type = 'SELL' AND net_amount != gross_amount - fee_amount)
           OR (transaction_type = 'DIVIDEND' AND net_amount != gross_amount);
    """)
    math_errors = cursor.fetchone()[0]
    assert math_errors == 0, f"Found {math_errors} financial calculation mismatches!"

    # Check 5: No blank risk_profiles remaining in dim_client
    cursor.execute("SELECT COUNT(*) FROM dim_client WHERE risk_profile IS NULL OR TRIM(risk_profile) = '';")
    blank_risk = cursor.fetchone()[0]
    assert blank_risk == 0, f"Found {blank_risk} blank risk_profile values in dim_client!"

    # Print breakdown of quarantined anomalies
    cursor.execute("""
        SELECT error_reason, COUNT(*)
        FROM quarantine_transactions
        GROUP BY error_reason
        ORDER BY COUNT(*) DESC;
    """)
    quarantine_summary = cursor.fetchall()

    print("=" * 60)
    print("AUTOMATED DATA QUALITY & RECONCILIATION REPORT: PASSED")
    print("=" * 60)
    print(f"Source Raw Transactions:      {raw_tx_count}")
    print(f"Loaded Valid Fact Rows:       {loaded_tx_count}")
    print(f"Quarantined Anomaly Rows:     {quarantined_tx_count}")
    print(f"Unaccounted Rows:             {raw_tx_count - reconciled_total}")
    print("-" * 60)
    print("Quarantine Breakdown by Rule:")
    for reason, cnt in quarantine_summary:
        print(f"  - [{cnt} rows] {reason}")
    print("=" * 60)

    cursor.close()
    conn.close()


if __name__ == "__main__":
    run_quality_checks()