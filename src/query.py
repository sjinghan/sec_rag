"""
Query pipeline for SEC filings. 
Parses the user query for filters (ticker, year, metric), retrives relevant chunks from ChromaDB, optionally pulls structured financials from Postgres, and generates the answer via ollama. 
"""

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

BALANCE_SHEET_METRICS = {"total_assets", "total_liabilities", "shareholders_equity", "cash"}

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

SYSTEM_PROMPT = """You are a financial research assistant. Answer the user's question using ONLY the provided sources.
 
Rules:
- Base your answer strictly on the provided sources.
- If STRUCTURED DATA is provided, use it for precise numerical answers.
- Cite your sources using the bracket notation, e.g. [AAPL 10-K 2025-10-31 - Risk Factors].
- For structured data, cite as [SEC XBRL Data].
- If the sources do not contain enough information to answer, say so explicitly.
- Be precise and concise."""

# Query parsing

def extract_ticker(query):
    # Match company names in the query to a ticker symbol
    # Sorted by length 
    
    query_lower = query.lower()
    for alias, ticker in sorted(COMPANY_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in query_lower:
            return ticker
    return None

def extract_year(query):
    """Pull the most recent 4-digit year from the query."""
    matches = re.findall(r"\b(20\d{2})\b", query)
    return matches[-1] if matches else None

def detect_metric(query):
    # Identify which financial metric the query is asking about, if any
    query_lower = query.lower()
    for metric_name, keywords in METRIC_KEYWORDS.items():
        if any(kw in query_lower for kw in keywords):
            return metric_name
    return None

# Data retrieval

def query_financials(ticker, metric_name, year=None, period_type="annual"):
    # Look up a structured financial metric.
    # Balance sheet metrics ignore period_type — the most recent point-in-time
    # value is always preferred regardless of whether it came from a 10-K or 10-Q.
    if metric_name in BALANCE_SHEET_METRICS:
        period_type = None

    conn = get_connection()
    cur = conn.cursor()

    sql = """
        SELECT fiscal_period_end, value, unit, period_type
        FROM financial_metrics
        WHERE ticker = %s AND metric_name = %s
    """
    params = [ticker, metric_name]

    if year:
        sql += " AND EXTRACT(YEAR FROM fiscal_period_end) = %s"
        params.append(int(year))

    if period_type:
        sql += " AND (period_type = %s OR period_type IS NULL)"
        params.append(period_type)
        sql += """
            ORDER BY
                CASE
                    WHEN period_type = %s THEN 0
                    WHEN period_type IS NULL THEN 1
                    ELSE 2
                END,
                fiscal_period_end DESC
            LIMIT 1
        """
        params.append(period_type)
    else:
        sql += " ORDER BY fiscal_period_end DESC LIMIT 1"
 
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close()
    conn.close()
 
    if not row:
        return None
 
    return {
        "fiscal_period_end": str(row[0]),
        "value": float(row[1]),
        "unit": row[2],
        "period_type": row[3],
        "metric_name": metric_name,
        "ticker": ticker,
    }
    
def retrieve(query, ticker=None, year=None):
    # Semantic search over ChromaDB for relevant filing chunks
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(COLLECTION_NAME)
 
    query_embedding = ollama.embed(model=EMBEDDING_MODEL, input=query)["embeddings"][0]
 
    where = build_where_filter(ticker, year)
    kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": TOP_K,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where
 
    return collection.query(**kwargs)

def build_where_filter(ticker, year):
    # Construct a ChromaDB where filter from optional ticker and year
    conditions = []
    if ticker:
        conditions.append({"ticker": ticker})
    if year:
        conditions.append({"filing_year": year})
 
    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}

# Response Generation

def format_metric(metric):
    # Human-readable formatting for a financial metric value
    value, unit = metric["value"], metric["unit"]
    if unit == "USD/share":
        return f"${value:.2f} per share"
    if abs(value) >= 1e9:
        return f"${value / 1e9:.1f} billion"
    if abs(value) >= 1e6:
        return f"${value / 1e6:.1f} million"
    return f"${value:,.0f}"
 
 
def build_prompt(query, results, financial_data=None):
    # Assemble the prompt from retrieved sources and optional structured data
    
    context_parts = []
 
    if financial_data:
        formatted = format_metric(financial_data)
        context_parts.append(
            f"STRUCTURED DATA: {financial_data['ticker']} "
            f"{financial_data['metric_name'].replace('_', ' ')} "
            f"for fiscal period ending {financial_data['fiscal_period_end']}: {formatted} "
            f"(Source: SEC XBRL filing data)"
        )
 
    for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
        citation = f"[{meta['ticker']} {meta['filing_type']} {meta['filing_date']} - {meta['section']}]"
        context_parts.append(f"Source {i + 1} {citation}:\n{doc}")
 
    context = "\n\n---\n\n".join(context_parts)
    return f"{SYSTEM_PROMPT}\n\nSources:\n{context}\n\nQuestion: {query}\n\nAnswer:"

def generate_answer(prompt):
    response = ollama.chat(
        model=GENERATION_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"]

# Orchestration

def ask(query):
    # full rag pipeline: parse query -> retrieve -> generate answer
    ticker = extract_ticker(query)
    year = extract_year(query)
 
    filters = []
    if ticker:
        filters.append(f"company={ticker}")
    if year:
        filters.append(f"year={year}")
    print(f"Filters: {', '.join(filters) if filters else 'none'}")
 
    financial_data = None
    metric = detect_metric(query)
    if metric and ticker:
        financial_data = query_financials(ticker, metric, year)
        if financial_data:
            print(f"Financial data: {metric} = {format_metric(financial_data)} "
                  f"(period: {financial_data['fiscal_period_end']})")
 
    results = retrieve(query, ticker, year)
    
    print(f"Retrieved {len(results['documents'][0])} chunks:")
    for i, meta in enumerate(results["metadatas"][0]):
        print(f"  {i + 1}. {meta['ticker']} | {meta['filing_type']} | "
              f"{meta['filing_date']} | {meta['section']}")
 
    prompt = build_prompt(query, results, financial_data)
    answer = generate_answer(prompt)
 
    return answer, results, financial_data
