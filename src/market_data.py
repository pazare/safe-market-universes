from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from .config import MARKET_DATA_CACHE_DIR


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, str, bool)):
        return value
    if pd.isna(value):
        return None
    return round(float(value), digits)


def _compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    avg_gain = gains.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = losses.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def _compute_atr(history: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = history["High"] - history["Low"]
    high_prev_close = (history["High"] - history["Close"].shift(1)).abs()
    low_prev_close = (history["Low"] - history["Close"].shift(1)).abs()
    true_range = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    return true_range.rolling(window=period, min_periods=period).mean()


def _safe_info_lookup(stock: yf.Ticker) -> dict[str, Any]:
    try:
        return stock.info or {}
    except Exception:
        return {}


def download_price_history(
    ticker: str,
    *,
    period: str = "1y",
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    cache_payload = {
        "ticker": ticker.upper(),
        "period": period,
        "start": start,
        "end": end,
        "interval": "1d",
        "auto_adjust": False,
    }
    cache_key = hashlib.sha256(json.dumps(cache_payload, sort_keys=True).encode("utf-8")).hexdigest()
    cache_disabled = os.getenv("SMU_MARKET_DATA_CACHE_DISABLED", "").strip().lower() in {"1", "true", "yes"}
    cache_csv = MARKET_DATA_CACHE_DIR / f"{cache_key}.csv"
    cache_meta = MARKET_DATA_CACHE_DIR / f"{cache_key}.json"
    if not cache_disabled and cache_csv.exists():
        cached = pd.read_csv(cache_csv, index_col=0, parse_dates=True)
        if not cached.empty:
            return cached.dropna(subset=["Close"]).copy()

    download_kwargs = {
        "tickers": ticker,
        "interval": "1d",
        "auto_adjust": False,
        "progress": False,
        "threads": False,
    }
    if start is None:
        download_kwargs["period"] = period
    else:
        download_kwargs["start"] = start
        download_kwargs["end"] = end

    history = yf.download(**download_kwargs)
    if isinstance(history.columns, pd.MultiIndex):
        history.columns = history.columns.get_level_values(0)
    cleaned = history.dropna(subset=["Close"]).copy()
    if not cache_disabled and not cleaned.empty:
        MARKET_DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cleaned.to_csv(cache_csv)
        cache_meta.write_text(
            json.dumps(
                {
                    "cache_key": cache_key,
                    "payload": cache_payload,
                    "rows": len(cleaned),
                    "first_date": cleaned.index[0].date().isoformat(),
                    "last_date": cleaned.index[-1].date().isoformat(),
                    "csv_sha256": hashlib.sha256(cache_csv.read_bytes()).hexdigest(),
                    "source": "yfinance",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return cleaned


def _coerce_as_of_date(as_of_date: str | date | datetime | None) -> pd.Timestamp | None:
    if as_of_date is None:
        return None
    return pd.Timestamp(as_of_date).normalize()


def build_market_data_from_history(
    ticker: str,
    history: pd.DataFrame,
    *,
    info: dict[str, Any] | None = None,
    as_of_date: str | date | datetime | None = None,
    allow_live_info_fields: bool = True,
) -> dict[str, Any]:
    """
    Build a market snapshot from a history DataFrame. When `as_of_date` is set,
    the function uses only rows at or before that date.
    """
    if history.empty:
        raise ValueError(f"{ticker} returned no price history.")

    cutoff = _coerce_as_of_date(as_of_date)
    scoped_history = history.copy()
    if cutoff is not None:
        scoped_history = scoped_history.loc[scoped_history.index.normalize() <= cutoff].copy()

    if len(scoped_history) < 90:
        raise ValueError(
            f"{ticker} returned only {len(scoped_history)} usable rows before the snapshot date; "
            "need at least 90."
        )

    scoped_history["daily_return"] = scoped_history["Close"].pct_change()
    scoped_history["rsi_14"] = _compute_rsi(scoped_history["Close"], period=14)
    scoped_history["atr_14"] = _compute_atr(scoped_history, period=14)

    close = scoped_history["Close"]
    volume = scoped_history["Volume"].fillna(0)

    last_30 = scoped_history.tail(30)
    last_90 = scoped_history.tail(90)
    last_252 = scoped_history.tail(min(252, len(scoped_history)))

    current_price = float(close.iloc[-1])
    price_30d_ago = float(close.iloc[-31] if len(close) >= 31 else close.iloc[0])
    avg_daily_volume_30d = float(last_30["Volume"].mean())
    latest_volume = float(volume.iloc[-1])
    volatility_30d = float(last_30["daily_return"].dropna().std())
    volatility_90d = float(last_90["daily_return"].dropna().std())
    moving_avg_20d = float(close.tail(20).mean())
    moving_avg_50d = float(close.tail(50).mean())
    moving_avg_200d = float(close.tail(200).mean())
    high_52w = float(last_252["Close"].max())
    low_52w = float(last_252["Close"].min())
    recent_peak_90d = float(last_90["Close"].max())
    rsi_14 = float(scoped_history["rsi_14"].iloc[-1])
    atr_14 = float(scoped_history["atr_14"].iloc[-1]) if not pd.isna(scoped_history["atr_14"].iloc[-1]) else None
    max_single_day_drop_90d = float(last_90["daily_return"].dropna().min())

    info = info or {}
    trailing_pe = None
    if allow_live_info_fields:
        trailing_pe = info.get("trailingPE")
        if trailing_pe is None:
            trailing_pe = info.get("forwardPE")

    latest_day = scoped_history.index[-1].date().isoformat()
    summary = {
        "company_name": (info.get("longName") or info.get("shortName") or ticker) if allow_live_info_fields else ticker,
        "sector": info.get("sector") if allow_live_info_fields else None,
        "latest_trading_day": latest_day,
        "snapshot_mode": "historical" if cutoff is not None else "live",
        "current_price": _round(current_price, 2),
        "price_30d_ago": _round(price_30d_ago, 2),
        "pct_change_30d": _round(((current_price / price_30d_ago) - 1) * 100, 2),
        "avg_daily_volume_30d": int(round(avg_daily_volume_30d)),
        "latest_volume": int(round(latest_volume)),
        "volume_vs_avg_30d": _round(latest_volume / avg_daily_volume_30d, 2) if avg_daily_volume_30d else None,
        "volatility_30d": _round(volatility_30d, 4),
        "volatility_90d": _round(volatility_90d, 4),
        "moving_avg_20d": _round(moving_avg_20d, 2),
        "moving_avg_50d": _round(moving_avg_50d, 2),
        "moving_avg_200d": _round(moving_avg_200d, 2),
        "short_vs_long_ma_pct": _round(((moving_avg_20d / moving_avg_50d) - 1) * 100, 2),
        "mid_vs_long_ma_pct": _round(((moving_avg_50d / moving_avg_200d) - 1) * 100, 2),
        "high_52w": _round(high_52w, 2),
        "low_52w": _round(low_52w, 2),
        "pct_from_52w_high": _round(((current_price / high_52w) - 1) * 100, 2),
        "pct_from_52w_low": _round(((current_price / low_52w) - 1) * 100, 2),
        "recent_drawdown_90d": _round(((current_price / recent_peak_90d) - 1) * 100, 2),
        "rsi_14": _round(rsi_14, 2),
        "atr_14": _round(atr_14, 2),
        "atr_pct_of_price": _round((atr_14 / current_price) * 100, 2) if atr_14 else None,
        "max_single_day_drop_90d": _round(max_single_day_drop_90d * 100, 2),
        "trailing_pe": _round(trailing_pe, 2),
    }
    return summary


def fetch_market_data(
    ticker: str,
    *,
    as_of_date: str | date | datetime | None = None,
) -> dict[str, Any]:
    """
    Fetch live or historical market data and compute the indicators needed by
    the Momentum Trader, Value Contrarian, and Volatility Averse strategies.

    Historical snapshots intentionally omit live valuation fields like
    `trailing_pe` to avoid lookahead bias when used in the backtest extension.
    """
    cutoff = _coerce_as_of_date(as_of_date)
    stock = yf.Ticker(ticker)
    info = _safe_info_lookup(stock) if cutoff is None else {}

    if cutoff is None:
        history = download_price_history(ticker, period="1y")
    else:
        start = (cutoff - timedelta(days=450)).date().isoformat()
        end = (cutoff + timedelta(days=1)).date().isoformat()
        history = download_price_history(ticker, start=start, end=end)

    return build_market_data_from_history(
        ticker,
        history,
        info=info,
        as_of_date=cutoff,
        allow_live_info_fields=cutoff is None,
    )


def verify_yfinance_fetch(ticker: str = "MSFT") -> dict[str, Any]:
    """Return one real market snapshot so setup can be verified before full execution."""
    return fetch_market_data(ticker)
