import csv
import os
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import mysql.connector

# Database configuration (reads from environment variables with local defaults)
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),  # Set via env var or update locally before running
    "database": os.getenv("MYSQL_DB", "wealth_dw"),
}

RAW_DIR = os.path.join("data", "raw")
QUARANTINE_DIR = os.path.join("data", "quarantined")

MARTS_DIR = os.path.join("data", "marts")
os.makedirs(MARTS_DIR, exist_ok=True)

os.makedirs(QUARANTINE_DIR, exist_ok=True)


def read_csv(filename):
    filepath = os.path.join(RAW_DIR, filename)
    with open(filepath, mode="r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def reset_warehouse_tables(cursor):
    """Clears tables in FK-safe order to ensure idempotent pipeline runs."""
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    for table in [
        "fact_transactions",
        "quarantine_transactions",
        "dim_client",
        "dim_asset",
        "dim_advisor",
        "dim_date",
    ]:
        cursor.execute(f"TRUNCATE TABLE {table};")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")


def populate_dim_date(cursor, start_dt=date(2025, 1, 1), end_dt=date(2026, 12, 31)):
    """Generates a complete calendar dimension table."""
    sql = """
        INSERT INTO dim_date (
            date_key, full_date, day_of_week, month_num, month_name,
            quarter_num, year_num, is_weekend
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    rows = []
    curr = start_dt
    while curr <= end_dt:
        date_key = int(curr.strftime("%Y%m%d"))
        quarter = (curr.month - 1) // 3 + 1
        is_weekend = curr.weekday() >= 5
        rows.append((
            date_key,
            curr.isoformat(),
            curr.strftime("%A"),
            curr.month,
            curr.strftime("%B"),
            quarter,
            curr.year,
            is_weekend,
        ))
        curr += timedelta(days=1)

    cursor.executemany(sql, rows)
    print(f"[DIM_DATE] Loaded {len(rows)} calendar days.")


def load_dim_advisor(cursor, advisors_raw):
    sql = """
        INSERT INTO dim_advisor (advisor_id, advisor_name, region, branch, seniority_tier)
        VALUES (%s, %s, %s, %s, %s)
    """
    rows = [
        (r["advisor_id"].strip(), r["advisor_name"].strip(), r["region"].strip(), r["branch"].strip(), r["seniority_tier"].strip())
        for r in advisors_raw
    ]
    cursor.executemany(sql, rows)

    cursor.execute("SELECT advisor_id, advisor_key FROM dim_advisor;")
    lookup = dict(cursor.fetchall())
    print(f"[DIM_ADVISOR] Loaded {len(lookup)} advisors.")
    return lookup


def load_dim_asset(cursor, assets_raw):
    sql = """
        INSERT INTO dim_asset (asset_id, asset_name, asset_class, risk_rating, annual_fee_pct, currency)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    rows = []
    fee_lookup = {}
    for r in assets_raw:
        aid = r["asset_id"].strip()
        fee_pct = Decimal(r["annual_fee_pct"])
        fee_lookup[aid] = fee_pct
        rows.append((
            aid,
            r["asset_name"].strip(),
            r["asset_class"].strip(),
            int(r["risk_rating"]),
            fee_pct,
            r.get("currency", "ZAR").strip(),
        ))
    cursor.executemany(sql, rows)

    cursor.execute("SELECT asset_id, asset_key FROM dim_asset;")
    key_lookup = dict(cursor.fetchall())
    print(f"[DIM_ASSET] Loaded {len(key_lookup)} assets.")
    return key_lookup, fee_lookup


def load_dim_client(cursor, clients_raw):
    """Loads clients and imputes missing risk_profile values as 'Unassigned'."""
    sql = """
        INSERT INTO dim_client (
            client_id, full_name, email, risk_profile, client_segment, onboarding_date, advisor_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    rows = []
    imputed_count = 0
    client_advisor_map = {}

    for r in clients_raw:
        cid = r["client_id"].strip()
        risk = r["risk_profile"].strip()
        if not risk:
            risk = "Unassigned"
            imputed_count += 1

        adv_id = r["advisor_id"].strip()
        client_advisor_map[cid] = adv_id

        rows.append((
            cid,
            r["full_name"].strip(),
            r["email"].strip() or None,
            risk,
            r["client_segment"].strip(),
            r["onboarding_date"].strip(),
            adv_id,
        ))

    cursor.executemany(sql, rows)
    cursor.execute("SELECT client_id, client_key FROM dim_client;")
    key_lookup = dict(cursor.fetchall())
    print(f"[DIM_CLIENT] Loaded {len(key_lookup)} clients ({imputed_count} missing risk_profiles imputed to 'Unassigned').")
    return key_lookup, client_advisor_map


def validate_and_load_transactions(
    cursor,
    tx_raw,
    client_keys,
    client_advisor_map,
    advisor_keys,
    asset_keys,
    asset_fees,
):
    """Validates raw transactions, quarantines anomalies, and loads clean facts."""
    seen_tx_ids = set()
    valid_rows = []
    quarantined_rows = []
    valid_tx_types = {"BUY", "SELL", "DIVIDEND", "FEE"}

    for r in tx_raw:
        tx_id = r.get("transaction_id", "").strip()
        cid = r.get("client_id", "").strip()
        aid = r.get("asset_id", "").strip()
        tx_date_str = r.get("transaction_date", "").strip()
        tx_type = r.get("transaction_type", "").strip().upper()
        units_str = r.get("units", "").strip()
        price_str = r.get("unit_price", "").strip()

        errors = []

        # Rule 1: Duplicate Transaction ID
        if not tx_id:
            errors.append("Missing transaction_id")
        elif tx_id in seen_tx_ids:
            errors.append(f"Duplicate transaction_id: {tx_id}")

        # Rule 2: Referential Integrity (Client & Asset)
        if cid not in client_keys:
            errors.append(f"Orphan client_id: {cid}")
        if aid not in asset_keys:
            errors.append(f"Orphan asset_id: {aid}")

        # Rule 3: Valid Transaction Type
        if tx_type not in valid_tx_types:
            errors.append(f"Invalid transaction_type: {tx_type}")

        # Rule 4: Valid Numeric Values (Units > 0, Unit Price > 0)
        units = None
        unit_price = None
        try:
            units = Decimal(units_str)
            if units <= 0:
                errors.append(f"Non-positive units: {units}")
        except Exception:
            errors.append(f"Invalid numeric units: {units_str}")

        try:
            unit_price = Decimal(price_str)
            if unit_price <= 0:
                errors.append(f"Non-positive unit_price: {unit_price}")
        except Exception:
            errors.append(f"Invalid numeric unit_price: {price_str}")

        # Rule 5: Valid Date Format
        date_key = None
        try:
            parsed_date = datetime.strptime(tx_date_str, "%Y-%m-%d").date()
            date_key = int(parsed_date.strftime("%Y%m%d"))
        except ValueError:
            errors.append(f"Invalid date format: {tx_date_str}")

        # Route failed records to quarantine
        if errors:
            quarantined_rows.append({
                "raw_transaction_id": tx_id,
                "raw_client_id": cid,
                "raw_asset_id": aid,
                "raw_transaction_date": tx_date_str,
                "raw_transaction_type": tx_type,
                "raw_units": units_str,
                "raw_unit_price": price_str,
                "error_reason": "; ".join(errors),
            })
            continue

        # Mark ID as seen only after passing validation
        seen_tx_ids.add(tx_id)

        # Business Transformations
        gross_amount = (units * unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        fee_rate = Decimal("0.00") if tx_type == "DIVIDEND" else asset_fees[aid]
        fee_amount = (gross_amount * fee_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if tx_type == "BUY":
            net_amount = gross_amount + fee_amount
        elif tx_type == "SELL":
            net_amount = gross_amount - fee_amount
        else:
            net_amount = gross_amount

        advisor_id = client_advisor_map[cid]

        valid_rows.append((
            tx_id,
            date_key,
            client_keys[cid],
            advisor_keys[advisor_id],
            asset_keys[aid],
            tx_type,
            units,
            unit_price,
            gross_amount,
            fee_amount,
            net_amount,
        ))

    # Insert valid records into fact_transactions
    fact_sql = """
        INSERT INTO fact_transactions (
            transaction_id, date_key, client_key, advisor_key, asset_key,
            transaction_type, units, unit_price, gross_amount, fee_amount, net_amount
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.executemany(fact_sql, valid_rows)

    # Inserting the rejected records into quarantine_transactions table
    quarantine_sql = """
        INSERT INTO quarantine_transactions (
            raw_transaction_id, raw_client_id, raw_asset_id, raw_transaction_date,
            raw_transaction_type, raw_units, raw_unit_price, error_reason
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    q_tuples = [
        (
            q["raw_transaction_id"],
            q["raw_client_id"],
            q["raw_asset_id"],
            q["raw_transaction_date"],
            q["raw_transaction_type"],
            q["raw_units"],
            q["raw_unit_price"],
            q["error_reason"],
        )
        for q in quarantined_rows
    ]
    cursor.executemany(quarantine_sql, q_tuples)

    # Export quarantined rows to CSV for operational visibility
    q_csv_path = os.path.join(QUARANTINE_DIR, "rejected_transactions.csv")
    if quarantined_rows:
        with open(q_csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(quarantined_rows[0].keys()))
            writer.writeheader()
            writer.writerows(quarantined_rows)

    print(f"[FACT_TRANSACTIONS] Loaded {len(valid_rows)} valid transactions.")
    print(f"[QUARANTINE] Flagged {len(quarantined_rows)} anomalous rows -> DB & {q_csv_path}")

def export_analytical_marts(cursor):
    """Exports the 4 governed SQL views to CSV marts for Power BI consumption."""
    views = [
        "vw_aum_by_advisor_and_risk",
        "vw_monthly_net_flows",
        "vw_fee_revenue_by_asset_class",
        "vw_client_churn_and_anomaly_flags",
    ]
    for view_name in views:
        cursor.execute(f"SELECT * FROM {view_name};")
        rows = cursor.fetchall()
        headers = [col[0] for col in cursor.description]

        out_path = os.path.join(MARTS_DIR, f"{view_name}.csv")
        with open(out_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        print(f"[MARTS] Exported {out_path} ({len(rows)} rows)")

def run_etl():
    print("Starting Wealth Portfolio ETL Pipeline...")
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        reset_warehouse_tables(cursor)
        populate_dim_date(cursor)

        advisors_raw = read_csv("advisors.csv")
        assets_raw = read_csv("assets.csv")
        clients_raw = read_csv("clients.csv")
        tx_raw = read_csv("transactions.csv")

        advisor_keys = load_dim_advisor(cursor, advisors_raw)
        asset_keys, asset_fees = load_dim_asset(cursor, assets_raw)
        client_keys, client_advisor_map = load_dim_client(cursor, clients_raw)

        validate_and_load_transactions(
            cursor,
            tx_raw,
            client_keys,
            client_advisor_map,
            advisor_keys,
            asset_keys,
            asset_fees,
        )

        conn.commit()
        print("\nETL Pipeline completed and committed successfully.")
        export_analytical_marts(cursor)
    except Exception as e:
        conn.rollback()
        print(f"\nETL Pipeline failed! Transaction rolled back. Error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    run_etl()