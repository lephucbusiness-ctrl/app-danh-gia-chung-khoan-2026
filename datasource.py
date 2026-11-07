"""
Nguồn dữ liệu (không dùng vnstock - gói này đang bị PyPI cách ly).

Thứ tự thử:
  Giá lịch sử : 1) Yahoo Finance (yfinance, mã dạng HPG.VN)  2) API công khai TCBS
  Chỉ số TC   : 1) API công khai TCBS                         2) Yahoo Finance
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta

import pandas as pd
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (radar-co-phieu)", "Accept": "application/json"}
TCBS = "https://apipubaws.tcbs.com.vn"


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=str.lower)
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df.index = df.index.normalize()
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    df = df[(df["close"] > 0)].dropna()
    return df[~df.index.duplicated(keep="last")].sort_index()


# ----------------------------------------------------------------- GIÁ
def price_yahoo(ticker: str, days: int) -> pd.DataFrame:
    import yfinance as yf

    df = yf.Ticker(f"{ticker}.VN").history(
        start=(datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d"),
        interval="1d", auto_adjust=False,
    )
    if df is None or df.empty:
        raise ValueError("Yahoo không có dữ liệu")
    return _clean(df)


def price_tcbs(ticker: str, days: int) -> pd.DataFrame:
    now = int(time.time())
    r = requests.get(
        f"{TCBS}/stock-insight/v2/stock/bars-long-term",
        params={"ticker": ticker, "type": "stock", "resolution": "D",
                "from": now - days * 86400, "to": now, "countBack": days},
        headers=HEADERS, timeout=20,
    )
    if r.status_code != 200:  # thử bản API cũ
        r = requests.get(
            f"{TCBS}/stock-insight/v1/stock/bars-long-term",
            params={"ticker": ticker, "type": "stock", "resolution": "D",
                    "from": now - days * 86400, "to": now},
            headers=HEADERS, timeout=20,
        )
    r.raise_for_status()
    data = r.json().get("data") or []
    if not data:
        raise ValueError("TCBS không có dữ liệu")
    df = pd.DataFrame(data)
    df.index = pd.to_datetime(df["tradingDate"].astype(str).str[:10])
    return _clean(df)


def load_price(ticker: str, days: int = 730) -> pd.DataFrame:
    errors = []
    for name, fn in (("Yahoo", price_yahoo), ("TCBS", price_tcbs)):
        try:
            df = fn(ticker, days)
            if len(df) >= 60:
                df.attrs["source"] = name
                return df
            errors.append(f"{name}: chỉ có {len(df)} phiên")
        except Exception as e:
            errors.append(f"{name}: {e}")
    raise RuntimeError(f"Không tải được giá {ticker}. " + " | ".join(errors))


# ----------------------------------------------------------------- CHỈ SỐ TÀI CHÍNH
def ratio_tcbs(ticker: str) -> pd.DataFrame:
    r = requests.get(
        f"{TCBS}/tcanalysis/v1/finance/{ticker}/financialratio",
        params={"yearly": 1, "isAll": "true"}, headers=HEADERS, timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):
        data = data.get("data") or data.get("listFinancialRatio") or []
    df = pd.DataFrame(data)
    if df.empty:
        raise ValueError("TCBS không có chỉ số tài chính")
    if "quarter" in df.columns:  # chỉ giữ số liệu cả năm
        yearly = df[df["quarter"].isin([5, 0]) | df["quarter"].isna()]
        df = yearly if not yearly.empty else df
    return df


def metrics_yahoo(ticker: str) -> dict:
    import yfinance as yf

    info = yf.Ticker(f"{ticker}.VN").info or {}

    def g(k):
        v = info.get(k)
        return float(v) if isinstance(v, (int, float)) else None

    roe, de, growth = g("returnOnEquity"), g("debtToEquity"), g("earningsGrowth")
    m = {
        "roe": roe * 100 if roe is not None else None,
        "pe": g("trailingPE"),
        "pb": g("priceToBook"),
        "de": de / 100 if de is not None else None,  # Yahoo trả theo %
        "growth": growth * 100 if growth is not None else None,
    }
    if all(v is None for v in m.values()):
        raise ValueError("Yahoo không có chỉ số tài chính")
    return m
