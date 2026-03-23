import time
import re
import ollama
import chromadb
from edgar import set_identity, Company
from src.config import TARGET_TICKERS, FILING_TYPES, YEARS_BACK, TARGET_SECTIONS, TENK_SECTION_MAP, TENQ_SECTION_MAP

set_identity("YourName your.email@example.com")

CHROMA_PATH = "data/chroma_db"
COLLECTION_NAME = "sec_filings"
EMBEDDING_MODEL = "nomic-embed-text"
MIN_CHUNK_LENGTH = 50
MAX_CHUNK_LENGTH = 2000

def get_section_text(filing_obj, section_name, filing_type):
    if filing_type == "10-K":
        prop = TENK_SECTION_MAP.get(section_name)
        if prop and hasattr(filing_obj, prop):
            text = getattr(filing_obj, prop)
            if text:
                return str(text)
    elif filing_type == "10-Q":
        item_key = TENQ_SECTION_MAP.get(section_name)
        if item_key:
            try:
                text = filing_obj[item_key]
                if text:
                    return str(text)
            except Exception:
                return None
    return None

def chunk_section(text, section_name, min_length=MIN_CHUNK_LENGTH, max_length=MAX_CHUNK_LENGTH):
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) > max_length and len(current_chunk) >= min_length:
            chunks.append(current_chunk.strip())
            current_chunk = para
        else:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para

    if current_chunk.strip() and len(current_chunk.strip()) >= min_length:
        chunks.append(current_chunk.strip())

    return chunks


def embed_text(text):
    response = ollama.embed(model=EMBEDDING_MODEL, input=text)
    return response["embeddings"][0]


def ingest():
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    try:
        client.delete_collection(name=COLLECTION_NAME)
        print(f"Deleted existing collection '{COLLECTION_NAME}'")
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    total_chunks = 0
    failed_tickers = []
    failed_filings = []

    for ticker in TARGET_TICKERS:
        print(f"\n{'='*60}")
        print(f"Processing {ticker}")
        print(f"{'='*60}")

        try:
            company = Company(ticker)
        except Exception as e:
            print(f"  ERROR: Could not find company {ticker}: {e}")
            failed_tickers.append(ticker)
            continue

        for filing_type in FILING_TYPES:
            try:
                filings = company.get_filings(form=filing_type)
            except Exception as e:
                print(f"  ERROR: Could not get {filing_type} filings for {ticker}: {e}")
                continue

            filing_count = 0

            for filing in filings:
                if filing_count >= YEARS_BACK:
                    break

                filing_date = str(filing.filing_date)
                filing_year = filing_date[:4]

                print(f"\n  {filing_type} | {filing_date}")

                try:
                    filing_obj = filing.obj()
                except Exception as e:
                    print(f"    ERROR: Could not parse filing: {e}")
                    failed_filings.append(f"{ticker} {filing_type} {filing_date}")
                    filing_count += 1
                    continue

                for section_name in TARGET_SECTIONS:
                    text = get_section_text(filing_obj, section_name, filing_type)
                    if not text:
                        print(f"    Section '{section_name}': not found")
                        continue

                    chunks = chunk_section(text, section_name)
                    print(f"    Section '{section_name}': {len(chunks)} chunks")

                    for i, chunk in enumerate(chunks):
                        chunk_id = f"{ticker}_{filing_type}_{filing_date}_{section_name}_{i}"
                        chunk_id = re.sub(r'[^a-zA-Z0-9_-]', '_', chunk_id)

                        try:
                            embedding = embed_text(chunk)
                        except Exception as e:
                            print(f"      ERROR embedding chunk {i}: {e}")
                            continue

                        collection.add(
                            ids=[chunk_id],
                            embeddings=[embedding],
                            documents=[chunk],
                            metadatas=[{
                                "ticker": ticker,
                                "company_name": company.name,
                                "filing_type": filing_type,
                                "filing_date": filing_date,
                                "filing_year": filing_year,
                                "section": section_name,
                                "chunk_index": i,
                            }]
                        )
                        total_chunks += 1

                filing_count += 1
                time.sleep(0.5)

    print(f"\n{'='*60}")
    print(f"INGESTION COMPLETE")
    print(f"Total chunks stored: {total_chunks}")
    if failed_tickers:
        print(f"Failed tickers: {failed_tickers}")
    if failed_filings:
        print(f"Failed filings: {failed_filings}")
    print(f"{'='*60}")