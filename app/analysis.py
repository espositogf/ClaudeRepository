"""Analisi dei titoli e calcolo della percentuale di confidenza."""

from dataclasses import dataclass, field
import logging

import pandas as pd

from . import config, gann
from .data import get_history
from .market_calendar import TradingCalendar, natural_days_between
from .universe import get_universe

logger = logging.getLogger(__name__)

CONDITION_LABELS = {
    "angolo_1x1": "Intersezione Angoli 1x1",
    "squadratura": "Squadratura Prezzo/Tempo",
    "quadrato_nove": "Quadrato di Nove",
    "cicli": "Cicli Temporali Primari",
}

WEEKLY_DIRECTION = {"RIALZISTA": gann.BUY, "RIBASSISTA": gann.SELL}


@dataclass
class TickerAnalysis:
    ticker: str
    name: str
    as_of: pd.Timestamp
    close: float
    scale: float
    atr: float
    action: str | None
    confidence: int
    weekly_trend: str
    signals: dict[str, gann.Signal] = field(default_factory=dict)

    @property
    def weekly_confirms(self) -> bool:
        return WEEKLY_DIRECTION.get(self.weekly_trend) == self.action

    @property
    def precision(self) -> float:
        """Distanza media dei segnali concordi (più bassa = più precisa)."""
        agreeing = [s.distance for s in self.signals.values() if s.direction == self.action]
        return sum(agreeing) / len(agreeing) if agreeing else 1.0

    def to_dict(self) -> dict:
        conditions = []
        for key, label in CONDITION_LABELS.items():
            signal = self.signals.get(key)
            conditions.append(
                {
                    "chiave": key,
                    "nome": label,
                    "peso": config.WEIGHTS[key],
                    "verificata": signal is not None,
                    "concorde": signal is not None and signal.direction == self.action,
                    "direzione": signal.direction if signal else None,
                    "dettaglio": signal.detail if signal else None,
                }
            )
        return {
            "ticker": self.ticker,
            "nome": self.name,
            "azione": self.action,
            "confidenza": self.confidence,
            "prezzo": round(self.close, 4),
            "data": self.as_of.strftime("%Y-%m-%d"),
            "fattore_scala": round(self.scale, 4),
            "atr": round(self.atr, 4),
            "trend_settimanale": self.weekly_trend,
            "conferma_settimanale": self.weekly_confirms,
            "condizioni": conditions,
        }


def _best(signals: list[gann.Signal]) -> gann.Signal | None:
    """Segnale più preciso; a parità, quello del pivot di lungo periodo."""
    if not signals:
        return None
    return min(signals, key=lambda s: (round(s.distance, 6), -s.pivot.window))


def decide(signals: dict[str, gann.Signal], weekly: str) -> tuple[str | None, int]:
    """Azione e confidenza: somma dei pesi delle condizioni verificate che
    concordano sulla stessa direzione. In caso di parità decide la tendenza
    settimanale, poi la precisione dei segnali."""
    scores = {gann.BUY: 0, gann.SELL: 0}
    for key, signal in signals.items():
        scores[signal.direction] += config.WEIGHTS[key]
    if scores[gann.BUY] == scores[gann.SELL] == 0:
        return None, 0
    if scores[gann.BUY] != scores[gann.SELL]:
        action = max(scores, key=scores.get)
    elif weekly in WEEKLY_DIRECTION:
        action = WEEKLY_DIRECTION[weekly]
    else:
        def mean_distance(direction):
            values = [s.distance for s in signals.values() if s.direction == direction]
            return sum(values) / len(values)

        action = min(scores, key=mean_distance)
    return action, scores[action]


def analyze_ticker(ticker: str, name: str, df: pd.DataFrame, calendar: TradingCalendar) -> TickerAnalysis | None:
    if len(df) < config.MIN_BARS:
        return None
    atr_series = gann.average_true_range(df, config.ATR_PERIOD)
    atr = float(atr_series.iloc[-1])
    if not atr or pd.isna(atr):
        return None
    scale = gann.scale_factor(atr_series, config.SCALE_LOOKBACK)
    as_of = df.index[-1]
    close = float(df["Close"].iloc[-1])
    price_tolerance = config.PRICE_TOLERANCE_ATR * atr

    candidates: dict[str, list[gann.Signal]] = {key: [] for key in CONDITION_LABELS}
    for pivot in gann.find_pivots(df, config.PIVOT_WINDOWS, config.PIVOT_MIN_AGE):
        natural = natural_days_between(pivot.date, as_of)
        trading = calendar.trading_days_between(pivot.date, as_of)
        checks = (
            gann.check_angle_1x1(pivot, close, scale, trading, price_tolerance),
            gann.check_squaring(pivot, close, scale, natural, config.SQUARING_TOLERANCE),
            gann.check_square_of_nine(pivot, close, price_tolerance, config.SQUARE_OF_NINE_DEGREES),
            gann.check_time_cycles(pivot, natural, config.TIME_CYCLES, config.CYCLE_TOLERANCE_DAYS),
        )
        for signal in checks:
            if signal is not None:
                candidates[signal.condition].append(signal)

    signals = {key: best for key, items in candidates.items() if (best := _best(items))}
    weekly = gann.weekly_trend(df)
    action, confidence = decide(signals, weekly)
    return TickerAnalysis(
        ticker=ticker,
        name=name,
        as_of=as_of,
        close=close,
        scale=scale,
        atr=atr,
        action=action,
        confidence=confidence,
        weekly_trend=weekly,
        signals=signals,
    )


def rank(analyses: list[TickerAnalysis], limit: int) -> list[TickerAnalysis]:
    """Titoli con segnale, ordinati per confidenza, conferma settimanale e
    precisione dei segnali."""
    selected = [a for a in analyses if a.action and a.confidence > 0]
    selected.sort(key=lambda a: (-a.confidence, not a.weekly_confirms, a.precision, a.ticker))
    return selected[:limit]


def run_forecast(limit: int | None = None, source: str | None = None) -> dict:
    limit = limit or config.DEFAULT_RESULTS
    universe = get_universe()
    history = get_history(list(universe), source=source)

    starts = [df.index[0] for df in history.values() if not df.empty]
    ends = [df.index[-1] for df in history.values() if not df.empty]
    calendar = TradingCalendar(min(starts), max(ends)) if starts else None

    analyses, skipped = [], []
    for ticker, name in universe.items():
        df = history.get(ticker)
        if df is None or calendar is None:
            skipped.append({"ticker": ticker, "motivo": "dati non disponibili"})
            continue
        try:
            result = analyze_ticker(ticker, name, df, calendar)
        except Exception as exc:  # un titolo problematico non blocca gli altri
            logger.exception("Errore nell'analisi di %s", ticker)
            skipped.append({"ticker": ticker, "motivo": f"errore di calcolo: {exc}"})
            continue
        if result is None:
            skipped.append({"ticker": ticker, "motivo": "storico insufficiente"})
            continue
        analyses.append(result)

    best = rank(analyses, limit)
    as_of = max((a.as_of for a in analyses), default=None)
    return {
        "fonte_dati": (source or config.DATA_SOURCE).lower(),
        "data_riferimento": as_of.strftime("%Y-%m-%d") if as_of is not None else None,
        "generato_il": pd.Timestamp.now().isoformat(timespec="seconds"),
        "titoli_analizzati": len(analyses),
        "titoli": [a.to_dict() for a in best],
        "esclusi": skipped,
    }
