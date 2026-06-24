# sec-rag

Local research assistant for SEC 10-K and 10-Q filings. It combines semantic search over filing sections with structured XBRL financial metrics so users can ask natural-language questions and get source-grounded answers.

## Problem

SEC filings are long and split across narrative disclosures, management commentary, and financial statements. `sec-rag` makes those filings searchable through a local RAG pipeline while using extracted XBRL data for precise numeric answers when available.

## What It Does

- Fetches 10-K and 10-Q filings for configured public companies.
- Extracts filing sections such as Risk Factors, MD&A, and Business.
- Chunks and embeds filing text with Ollama.
- Stores filing chunks and metadata in ChromaDB for semantic retrieval.
- Extracts selected XBRL financial metrics into Postgres.
- Answers questions with an Ollama LLM using retrieved sources and structured data.
- Provides a Streamlit UI and a JSONL batch evaluation runner.

## Architecture

```text
Filing text -> sections -> chunks -> embeddings -> ChromaDB -> retrieved context
XBRL financials -> metric extraction -> Postgres -> structured numeric context
```

`src/query.py` combines both paths. It detects a ticker, year, and financial metric from the user query, retrieves relevant filing chunks from ChromaDB, optionally pulls a precise metric from Postgres, and sends the combined context to the LLM.

## Tech Stack

- `edgartools`: SEC filing access and parsed filing objects
- `ChromaDB`: persistent vector store for filing chunks
- `Ollama`: local embeddings and answer generation
- `Postgres`: structured financial metric storage
- `Streamlit`: local web UI
- `psycopg2`: Postgres client

## Setup

Create a Python environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Install and start Ollama, then pull the required models:

```bash
ollama pull nomic-embed-text
ollama pull llama3:8b-instruct-q4_0
```

Create a local Postgres database named `sec_rag`, then create the tables:

```bash
createdb sec_rag
python -m src.database
```

Update the SEC identity placeholders before ingestion:

- `src/ingest.py`
- `src/extract_financials.py`
- `src/test_ingest.py`
- `src/test_financials.py`

Then ingest filing text and extract financial metrics:

```bash
python -m src.ingest
python -m src.extract_financials
```

## Run The App

```bash
streamlit run src/app.py
```

Example questions:

- What was Apple's revenue in 2025?
- What is Nvidia's net income?
- What are Tesla's main risk factors?

Numeric metric questions use structured XBRL data when the query matches a supported metric and company. Qualitative questions use retrieved filing sections.

## Configuration

Main project settings are in `src/config.py`:

- company aliases and target tickers
- filing types
- number of filings to pull
- target filing sections
- 10-K and 10-Q section mappings

Postgres connection settings are currently in `src/database.py`.

## Tests And Evaluation

Run the test suite:

```bash
python tests/run_tests.py
```

The smoke tests assume:

- Ollama is running
- required Ollama models are available
- ChromaDB has an existing `sec_filings` collection
- Postgres contains extracted financial metrics

Run batch evaluation from a JSONL question file:

```bash
python eval_runner.py --questions questions.jsonl --output data/eval_results.jsonl
```

Each input line should contain a `question` field:

```json
{"question": "What was Apple revenue in 2025?"}
```

## Repository Structure

```text
src/ingest.py              Ingest filing text into ChromaDB
src/extract_financials.py  Extract XBRL metrics into Postgres
src/query.py               Parse queries, retrieve context, generate answers
src/app.py                 Streamlit UI
src/database.py            Postgres schema and connection
src/config.py              Companies, filing types, and section mappings
tests/                     Runtime smoke tests and helper tests
eval_runner.py             Batch evaluation runner
```

## Known Limitations

- Local services must be running before querying.
- Filing text and financial metrics must be ingested before the app can answer reliably.
- SEC identity values are placeholders and should be replaced before using `edgartools`.
- Database connection settings are hardcoded for a local environment.
- ChromaDB paths are relative to the current working directory.
- Error handling is limited if Ollama, ChromaDB, or Postgres are unavailable.
- Generated answers should be checked against the cited SEC filings.

## Disclaimer

This project is for research assistance only. It is not financial advice, and generated answers should be verified against original SEC filings.
