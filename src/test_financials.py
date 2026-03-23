from edgar import set_identity, Company

set_identity("YourName your.email@example.com")

company = Company("AAPL")
filing = company.get_filings(form="10-K")[0]
obj = filing.obj()

cf = obj.financials.cash_flow_statement()
df = cf.to_dataframe()

print("=== Cash Flow Statement Labels ===")
for _, row in df.iterrows():
    dim = row['dimension']
    print(f"  {'[DIM] ' if dim else ''}{row['label']:55s} | {row['concept']}")
