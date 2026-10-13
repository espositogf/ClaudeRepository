"""Recupero delle serie storiche OHLCV (giornaliere)."""

import logging
import threading
import time
import zlib

import numpy as np
import pandas as pd

from . import config
from .market_calendar import TradingCalendar

logger = logging.getLogger(__name__)

COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

_cache: dict[tuple, tuple[float, dict[str, pd.DataFrame]]] = {}
_cache_lock = threading.Lock()


class DataSourceError(RuntimeError):
    """Errore nel recupero dei dati di mercato."""


def get_history(tickers: list[str], source: str | None = None) -> dict[str, pd.DataFrame]:
    """Serie giornaliere OHLCV per ogni ticker, con cache in memoria.

    I ticker per cui non arrivano dati vengono omessi dal risultato.
    """
    source = (source or config.DATA_SOURCE).lower()
    key = (source, config.HISTORY_PERIOD, tuple(tickers))
    with _cache_lock:
        cached = _cache.get(key)
        if cached and time.time() - cached[0] < config.CACHE_TTL_SECONDS:
            return cached[1]

    if source == "demo":
        data = _demo_history(tickers)
    elif source == "yahoo":
        data = _yahoo_history(tickers)
    else:
        raise DataSourceError(f"Fonte dati sconosciuta: {source!r}")

    with _cache_lock:
        _cache[key] = (time.time(), data)
    return data


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df[[c for c in COLUMNS if c in df.columns]].copy()
    df = df.dropna(subset=["High", "Low", "Close"])
    df.index = pd.DatetimeIndex(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df.index = df.index.normalize()
    return df[~df.index.duplicated(keep="last")].sort_index()


def _yahoo_history(tickers: list[str]) -> dict[str, pd.DataFrame]:
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover
        raise DataSourceError("Il pacchetto yfinance non è installato.") from exc

    raw = yf.download(
        tickers,
        period=config.HISTORY_PERIOD,
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=True,
    )
    if raw is None or raw.empty:
        raise DataSourceError(
            "Nessun dato ricevuto da Yahoo Finance: verificare la connessione "
            "a Internet oppure avviare in modalità demo (GANN_DATA_SOURCE=demo)."
        )

    result = {}
    for ticker in tickers:
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                df = raw[ticker]
            else:
                df = raw
            df = _clean(df)
        except KeyError:
            continue
        if not df.empty:
            result[ticker] = df
    if not result:
        raise DataSourceError("Yahoo Finance non ha restituito dati validi.")
    return result


def _demo_history(tickers: list[str]) -> dict[str, pd.DataFrame]:
    """Serie sintetiche ma realistiche, riproducibili per ticker e giorno."""
    end = pd.Timestamp.today().normalize()
    start = end - pd.DateOffset(years=2)
    days = TradingCalendar(start, end).days
    day_seed = int(end.strftime("%Y%m%d"))

    result = {}
    for ticker in tickers:
        rng = np.random.default_rng(zlib.crc32(ticker.encode()) + day_seed)
        n = len(days)
        base = rng.uniform(2, 60)
        drift = rng.normal(0.0002, 0.0006)
        vol = rng.uniform(0.010, 0.022)
        # Componente ciclica per rendere più evidenti massimi e minimi.
        period = rng.uniform(40, 120)
        cycle = 0.004 * np.sin(2 * np.pi * np.arange(n) / period + rng.uniform(0, 6))
        returns = rng.normal(drift, vol, n) + cycle
        close = base * np.exp(np.cumsum(returns))
        open_ = close * np.exp(rng.normal(0, vol / 3, n))
        spread = np.abs(rng.normal(0, vol * 0.8, n)) * close
        high = np.maximum(open_, close) + spread * rng.uniform(0.2, 1.0, n)
        low = np.minimum(open_, close) - spread * rng.uniform(0.2, 1.0, n)
        volume = rng.lognormal(14, 0.4, n).round()
        result[ticker] = pd.DataFrame(
            {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
            index=days,
        )
    return result
