# Data Dictionary & Governance Rules (`wealth_dw`)

## 1. Data Lineage Overview
```text
[Raw CSV Extracts] ──► [Python Quality Gate] ──► [MySQL Star Schema] ──► [Semantic Views] ──► [Power BI Marts]
 (data/raw/*.csv)       │ (src/etl_pipeline.py)     (wealth_dw)          (02_analytical_views)   (data/marts/*.csv)
                        ▼
               [Quarantine Layer]
            (quarantine_transactions +
             rejected_transactions.csv)
```
## 2.Dimension Tables (dim_date, dim_advisor, dim client, dim_assest)      
Calender dimension supportinmg time-series rollups, quater/month reporting and weekend filtering
dim date

Column               Data Type               Constraint               Description 
date_key             INT                     PRIMARY KEY              Smart surrogate key formatted as YYYYMMDD (e.g., 20261120).full_date            DATE                    NOT NULL, UNIQUE         Standard ISO calendar date (YYYY-MM-DD).
day_of_week          VARCHAR(15)             NOT NULL                 Full weekday name (Monday – Sunday).
month_num            INT                     NOT NULL                 Calendar month number (1 – 12).
month_name           VARCHAR(15)             NOT NULL                 Full month name (January – December).
quarter_num          INT                     NOT NULL                 Calendar quarter (1 – 4).
year_num             INT                     NOT NULL                 Four-digit calendar year. 
is_weekend           BOOLEAN                 NOT NULL                 TRUE (1) for Saturday/Sunday, FALSE (0) otherwise.


Wealth management advisors and regional branch hierarchy.
dim_advisor

Column               Data Type               Constraint                 Description
advisor_key          INT                     PRIMARY KEY,AUTO_INCREMENT Warehouse surrogate key.
advisor_id           VARCHAR(20)             NOT NULL, UNIQUE           Business natural key from CRM (e.g., ADV001).
advisor_name         VARCHAR(100)            NOT NULL                   Advisor full name.
region               VARCHAR(50)             NOT NULL                   South African operating province (Western Cape, Gauteng, KZN).branch               VARCHAR(50)             NOT NULL                   Local wealth advisory branch office.
seniority_tier       VARCHAR(30)             NOT NULL                   Advisory rank (Associate, Senior, Principal)
loaded_at            TIMESTAMP               DEFAULT, CURRENT_TIMESTAMP Record load audit timestamp.


Investor master data, KYC risk classification and primary advispr
dim_client

Column               Data Type               Constraint                   Description
client_key	         INT	                 PRIMARY KEY, AUTO_INCREMENT  Warehouse surrogate key.
client_id	         VARCHAR(20)	         NOT NULL, UNIQUE	          Business natural key from CRM (e.g., CLI0001).
full_name	         VARCHAR(100)	         NOT NULL	                  Client full legal name.
email	             VARCHAR(100)	         NULLABLE	                  Client contact email address.
risk_profile	     VARCHAR(30)	         NOT NULL	                  KYC risk appetite (Conservative, Moderate, Balanced,      
                                                                          Aggressive, or Unassigned if blank at source).
client_segment	     VARCHAR(30)	         NOT NULL	                  Wealth tier (Mass Affluent, High Net Worth, Private Wealth).
onboarding_date	     DATE	                 NOT NULL	                  Date client account was opened.
advisor_id	         VARCHAR(20)           	 NOT NULL	                  Natural key of assigned relationship advisor.
loaded_at	         TIMESTAMP	             DEFAULT CURRENT_TIMESTAMP	  Record load audit timestamp.


Investment funds, ETFs, and fee schedules denominated in ZAR.
dim_asset

Column               Data Type               Constraint                   Description
asset_key            INT                     PRIMARY KEY, AUTO_INCREMENT  Warehouse surrogate key.
asset_id             VARCHAR(20)             NOT NULL, UNIQUE             Business natural key (e.g., AST001).
asset_name           VARCHAR(100)            NOT NULL                     Fund or instrument name.
asset_class          VARCHAR(50)             NOT NULL                     Asset category (Equities, Offshore ETF, Multi-Asset,
                                                                          Fixed Income, Cash).
risk_rating          INT                     NOT NULL                     Fund volatility score (1 = Lowest risk to 5 = Highest risk).annual_fee_pct       DECIMAL(5,4)            NOT NULL                     Management fee rate expressed as decimal (e.g 0.0085 = 0.85%).currency             VARCHAR(10)             DEFAULT 'ZAR'                Reporting currency (ZAR).
loaded_at            TIMESTAMP               DEFAULT CURRENT_TIMESTAMP    Record load audit timestamp.


## 3. Fact & Governance Tables (fact_transactions, quarantine_transactions)

Grain:One row per validated client investment transaction.
fact_transactions 

Column               Data Type               Constraint                    Description
transaction_key      INT                     PRIMARY KEY, AUTO_INCREMENT   Warehouse surrogate key.
transaction_id       VARCHAR(30)             NOT NULL, UNIQUE              Source system transaction reference (e.g., TXN000001).
date_key             INT                     FK-> dim_date(date_key)       Transaction settlement/trade date key.
client_key           INT                     FK-> dim_client(client_key)   Foreign key to investor dimension.
advisor_key          INT                     FK-> dim_advisor(advisor_key) Foreign key to servicing advisor at load time.
asset_key            INT                     FK-> dim_asset(asset_key)     Foreign key to traded fund/asset.
transaction_type     VARCHAR(20)             NOT NULL                      Movement type (BUY, SELL, DIVIDEND, FEE).
units                DECIMAL(14,4)           NOT NULL                      Number of fund units transacted (must be > 0).unit_price           DECIMAL(14,2)           NOT NULL                      Price per unit in ZAR (must be > 0).
gross_amount         DECIMAL(16,2)           NOT NULL                      ROUND(units * unit_price, 2) in ZAR.
fee_amount           DECIMAL(14,2)           NOT NULL                      0.00 for DIVIDEND; otherwise ROUND(gross_amount *        
                                                                           annual_fee_pct, 2).
net_amount           DECIMAL(16,2)           NOT NULL                      gross + fee for BUY; gross - fee for SELL; 
                                                                           gross for DIVIDEND.
loaded_at            TIMESTAMP               DEFAULT CURRENT_TIMESTAMP     Record load audit timestamp.


Captures rejected raw transaction rows without halting batch ingestion or corrupting downstream AUM metrics.
quarantine_transactions

Column               Data Type               Description
quarantine_id        INT (PK)                Auto-increment audit identifier.
raw_*                VARCHAR(50)             Unmodified raw string values from source CSV for root-cause inspection.
error_reason         VARCHAR(255)            Semicolon-delimited list of failed validation rules.
quarantined_at       TIMESTAMP               Timestamp when record was rejected by the ETL quality gate.


## 4. Business Metric Definitions
-Net AUM (ZAR): sum(BUY gross + DIVIDEND gross) - sum(SELL gross)
-High Churn Risk: Clients whose cumulative redemptions (SELL) exceed total purchases (BUY).
-Moderate Churn Risk: Clients who have redeemed  >=50% of their cumulative purchases.
-KYC Governance Flag: Clients loaded with a blank risk_profile (standardized to 'Unassigned' to preserve referential integrity while surfacing compliance remediation).