"""Ingest filings (10-K, 10-Q) into ChromaDB. 

Fetch filing using edgartools, extracts target sections, chunks the text, embeds with ollama, and stores in a vector collection
"""

import time
import re
import ollama
import chromadb
from edgar import set_identity, Company
from src.config import (
    TARGET_TICKERS, FILING_TYPES, YEARS_BACK,
    TARGET_SECTIONS, TENK_SECTION_MAP, TENQ_SECTION_MAP,
)

set_identity("YourName your.email@example.com")

CHROMA_PATH = "data/chroma_db"
COLLECTION_NAME = "sec_filings"
EMBEDDING_MODEL = "nomic-embed-text"
MIN_CHUNK_LENGTH = 50
MAX_CHUNK_LENGTH = 2000
MAX_CHUNKS_PER_SECTION = 60

def get_section_text(filing_obj, section_name, filing_type):
    # extract a named section from a parsed filing. 
    # Returns None if not found
    if filing_type == "10-K":
        attr = TENK_SECTION_MAP.get(section_name)
        text = getattr(filing_obj, attr, None) if attr else None
        return str(text) if text else None
 
    if filing_type == "10-Q":
        for key in TENQ_SECTION_MAP.get(section_name, []):
            try:
                text = filing_obj[key]
                if text:
                    return str(text)
            except KeyError:
                continue
        return None
 
    return None

def chunk_text(text, min_length=MIN_CHUNK_LENGTH, max_length=MAX_CHUNK_LENGTH):
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, current = [], ""
 
    for para in paragraphs:
        if len(current) + len(para) > max_length and len(current) >= min_length:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
 
    if current and len(current) >= min_length:
        chunks.append(current)
 
    return chunks


def build_chunk_id(ticker, filing_type, filing_date, section_name, index):
    raw = f"{ticker}_{filing_type}_{filing_date}_{section_name}_{index}"
    return re.sub(r"[^a-zA-Z0-9_-]", "_", raw)
 
 
def process_filing(filing, ticker, company_name, filing_type, collection):
    """Parse one filing, chunk each section, embed and store. Returns chunk count."""
    filing_date = str(filing.filing_date)
 
    try:
        filing_obj = filing.obj()
    except Exception as e:
        print(f"    Could not parse filing: {e}")
        return 0
 
    chunk_count = 0
 
    for section_name in TARGET_SECTIONS:
        text = get_section_text(filing_obj, section_name, filing_type)
        if not text:
            print(f"    {section_name}: not found")
            continue
 
        chunks = chunk_text(text)
 
        if len(chunks) > MAX_CHUNKS_PER_SECTION:
            print(f"    {section_name}: {len(chunks)} chunks, capping at {MAX_CHUNKS_PER_SECTION}")
            chunks = chunks[:MAX_CHUNKS_PER_SECTION]
        else:
            print(f"    {section_name}: {len(chunks)} chunks")
 
        for i, chunk in enumerate(chunks):
            try:
                embedding = ollama.embed(model=EMBEDDING_MODEL, input=chunk)["embeddings"][0]
            except Exception as e:
                print(f"    Failed to embed chunk {i} in {section_name}: {e}")
                continue
 
            collection.add(
                ids=[build_chunk_id(ticker, filing_type, filing_date, section_name, i)],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[{
                    "ticker": ticker,
                    "company_name": company_name,
                    "filing_type": filing_type,
                    "filing_date": filing_date,
                    "filing_year": filing_date[:4],
                    "section": section_name,
                    "chunk_index": i,
                }],
            )
            chunk_count += 1
 
    return chunk_count
 
 
def ingest():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
 
    try:
        client.delete_collection(name=COLLECTION_NAME)
        print(f"Cleared existing collection '{COLLECTION_NAME}'")
    except Exception:
        # Collection may not exist on first run
        print(f"No existing collection to clear, starting fresh")
 
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
 
    total_chunks = 0
    skipped = []
 
    for ticker in TARGET_TICKERS:
        print(f"\n{'=' * 60}\nProcessing {ticker}\n{'=' * 60}")
 
        try:
            company = Company(ticker)
        except Exception as e:
            print(f"  Could not find company: {e}")
            skipped.append(ticker)
            continue
 
        for filing_type in FILING_TYPES:
            try:
                filings = company.get_filings(form=filing_type)
            except Exception as e:
                print(f"  Could not fetch {filing_type} filings: {e}")
                continue
 
            for i, filing in enumerate(filings):
                if i >= YEARS_BACK:
                    break
 
                print(f"\n  {filing_type} | {filing.filing_date}")
                total_chunks += process_filing(
                    filing, ticker, company.name, filing_type, collection,
                )
                time.sleep(0.5)
 
    print(f"\n{'=' * 60}")
    print(f"Ingestion complete — {total_chunks} chunks stored")
    if skipped:
        print(f"Skipped tickers: {skipped}")
    print(f"{'=' * 60}")
 
 
if __name__ == "__main__":
    ingest()