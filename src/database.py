"""
Postgres connection and schema setup for structured financial data. 

Defines tables for companies,filings, and XBRL-sourced financial metrics, used alongside the vector store
"""


import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "dbname": "sec_rag",
    "user": "jinghansun",
    "password": "",
    "host": "localhost",
    "port": 5432,
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def create_tables():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            ticker VARCHAR(10) PRIMARY KEY,
            company_name VARCHAR(255) NOT NULL,
            sector VARCHAR(100)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS filings (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(10) REFERENCES companies(ticker),
            filing_type VARCHAR(10) NOT NULL,
            filing_date DATE NOT NULL,
            fiscal_period_end DATE,
            sections_found TEXT[],
            total_chunks INTEGER DEFAULT 0,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, filing_type, filing_date)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS financial_metrics (
            id SERIAL PRIMARY KEY,
            filing_id INTEGER REFERENCES filings(id),
            ticker VARCHAR(10) REFERENCES companies(ticker),
            fiscal_period_end DATE NOT NULL,
            metric_name VARCHAR(100) NOT NULL,
            xbrl_concept VARCHAR(255) NOT NULL,
            value NUMERIC,
            unit VARCHAR(50),
            UNIQUE(filing_id, metric_name, fiscal_period_end)
        );
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_filings_ticker ON filings(ticker);
        CREATE INDEX IF NOT EXISTS idx_filings_date ON filings(filing_date);
        CREATE INDEX IF NOT EXISTS idx_metrics_ticker ON financial_metrics(ticker);
        CREATE INDEX IF NOT EXISTS idx_metrics_name ON financial_metrics(metric_name);
        CREATE INDEX IF NOT EXISTS idx_metrics_period ON financial_metrics(fiscal_period_end);
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("Tables created successfully.")


if __name__ == "__main__":
    create_tables()