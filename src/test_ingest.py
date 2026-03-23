from edgar import set_identity, Company
from src.ingest import get_section_text, chunk_section, embed_text
from src.config import TARGET_SECTIONS

set_identity("YourName your.email@example.com")

def test():
    print("=== Testing 10-K (Apple) ===")
    company = Company("AAPL")
    filing = company.get_filings(form="10-K")[0]
    print(f"Filing date: {filing.filing_date}")
    obj = filing.obj()

    for section in TARGET_SECTIONS:
        text = get_section_text(obj, section, "10-K")
        if not text:
            print(f"  {section}: NOT FOUND")
            continue
        chunks = chunk_section(text, section)
        print(f"  {section}: {len(text)} chars, {len(chunks)} chunks")

    print("\n=== Testing 10-Q (Apple) ===")
    filing = company.get_filings(form="10-Q")[0]
    print(f"Filing date: {filing.filing_date}")
    obj = filing.obj()

    for section in TARGET_SECTIONS:
        text = get_section_text(obj, section, "10-Q")
        if not text:
            print(f"  {section}: NOT FOUND")
            continue
        chunks = chunk_section(text, section)
        print(f"  {section}: {len(text)} chars, {len(chunks)} chunks")

    print("\nEmbed test...")
    text = get_section_text(Company("AAPL").get_filings(form="10-K")[0].obj(), "Risk Factors", "10-K")
    chunks = chunk_section(text, "Risk Factors")
    emb = embed_text(chunks[0])
    print(f"  Embedding dimension: {len(emb)}")
    print("\nAll tests passed.")

if __name__ == "__main__":
    test()