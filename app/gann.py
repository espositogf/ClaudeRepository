"""Strumenti di analisi secondo la teoria di W.D. Gann.

Ogni funzione `check_*` valuta una delle condizioni della matrice di
confidenza rispetto a un pivot di ancoraggio e restituisce un `Signal`
quando la condizione è verificata, altrimenti `None`.
"""

from dataclasses import dataclass
import math

import pandas as pd

BUY = "COMPRARE"
SELL = "VENDERE"

LOW = "minimo"
HIGH = "massimo"


@dataclass(frozen=True)
class Pivot:
    kind: str  # LOW oppure HIGH
    date: pd.Timestamp
    price: float
    window: int  # finestra di ricerca in giorni solari


@dataclass(frozen=True)
class Signal:
    condition: str
    direction: str
    # Distanza normalizzata dal contatto perfetto: 0 = esatto, 1 = al limite
    # della tolleranza. Serve a scegliere il segnale più preciso.
    distance: float
    pivot: Pivot
    detail: str


def fmt_num(value: float, decimals: int = 3) -> str:
    return f"{value:.{decimals}f}".replace(".", ",")


def fmt_date(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%d/%m/%Y")


def _pivot_label(pivot: Pivot) -> str:
    return f"{pivot.kind} a {pivot.window} gg ({fmt_num(pivot.price)} del {fmt_date(pivot.date)})"


# --- Indicatori di base -------------------------------------------------


def average_true_range(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """ATR con media di Wilder."""
    prev_close = df["Close"].shift(1)
    true_range = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def scale_factor(atr: pd.Series, lookback: int = 252) -> float:
    """Fattore di scala 1x1: valore monetario di una unità di tempo (seduta),
    pari alla media dell'ATR sulle ultime `lookback` sedute."""
    values = atr.dropna().iloc[-lookback:]
    if values.empty:
        raise ValueError("ATR non disponibile: storico troppo corto")
    return float(values.mean())


def find_pivots(df: pd.DataFrame, windows=(30, 60, 180, 365), min_age: int = 5) -> list[Pivot]:
    """Massimi e minimi (rolling max/min) nelle finestre in giorni solari.

    Un estremo è un pivot solo se confermato, cioè seguito da almeno
    `min_age` sedute che non lo hanno superato. Pivot ripetuti tra finestre
    diverse vengono tenuti una sola volta, con la finestra più ampia."""
    as_of = df.index[-1]
    found: dict[tuple, Pivot] = {}
    for window in sorted(windows):
        part = df[df.index > as_of - pd.Timedelta(days=window)]
        if part.empty:
            continue
        for kind, column, locate in ((HIGH, "High", "idxmax"), (LOW, "Low", "idxmin")):
            date = getattr(part[column], locate)()
            age = len(part) - 1 - part.index.get_loc(date)
            if age < min_age:
                continue
            price = float(part.at[date, column])
            found[(kind, date)] = Pivot(kind, pd.Timestamp(date), price, window)
    return sorted(found.values(), key=lambda p: (p.window, p.kind))


def weekly_trend(df: pd.DataFrame, weeks: int = 4) -> str:
    """Tendenza settimanale (conferma di lungo periodo) secondo la regola
    di Gann dei massimi/minimi crescenti o decrescenti: confronta le
    ultime `weeks` settimane con le `weeks` precedenti."""
    weekly = (
        df.resample("W-FRI")
        .agg({"High": "max", "Low": "min", "Close": "last"})
        .dropna()
    )
    if len(weekly) < 2 * weeks:
        return "NEUTRALE"
    recent, previous = weekly.iloc[-weeks:], weekly.iloc[-2 * weeks : -weeks]
    higher = recent["High"].max() > previous["High"].max() and recent["Low"].min() > previous["Low"].min()
    lower = recent["High"].max() < previous["High"].max() and recent["Low"].min() < previous["Low"].min()
    if higher:
        return "RIALZISTA"
    if lower:
        return "RIBASSISTA"
    return "NEUTRALE"


# --- Condizioni della matrice di confidenza -----------------------------


def angle_1x1_value(pivot: Pivot, scale: float, trading_days: int) -> float:
    """Valore della retta 1x1 dopo `trading_days` sedute dal pivot:
    ascendente da un minimo, discendente da un massimo."""
    step = scale * trading_days
    return pivot.price + step if pivot.kind == LOW else pivot.price - step


def check_angle_1x1(pivot: Pivot, close: float, scale: float, trading_days: int, tolerance: float):
    """Prezzo a contatto con la retta 1x1 tracciata dal pivot.

    La 1x1 ascendente da un minimo fa da supporto (COMPRARE), quella
    discendente da un massimo fa da resistenza (VENDERE)."""
    if trading_days < 1 or tolerance <= 0:
        return None
    line = angle_1x1_value(pivot, scale, trading_days)
    if line <= 0:
        return None
    gap = abs(close - line)
    if gap > tolerance:
        return None
    if pivot.kind == LOW:
        direction, role = BUY, "1x1 ascendente (supporto)"
    else:
        direction, role = SELL, "1x1 discendente (resistenza)"
    detail = (
        f"Prezzo a contatto con la {role} dal {_pivot_label(pivot)}: "
        f"retta a {fmt_num(line)} dopo {trading_days} sedute"
    )
    return Signal("angolo_1x1", direction, gap / tolerance, pivot, detail)


def check_squaring(pivot: Pivot, close: float, scale: float, natural_days: int, rel_tolerance: float):
    """Squadratura prezzo/tempo: unità di prezzo percorse dal pivot (in
    multipli del fattore di scala) pari ai giorni solari trascorsi.

    Il quadrato completato segnala una possibile inversione del movimento
    partito dal pivot: dopo un rialzo da un minimo VENDERE, dopo un ribasso
    da un massimo COMPRARE."""
    if natural_days < 1 or scale <= 0:
        return None
    move = close - pivot.price
    if (pivot.kind == LOW and move <= 0) or (pivot.kind == HIGH and move >= 0):
        return None
    price_units = abs(move) / scale
    tolerance = max(1.0, rel_tolerance * natural_days)
    gap = abs(price_units - natural_days)
    if gap > tolerance:
        return None
    direction = SELL if pivot.kind == LOW else BUY
    detail = (
        f"Prezzo e tempo in quadratura dal {_pivot_label(pivot)}: "
        f"{fmt_num(price_units, 1)} unità di prezzo in {natural_days} giorni solari"
    )
    return Signal("squadratura", direction, gap / tolerance, pivot, detail)


def square_of_nine_levels(price: float, degrees=(90, 180, 360), upward: bool = True) -> dict[int, float]:
    """Livelli del Quadrato di Nove: (sqrt(P) ± gradi/180)^2."""
    root = math.sqrt(price)
    levels = {}
    for deg in degrees:
        shifted = root + deg / 180 if upward else root - deg / 180
        if shifted > 0:
            levels[deg] = shifted**2
    return levels


def check_square_of_nine(pivot: Pivot, close: float, tolerance: float, degrees=(90, 180, 360)):
    """Prezzo a contatto con un angolo chiave del Quadrato di Nove calcolato
    dal pivot: i livelli sopra un minimo sono resistenze (VENDERE), quelli
    sotto un massimo sono supporti (COMPRARE)."""
    if tolerance <= 0:
        return None
    upward = pivot.kind == LOW
    levels = square_of_nine_levels(pivot.price, degrees, upward=upward)
    if not levels:
        return None
    deg, level = min(levels.items(), key=lambda item: abs(close - item[1]))
    gap = abs(close - level)
    if gap > tolerance:
        return None
    if upward:
        direction, role = SELL, "resistenza"
    else:
        direction, role = BUY, "supporto"
    detail = (
        f"Prezzo sul livello a {deg}° del Quadrato di Nove ({role} a {fmt_num(level)}) "
        f"dal {_pivot_label(pivot)}"
    )
    return Signal("quadrato_nove", direction, gap / tolerance, pivot, detail)


def check_time_cycles(pivot: Pivot, natural_days: int, cycles=(30, 60, 90, 180), tolerance_days: int = 2):
    """Scadenza di un ciclo temporale primario dal pivot.

    La fine del ciclo segnala una possibile inversione: dopo un minimo
    VENDERE, dopo un massimo COMPRARE."""
    if natural_days < 1:
        return None
    cycle = min(cycles, key=lambda c: abs(natural_days - c))
    gap = abs(natural_days - cycle)
    if gap > tolerance_days:
        return None
    direction = SELL if pivot.kind == LOW else BUY
    detail = (
        f"Scadenza del ciclo di {cycle} giorni dal {_pivot_label(pivot)} "
        f"({natural_days} giorni solari trascorsi)"
    )
    distance = gap / tolerance_days if tolerance_days else 0.0
    return Signal("cicli", direction, distance, pivot, detail)
