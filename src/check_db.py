import chromadb

client = chromadb.PersistentClient(path="data/chroma_db")
col = client.get_collection("sec_filings")
print(f"Total chunks: {col.count()}")

result = col.get(limit=5, include=["metadatas", "documents"])
for m, d in zip(result["metadatas"], result["documents"]):
    print(f"{m['ticker']} | {m['filing_type']} | {m['filing_date']} | {m['section']}")
    print(f"  {d[:120]}...")
    print()