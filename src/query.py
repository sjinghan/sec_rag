import re
import ollama
import chromadb
from src.config import COMPANY_ALIASES
from src.database import get_connection

CHROMA_PATH = "data/chroma_db"
COLLECTION_NAME = "sec_filings"
EMBEDDING_MODEL = "nomic-embed-text"
GENERATION_MODEL = "llama3:8b-instruct-q4_0"
TOP_K = 5

METRIC_KEYWORDS = {
    "revenue": ["revenue", "sales", "top line"],
    "net_income": ["net income", "net profit", "bottom line", "earnings"],
    "operating_income": ["operating income", "operating profit"],
    "eps_diluted": ["eps", "earnings per share"],
    "total_assets": ["total assets", "assets"],
    "total_liabilities": ["total liabilities", "liabilities", "debt"],
    "shareholders_equity": ["shareholders equity", "shareholder equity", "book value", "equity"],
    "cash": ["cash", "cash position", "cash on hand"],
    "operating_cash_flow": ["operating cash flow", "cash flow from operations", "cash from operations"],
}


def extract_filters(query):
    query_lower = query.lower()
    ticker = None
    year = None

    for alias, mapped_ticker in sorted(COMPANY_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in query_lower:
            ticker = mapped_ticker
            break

    year_match = re.findall(r"\b(20[0-9]{2})\b", query)
    if year_match:
        year = year_match[-1]

    return ticker, year


def detect_metric(query):
    query_lower = query.lower()
    for metric_name, keywords in METRIC_KEYWORDS.items():
        for keyword in keywords:
            if keyword in query_lower:
                return metric_name
    return None


def query_financials(ticker, metric_name, year=None):
    conn = get_connection()
    cur = conn.cursor()

    if year:
        cur.execute("""
            SELECT fiscal_period_end, value, unit
            FROM financial_metrics
            WHERE ticker = %s AND metric_name = %s
            AND EXTRACT(YEAR FROM fiscal_period_end) = %s
            AND fiscal_period_end IN (
                SELECT MAX(fiscal_period_end)
                FROM financial_metrics
                WHERE ticker = %s AND metric_name = %s
                AND EXTRACT(YEAR FROM fiscal_period_end) = %s
            )
            LIMIT 1
        """, (ticker, metric_name, int(year), ticker, metric_name, int(year)))
    else:
        cur.execute("""
            SELECT fiscal_period_end, value, unit
            FROM financial_metrics
            WHERE ticker = %s AND metric_name = %s
            ORDER BY fiscal_period_end DESC
            LIMIT 1
        """, (ticker, metric_name))

    row = cur.fetchone()
    cur.close()
    conn.close()

    if row:
        return {
            "fiscal_period_end": str(row[0]),
            "value": float(row[1]),
            "unit": row[2],
            "metric_name": metric_name,
            "ticker": ticker,
        }
    return None


def format_metric_value(metric):
    value = metric["value"]
    unit = metric["unit"]
    if unit == "USD/share":
        return f"${value:.2f} per share"
    elif abs(value) >= 1e9:
        return f"${value/1e9:.1f} billion"
    elif abs(value) >= 1e6:
        return f"${value/1e6:.1f} million"
    else:
        return f"${value:,.0f}"


def build_where_filter(ticker, year):
    conditions = []
    if ticker:
        conditions.append({"ticker": ticker})
    if year:
        conditions.append({"filing_year": year})

    if len(conditions) == 0:
        return None
    elif len(conditions) == 1:
        return conditions[0]
    else:
        return {"$and": conditions}


def retrieve(query, ticker=None, year=None):
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(COLLECTION_NAME)

    query_embedding = ollama.embed(model=EMBEDDING_MODEL, input=query)["embeddings"][0]

    where_filter = build_where_filter(ticker, year)

    kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": TOP_K,
        "include": ["documents", "metadatas", "distances"],
    }
    if where_filter:
        kwargs["where"] = where_filter

    results = collection.query(**kwargs)
    return results


def build_prompt(query, results, financial_data=None):
    context_parts = []

    if financial_data:
        formatted = format_metric_value(financial_data)
        context_parts.append(
            f"STRUCTURED DATA: {financial_data['ticker']} {financial_data['metric_name'].replace('_', ' ')} "
            f"for fiscal period ending {financial_data['fiscal_period_end']}: {formatted} "
            f"(Source: SEC XBRL filing data)"
        )

    for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
        citation = f"[{meta['ticker']} {meta['filing_type']} {meta['filing_date']} - {meta['section']}]"
        context_parts.append(f"Source {i+1} {citation}:\n{doc}")

    context = "\n\n---\n\n".join(context_parts)

    prompt = f"""You are a financial research assistant. Answer the user's question using ONLY the provided sources.

Rules:
- Base your answer strictly on the provided sources.
- If STRUCTURED DATA is provided, use it for precise numerical answers.
- Cite your sources using the bracket notation, e.g. [AAPL 10-K 2025-10-31 - Risk Factors].
- For structured data, cite as [SEC XBRL Data].
- If the sources do not contain enough information to answer, say so explicitly.
- Be precise and concise.

Sources:
{context}

Question: {query}

Answer:"""

    return prompt


def generate_answer(prompt):
    response = ollama.chat(
        model=GENERATION_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"]


def ask(query):
    ticker, year = extract_filters(query)

    filter_info = []
    if ticker:
        filter_info.append(f"company={ticker}")
    if year:
        filter_info.append(f"year={year}")
    print(f"Filters applied: {', '.join(filter_info) if filter_info else 'none'}")

    financial_data = None
    metric = detect_metric(query)
    if metric and ticker:
        financial_data = query_financials(ticker, metric, year)
        if financial_data:
            formatted = format_metric_value(financial_data)
            print(f"Financial data found: {metric} = {formatted} (period: {financial_data['fiscal_period_end']})")

    results = retrieve(query, ticker, year)

    print(f"Retrieved {len(results['documents'][0])} chunks")
    for i, meta in enumerate(results["metadatas"][0]):
        print(f"  {i+1}. {meta['ticker']} | {meta['filing_type']} | {meta['filing_date']} | {meta['section']}")

    prompt = build_prompt(query, results, financial_data)
    answer = generate_answer(prompt)

    return answer, results, financial_data