### 2. Operational Runbook (`docs/runbook.md`)

```markdown
# Operational Runbook: Wealth Portfolio Analytics Pipeline

## 1. Prerequisites & Environment Setup
* **Python:** 3.10+ with `mysql-connector-python` installed (`pip install -r requirements.txt`).
* **Database:** MySQL Server 8.0+ running locally on port `3306`.
* **BI Tool:** Power BI Desktop (Windows) for inspecting/refreshing `dashboard/wealth_overview.pbix`.

### Credentials Configuration
Create a `.env` file in the project root (ignored by Git via `.gitignore`) or set environment variables in your shell before execution:
```powershell
$env:MYSQL_HOST="localhost"
$env:MYSQL_PORT="3306"
$env:MYSQL_USER="root"
$env:MYSQL_PASSWORD="<your_mysql_password>"
$env:MYSQL_DB="wealth_dw"

2. Standard Execution Procedure
Step 1: Initialize Database Schema (First Run Only)
Execute sql/01_ddl_star_schema.sql and sql/02_analytical_views.sql in MySQL Workbench (or CLI) to create the wealth_dw star schema, quarantine table, and semantic reporting views.

Step 2: Generate Synthetic Raw Extracts on powershell (Optional Reset)

python src/generate_data.py

Expected Output: 4 CSV files written to data/raw/ (advisors.csv, assets.csv, clients.csv [60 rows], transactions.csv [516 rows including 16 injected anomalies]).

Step 3: Run ETL Pipeline & Mart Export

python src/etl_pipeline.py

Behavior: Idempotently truncates target tables in FK-safe order, populates dim_date (730 days) and master dimensions, routes invalid transactions to quarantine_transactions + data/quarantined/rejected_transactions.csv, loads clean facts into fact_transactions, and exports the 4 semantic views to data/marts/*.csv.

Step 4: Execute Automated QA & Reconciliation Gate

python src/quality_checks.py

Expected Output: Prints AUTOMATED DATA QUALITY & RECONCILIATION REPORT: 
PASSED confirming 516 Raw == 500 Valid + 16 Quarantined and zero arithmetic or referential errors.

(Optional SQL Audit): Run sql/03_reconciliation_tests.sql in MySQL Workbench to verify cross-view 
AUM consistency (PASS).


3. Troubleshooting & Known Operational Notes

Symptom / Error            Root Cause                Resolution
FileNotFoundError:         Script executed outside   cd to wealth-analytics-pipeline root 
data\raw\advisors.csv      repository root or prior  and run python src/generate_data.py
                           to data generation.

Error Code 1146:           Semantic views not yet    Execute sql/02_analytical_views.sql in
Table 'wealth_dw.vw_...'   created in MySQL          MySQL Workbench before running etl_pipeline.py.
doesn't exist.'  

Power BI DataFormat.Error  South African Windows     In Power Query, use Change Type 
on decimal column          regional settings expect  -> Using Locale...-> Decimal Number
                           comma (,) decimals while  (English (United States)) on currency
                           Python exports ISO dot.   columns only (exclude text IDs like advisor_id)
                           decimals.    
Pipeline failure mid-run   Database constraint or    etl_pipeline.py wraps loads in an 
                           connection interruption.  atomic transaction with conn.rollback() on 
                                                     exception; resolve the error and re-run safely.
