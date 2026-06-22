import re
from edgar import set_identity, Company
from src.database import get_connection
from src.config import TARGET_TICKERS, FILING_TYPES, YEARS_BACK

set_identity("YourName your.email@example.com")

METRICS = {
    "revenue": {
        "concept": "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
        "statement": "income_statement",
        "filter_dimension": True,
    },
    "operating_income": {
        "concept": "us-gaap_OperatingIncomeLoss",
        "statement": "income_statement",
        "filter_dimension": True,
    },
    "net_income": {
        "concept": "us-gaap_NetIncomeLoss",
        "statement": "income_statement",
        "filter_dimension": True,
    },
    "eps_diluted": {
        "concept": "us-gaap_EarningsPerShareDiluted",
        "statement": "income_statement",
        "filter_dimension": False,
    },
    "total_assets": {
        "concept": "us-gaap_Assets",
        "statement": "balance_sheet",
        "filter_dimension": False,
    },
    "total_liabilities": {
        "concept": "us-gaap_Liabilities",
        "statement": "balance_sheet",
        "filter_dimension": False,
    },
    "shareholders_equity": {
        "concept": "us-gaap_StockholdersEquity",
        "statement": "balance_sheet",
        "filter_dimension": True,
    },
    "cash": {
        "concept": "us-gaap_CashAndCashEquivalentsAtCarryingValue",
        "statement": "balance_sheet",
        "filter_dimension": True,
    },
    "operating_cash_flow": {
        "concept": "us-gaap_NetCashProvidedByUsedInOperatingActivities",
        "statement": "cash_flow_statement",
        "filter_dimension": False,
    },
}


def get_statement(financials, statement_name):
    try:
        method = getattr(financials, statement_name)
        return method()
    except Exception:
        return None


def extract_metrics_from_filing(filing_obj, period_type):
    financials = filing_obj.financials
    if not financials:
        return []

    # For quarterly filings, only extract balance sheet metrics.
    # Income statement and cash flow columns in a 10-Q represent the partial
    # period (e.g. 3-month Q3 revenue), which XBRL also reports alongside a
    # YTD figure under the same end date — we can't distinguish them from the
    # flattened dataframe, so we skip them entirely for 10-Qs.
    if period_type == "quarterly":
        statements_to_load = ["balance_sheet"]
    else:
        statements_to_load = ["income_statement", "balance_sheet", "cash_flow_statement"]

    statements = {}
    for statement_name in statements_to_load:
        stmt = get_statement(financials, statement_name)
        if stmt:
            try:
                statements[statement_name] = stmt.to_dataframe()
            except Exception:
                continue

    results = []

    for metric_name, config in METRICS.items():
        statement_name = config["statement"]
        if statement_name not in statements:
            continue

        df = statements[statement_name]
        rows = df[df["concept"] == config["concept"]]

        if config["filter_dimension"]:
            rows = rows[rows["dimension"] == False]

        if rows.empty:
            continue

        row = rows.iloc[0]

        date_columns = [col for col in df.columns if col.startswith("20")]

        for period in date_columns:
            value = row.get(period)
            if value is not None and str(value) != "nan":
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    continue

                date_match = re.match(r'\d{4}-\d{2}-\d{2}', period)
                if not date_match:
                    continue
                clean_date = date_match.group(0)

                unit = "USD"
                if "per_share" in metric_name or "eps" in metric_name:
                    unit = "USD/share"

                results.append({
                    "metric_name": metric_name,
                    "xbrl_concept": config["concept"],
                    "fiscal_period_end": clean_date,
                    "value": value,
                    "unit": unit,
                    "period_type": period_type,
                })

    return results


def run_extraction():
    conn = get_connection()
    cur = conn.cursor()

    total_metrics = 0
    failed = []

    for ticker in TARGET_TICKERS:
        print(f"\n{'='*60}")
        print(f"Processing {ticker}")
        print(f"{'='*60}")

        try:
            company = Company(ticker)
        except Exception as e:
            print(f"  ERROR: Could not find company {ticker}: {e}")
            failed.append(ticker)
            continue

        cur.execute(
            "INSERT INTO companies (ticker, company_name) VALUES (%s, %s) ON CONFLICT (ticker) DO NOTHING",
            (ticker, company.name)
        )

        for filing_type in FILING_TYPES:
            try:
                filings = company.get_filings(form=filing_type)
            except Exception as e:
                print(f"  ERROR: Could not get {filing_type} filings: {e}")
                continue

            count = 0
            for filing in filings:
                if count >= YEARS_BACK:
                    break

                filing_date = str(filing.filing_date)
                print(f"\n  {filing_type} | {filing_date}")

                try:
                    filing_obj = filing.obj()
                except Exception as e:
                    print(f"    ERROR parsing filing: {e}")
                    count += 1
                    continue

                period_of_report = str(filing.period_of_report) if filing.period_of_report else filing_date

                cur.execute(
                    """INSERT INTO filings (ticker, filing_type, filing_date, fiscal_period_end)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (ticker, filing_type, filing_date) DO UPDATE
                       SET fiscal_period_end = EXCLUDED.fiscal_period_end
                       RETURNING id""",
                    (ticker, filing_type, filing_date, period_of_report)
                )
                filing_id = cur.fetchone()[0]

                period_type = "annual" if filing_type == "10-K" else "quarterly"
                metrics = extract_metrics_from_filing(filing_obj, period_type)
                print(f"    Extracted {len(metrics)} metric values ({period_type})")

                for m in metrics:
                    try:
                        cur.execute(
                            """INSERT INTO financial_metrics
                               (filing_id, ticker, fiscal_period_end, metric_name, xbrl_concept, value, unit, period_type)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                               ON CONFLICT (filing_id, metric_name, fiscal_period_end, period_type) DO UPDATE
                               SET value = EXCLUDED.value""",
                            (filing_id, ticker, m["fiscal_period_end"], m["metric_name"],
                             m["xbrl_concept"], m["value"], m["unit"], m["period_type"])
                        )
                        total_metrics += 1
                    except Exception as e:
                        print(f"    ERROR storing metric {m['metric_name']}: {e}")

                conn.commit()
                count += 1

    print(f"\n{'='*60}")
    print(f"EXTRACTION COMPLETE")
    print(f"Total metric values stored: {total_metrics}")
    if failed:
        print(f"Failed tickers: {failed}")
    print(f"{'='*60}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    run_extraction()