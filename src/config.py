COMPANY_ALIASES = {
    # Tech
    "apple": "AAPL",
    "aapl": "AAPL",
    "microsoft": "MSFT",
    "msft": "MSFT",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "googl": "GOOGL",
    "meta": "META",
    "facebook": "META",
    "fb": "META",
    "amazon": "AMZN",
    "amzn": "AMZN",
    "nvidia": "NVDA",
    "nvda": "NVDA",
    "tesla": "TSLA",
    "tsla": "TSLA",

    # Finance
    "jpmorgan": "JPM",
    "jp morgan": "JPM",
    "jpm": "JPM",
    "goldman sachs": "GS",
    "goldman": "GS",
    "gs": "GS",
    "bank of america": "BAC",
    "bac": "BAC",

    # Healthcare
    "johnson & johnson": "JNJ",
    "johnson and johnson": "JNJ",
    "jnj": "JNJ",
    "pfizer": "PFE",
    "pfe": "PFE",
    "unitedhealth": "UNH",
    "unh": "UNH",

    # Consumer
    "walmart": "WMT",
    "wmt": "WMT",
    "coca-cola": "KO",
    "coca cola": "KO",
    "coke": "KO",
    "ko": "KO",
    "procter & gamble": "PG",
    "procter and gamble": "PG",
    "pg": "PG",

    # Energy
    "exxon": "XOM",
    "exxonmobil": "XOM",
    "exxon mobil": "XOM",
    "xom": "XOM",
    "chevron": "CVX",
    "cvx": "CVX",

    # Industrial
    "boeing": "BA",
    "ba": "BA",
    "caterpillar": "CAT",
    "cat": "CAT",
    "3m": "MMM",
    "mmm": "MMM",
}

# Tickers to fetch filings for
TARGET_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "META", "AMZN", "NVDA", "TSLA",
    "JPM", "GS", "BAC",
    "JNJ", "PFE", "UNH",
    "WMT", "KO", "PG",
    "XOM", "CVX",
    "BA", "CAT", "MMM",
]

# Filing types to fetch
FILING_TYPES = ["10-K", "10-Q"]

# How many years back to pull
YEARS_BACK = 3

# Sections of interest in filings
TARGET_SECTIONS = [
    "Risk Factors",
    "Management's Discussion and Analysis",
    "Business",
]

TENK_SECTION_MAP = {
    "Risk Factors": "risk_factors",
    "Management's Discussion and Analysis": "management_discussion",
    "Business": "business",
}

TENQ_SECTION_MAP = {
    "Risk Factors": "Part II, Item 1A",
    "Management's Discussion and Analysis": "Part I, Item 2",
}