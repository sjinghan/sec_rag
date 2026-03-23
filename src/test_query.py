from src.query import ask

queries = [
    "What was Apple's revenue in 2025?",
    "What is Nvidia's net income?",
    "What are Tesla's main risk factors?",
]

for query in queries:
    print(f"Question: {query}\n")
    answer, results, financial_data = ask(query)
    print(f"\nAnswer:\n{answer}")
    print(f"\n{'='*60}\n")