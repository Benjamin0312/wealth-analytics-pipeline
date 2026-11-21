import csv
import os
import random
from datetime import date, timedelta

#ensuring reproducibility
random.seed(42)

RAW_DIR = os.path.join("data", "raw")
os.makedirs(RAW_DIR, exist_ok=True)


def write_csv(filename, fieldnames, rows):
    filepath = os.path.join(RAW_DIR, filename)
    with open(filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {filepath} ({len(rows)} rows)")


def generate_advisors():
    advisors = [
        {"advisor_id": "ADV001", "advisor_name": "Thabo Mokoena", "region": "Western Cape", "branch": "Cape Town CBD", "seniority_tier": "Principal"},
        {"advisor_id": "ADV002", "advisor_name": "Sarah van der Merwe", "region": "Western Cape", "branch": "Claremont", "seniority_tier": "Senior"},
        {"advisor_id": "ADV003", "advisor_name": "Lerato Khumalo", "region": "Gauteng", "branch": "Sandton", "seniority_tier": "Principal"},
        {"advisor_id": "ADV004", "advisor_name": "Priya Naidoo", "region": "KwaZulu-Natal", "branch": "Umhlanga", "seniority_tier": "Senior"},
        {"advisor_id": "ADV005", "advisor_name": "David Botha", "region": "Gauteng", "branch": "Pretoria", "seniority_tier": "Associate"},
        {"advisor_id": "ADV006", "advisor_name": "Amina Patel", "region": "Western Cape", "branch": "Bellville", "seniority_tier": "Associate"},
    ]
    write_csv("advisors.csv", list(advisors[0].keys()), advisors)
    return advisors


def generate_assets():
    assets = [
        {"asset_id": "AST001", "asset_name": "SA Top 40 Equity ETF", "asset_class": "Equities", "risk_rating": 4, "annual_fee_pct": 0.0045, "currency": "ZAR"},
        {"asset_id": "AST002", "asset_name": "Global Developed Markets ETF", "asset_class": "Offshore ETF", "risk_rating": 5, "annual_fee_pct": 0.0065, "currency": "ZAR"},
        {"asset_id": "AST003", "asset_name": "Balanced Multi-Asset Fund", "asset_class": "Multi-Asset", "risk_rating": 3, "annual_fee_pct": 0.0110, "currency": "ZAR"},
        {"asset_id": "AST004", "asset_name": "SA Government Bond Fund", "asset_class": "Fixed Income", "risk_rating": 2, "annual_fee_pct": 0.0055, "currency": "ZAR"},
        {"asset_id": "AST005", "asset_name": "Enhanced Money Market Fund", "asset_class": "Cash", "risk_rating": 1, "annual_fee_pct": 0.0030, "currency": "ZAR"},
        {"asset_id": "AST006", "asset_name": "Property Income Unit Trust", "asset_class": "Multi-Asset", "risk_rating": 3, "annual_fee_pct": 0.0095, "currency": "ZAR"},
    ]
    write_csv("assets.csv", list(assets[0].keys()), assets)
    return assets


def generate_clients(advisors, num_clients=60):
    first_names = ["Sipho", "Naledi", "Johan", "Annelize", "Kagiso", "Zanele", "Rohan", "Fatima", "Michael", "Bongani", "Claire", "Tshepo"]
    last_names = ["Dlamini", "Nkosi", "Venter", "Pillay", "Mabena", "Pretorius", "Jacobs", "Mthembu", "Govender", "Sithole", "Meyer", "Ndlovu"]
    risk_profiles = ["Conservative", "Moderate", "Balanced", "Aggressive"]
    segments = ["Mass Affluent", "High Net Worth", "Private Wealth"]

    clients = []
    start_date = date(2022, 1, 1)

    for i in range(1, num_clients + 1):
        fname = random.choice(first_names)
        lname = random.choice(last_names)
        cid = f"CLI{i:04d}"
        onboard = start_date + timedelta(days=random.randint(0, 1000))

        # deliberate Anomaly: ~5% of the clients have a missing risk  profile
        risk = "" if random.random() < 0.05 else random.choice(risk_profiles)

        clients.append({
            "client_id": cid,
            "full_name": f"{fname} {lname}",
            "email": f"{fname.lower()}.{lname.lower()}{i}@example.co.za",
            "risk_profile": risk,
            "client_segment": random.choices(segments, weights=[0.55, 0.30, 0.15])[0],
            "onboarding_date": onboard.isoformat(),
            "advisor_id": random.choice(advisors)["advisor_id"],
        })

    write_csv("clients.csv", list(clients[0].keys()), clients)
    return clients


def generate_transactions(clients, assets, num_transactions=500):
    tx_types = ["BUY", "SELL", "DIVIDEND"]
    start_date = date(2025, 11, 1)
    end_date = date(2026, 11, 20)
    days_range = (end_date - start_date).days

    transactions = []
    for i in range(1, num_transactions + 1):
        tx_id = f"TXN{i:06d}"
        client = random.choice(clients)
        asset = random.choice(assets)
        tx_date = start_date + timedelta(days=random.randint(0, days_range))
        tx_type = random.choices(tx_types, weights=[0.60, 0.25, 0.15])[0]

        units = round(random.uniform(5.0, 250.0), 4)
        unit_price = round(random.uniform(50.0, 1200.0), 2)

        transactions.append({
            "transaction_id": tx_id,
            "client_id": client["client_id"],
            "asset_id": asset["asset_id"],
            "transaction_date": tx_date.isoformat(),
            "transaction_type": tx_type,
            "units": units,
            "unit_price": unit_price,
        })

    # INJECTING DELIBERATE DATA QUALITY ANOMALIES
    # 1.Duplicate transaction IDs (5 records)
    for dup in transactions[:5]:
        transactions.append(dup.copy())

    # 2.Negative unit prices (4 records)
    for idx in [10, 45, 120, 310]:
        transactions[idx]["unit_price"] = -abs(transactions[idx]["unit_price"])

    # 3.Orphan client IDs (4 records referencing  clients that dont exist)
    for idx in [25, 88, 204, 412]:
        transactions[idx]["client_id"] = f"CLI99{idx}"

    # 4.Zero or negative units(4 records)
    for idx in [15, 199, 350]:
        transactions[idx]["units"] = 0.0

    random.shuffle(transactions)
    write_csv("transactions.csv", list(transactions[0].keys()), transactions)


if __name__ == "__main__":
    advisors = generate_advisors()
    assets = generate_assets()
    clients = generate_clients(advisors)
    generate_transactions(clients, assets)
    print("\nData generation complete")