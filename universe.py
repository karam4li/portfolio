"""
Stock universe management.
Primary: Download the full NASDAQ-traded file (all US-listed equities).
Fallback: A curated list of historically volatile small/micro-cap stocks.
"""

import io
import re
from typing import List

import pandas as pd
import requests

NASDAQ_TRADER_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"

# Stocks known for extreme volatility — used as fallback if download fails
FALLBACK_TICKERS = [
    "GME", "AMC", "BBBY", "CLOV", "WKHS", "NKLA", "SPCE", "MVIS",
    "SNDL", "EXPR", "KOSS", "NOK", "BB", "TLRY", "OCGN", "BCRX",
    "SRNE", "VXRT", "INO", "NVAX", "ATOS", "MMAT", "PROG", "BBIG",
    "IRNT", "SPRT", "PLTR", "WISH", "CLNE", "APPH", "GOEV", "ARVL",
    "XPEV", "NIO", "LCID", "RIVN", "FSR", "HYMC", "CTRM", "NAKD",
    "SIGA", "GREE", "DPLS", "COSM", "NURO", "AGRX", "TPVG", "VCNX",
]


def load_us_stocks(max_size: int = 3000) -> List[str]:
    """
    Download and parse the NASDAQ trader file to get all US-listed common stocks.
    Returns a list of plain ticker symbols, filtered to real equities (no ETFs/tests).
    """
    try:
        response = requests.get(NASDAQ_TRADER_URL, timeout=15)
        response.raise_for_status()

        df = pd.read_csv(io.StringIO(response.text), sep="|")

        # Drop the file-creation-timestamp footer row
        df = df.dropna(subset=["Symbol"])
        df = df[~df["Symbol"].astype(str).str.startswith("File")]

        # Keep only real equities: traded on NASDAQ, not an ETF, not a test issue
        mask = (
            (df.get("Nasdaq Traded", pd.Series(["Y"] * len(df))) == "Y")
            & (df.get("ETF", pd.Series(["N"] * len(df))) != "Y")
            & (df.get("Test Issue", pd.Series(["N"] * len(df))) != "Y")
        )
        clean = df[mask].copy()

        # Only simple 1–5-letter symbols (filters out warrants, units, preferred shares)
        clean = clean[clean["Symbol"].str.match(r"^[A-Z]{1,5}$", na=False)]

        symbols = clean["Symbol"].tolist()
        return symbols[:max_size]

    except Exception as exc:
        print(f"Warning: could not fetch NASDAQ universe ({exc}); using fallback list")
        return list(FALLBACK_TICKERS)
