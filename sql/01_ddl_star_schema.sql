-- Domain: Wealth Management Portfolio Analytics

CREATE DATABASE IF NOT EXISTS wealth_dw;
USE wealth_dw;


--1. DIMENSION TABLES

CREATE TABLE IF NOT EXISTS dim_date (
    date_key INT PRIMARY KEY,          
    full_date DATE NOT NULL UNIQUE,
    day_of_week VARCHAR(15) NOT NULL,
    month_num INT NOT NULL,
    month_name VARCHAR(15) NOT NULL,
    quarter_num INT NOT NULL,
    year_num INT NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_advisor (
    advisor_key INT AUTO_INCREMENT PRIMARY KEY,
    advisor_id VARCHAR(20) NOT NULL UNIQUE,
    advisor_name VARCHAR(100) NOT NULL,
    region VARCHAR(50) NOT NULL,
    branch VARCHAR(50) NOT NULL,
    seniority_tier VARCHAR(30) NOT NULL,    
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dim_client (
    client_key INT AUTO_INCREMENT PRIMARY KEY,
    client_id VARCHAR(20) NOT NULL UNIQUE,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100),
    risk_profile VARCHAR(30) NOT NULL,      
    client_segment VARCHAR(30) NOT NULL,    
    onboarding_date DATE NOT NULL,
    advisor_id VARCHAR(20) NOT NULL,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dim_asset (
    asset_key INT AUTO_INCREMENT PRIMARY KEY,
    asset_id VARCHAR(20) NOT NULL UNIQUE,
    asset_name VARCHAR(100) NOT NULL,
    asset_class VARCHAR(50) NOT NULL,        
    risk_rating INT NOT NULL,                
    annual_fee_pct DECIMAL(5, 4) NOT NULL,   
    currency VARCHAR(10) DEFAULT 'ZAR',
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


--2.FACT TABLE

CREATE TABLE IF NOT EXISTS fact_transactions (
    transaction_key INT AUTO_INCREMENT PRIMARY KEY,
    transaction_id VARCHAR(30) NOT NULL UNIQUE,
    date_key INT NOT NULL,
    client_key INT NOT NULL,
    advisor_key INT NOT NULL,
    asset_key INT NOT NULL,
    transaction_type VARCHAR(20) NOT NULL, 
    units DECIMAL(14, 4) NOT NULL,
    unit_price DECIMAL(14, 2) NOT NULL,
    gross_amount DECIMAL(16, 2) NOT NULL,
    fee_amount DECIMAL(14, 2) NOT NULL,
    net_amount DECIMAL(16, 2) NOT NULL,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_fact_date FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    CONSTRAINT fk_fact_client FOREIGN KEY (client_key) REFERENCES dim_client(client_key),
    CONSTRAINT fk_fact_advisor FOREIGN KEY (advisor_key) REFERENCES dim_advisor(advisor_key),
    CONSTRAINT fk_fact_asset FOREIGN KEY (asset_key) REFERENCES dim_asset(asset_key)
);

-- Indexes for analytical query performance
CREATE INDEX idx_fact_date ON fact_transactions(date_key);
CREATE INDEX idx_fact_client ON fact_transactions(client_key);
CREATE INDEX idx_fact_advisor ON fact_transactions(advisor_key);
CREATE INDEX idx_fact_asset ON fact_transactions(asset_key);


--3.DATA QUALITY & GOVERNANCE (QUARANTINE)

CREATE TABLE IF NOT EXISTS quarantine_transactions (
    quarantine_id INT AUTO_INCREMENT PRIMARY KEY,
    raw_transaction_id VARCHAR(50),
    raw_client_id VARCHAR(50),
    raw_asset_id VARCHAR(50),
    raw_transaction_date VARCHAR(50),
    raw_transaction_type VARCHAR(50),
    raw_units VARCHAR(50),
    raw_unit_price VARCHAR(50),
    error_reason VARCHAR(255) NOT NULL,
    quarantined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);