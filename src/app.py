import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from src.query import ask

st.set_page_config(page_title="SEC Filing RAG", layout="wide")
st.title("SEC Filing Research Assistant")
st.caption("Ask questions about 10-K and 10-Q filings from major public companies.")

query = st.text_input("Enter your question:", placeholder="e.g. What was Apple's revenue in 2025?")

if query:
    with st.spinner("Searching filings and generating answer..."):
        answer, results, financial_data = ask(query)

    if financial_data:
        st.info(f"Structured data match: **{financial_data['ticker']} {financial_data['metric_name'].replace('_', ' ')}** "
                f"for period ending {financial_data['fiscal_period_end']}")

    st.subheader("Answer")
    st.markdown(answer)

    st.subheader("Retrieved Sources")
    for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
        with st.expander(f"Source {i+1}: {meta['ticker']} | {meta['filing_type']} | {meta['filing_date']} | {meta['section']}"):
            st.text(doc)