from src.database import get_connection

conn = get_connection()
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM companies")
print(f"Companies: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM filings")
print(f"Filings: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM financial_metrics")
print(f"Metric values: {cur.fetchone()[0]}")

print("\n=== Apple Revenue by Period ===")
cur.execute("""
    SELECT fiscal_period_end, value
    FROM financial_metrics
    WHERE ticker = 'AAPL' AND metric_name = 'revenue'
    ORDER BY fiscal_period_end DESC
""")
for row in cur.fetchall():
    print(f"  {row[0]}: ${float(row[1])/1e9:.1f}B")

print("\n=== Latest Net Income by Company ===")
cur.execute("""
    SELECT ticker, fiscal_period_end, value
    FROM financial_metrics fm1
    WHERE metric_name = 'net_income'
    AND fiscal_period_end = (
        SELECT MAX(fiscal_period_end)
        FROM financial_metrics fm2
        WHERE fm2.ticker = fm1.ticker AND fm2.metric_name = 'net_income'
    )
    ORDER BY ticker
""")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} ${float(row[2])/1e9:.1f}B")

cur.close()
conn.close()