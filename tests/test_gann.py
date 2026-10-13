import math

import numpy as np
import pandas as pd
import pytest

from app import gann
from app.analysis import decide
from app.gann import BUY, HIGH, LOW, SELL, Pivot, Signal
from app.market_calendar import TradingCalendar, natural_days_between

DAY = pd.Timestamp("2026-03-02")


def pivot(kind=LOW, price=100.0, window=60):
    return Pivot(kind, DAY, price, window)


def test_square_of_nine_levels():
    up = gann.square_of_nine_levels(100, upward=True)
    assert up[90] == pytest.approx(10.5**2)
    assert up[180] == pytest.approx(121)
    assert up[360] == pytest.approx(144)
    down = gann.square_of_nine_levels(100, upward=False)
    assert down[180] == pytest.approx(81)


def test_angle_1x1_from_low_is_support():
    # 10 sedute a 0,5 per seduta: la retta vale 105
    signal = gann.check_angle_1x1(pivot(LOW), close=105.2, scale=0.5, trading_days=10, tolerance=0.5)
    assert signal.direction == BUY
    assert signal.distance == pytest.approx(0.4)
    assert gann.check_angle_1x1(pivot(LOW), close=107, scale=0.5, trading_days=10, tolerance=0.5) is None


def test_angle_1x1_from_high_is_resistance():
    signal = gann.check_angle_1x1(pivot(HIGH), close=95, scale=0.5, trading_days=10, tolerance=0.5)
    assert signal.direction == SELL


def test_squaring_price_and_time():
    # 30 unità da 0,5 = 15 euro percorsi in 30 giorni solari
    signal = gann.check_squaring(pivot(LOW), close=115, scale=0.5, natural_days=30, rel_tolerance=0.05)
    assert signal.direction == SELL
    assert gann.check_squaring(pivot(LOW), close=110, scale=0.5, natural_days=30, rel_tolerance=0.05) is None
    # movimento in direzione opposta al pivot: nessun quadrato
    assert gann.check_squaring(pivot(HIGH), close=115, scale=0.5, natural_days=30, rel_tolerance=0.05) is None
    assert gann.check_squaring(pivot(HIGH), close=85, scale=0.5, natural_days=30, rel_tolerance=0.05).direction == BUY


def test_square_of_nine_contact():
    signal = gann.check_square_of_nine(pivot(LOW), close=121.1, tolerance=0.5)
    assert signal.direction == SELL and "180°" in signal.detail
    signal = gann.check_square_of_nine(pivot(HIGH), close=81.2, tolerance=0.5)
    assert signal.direction == BUY
    assert gann.check_square_of_nine(pivot(LOW), close=130, tolerance=0.5) is None


def test_time_cycles():
    assert gann.check_time_cycles(pivot(LOW), 89, tolerance_days=2).direction == SELL
    assert gann.check_time_cycles(pivot(HIGH), 181, tolerance_days=2).direction == BUY
    assert gann.check_time_cycles(pivot(LOW), 45, tolerance_days=2) is None


def test_average_true_range_and_scale():
    idx = pd.bdate_range("2026-01-01", periods=40)
    df = pd.DataFrame({"High": 11.0, "Low": 10.0, "Close": 10.5}, index=idx)
    atr = gann.average_true_range(df, 14)
    assert atr.iloc[-1] == pytest.approx(1.0)
    assert gann.scale_factor(atr, 252) == pytest.approx(1.0)


def test_find_pivots_requires_confirmation():
    idx = pd.bdate_range("2026-01-01", periods=80)
    base = np.linspace(10, 20, 80)
    df = pd.DataFrame({"High": base + 0.5, "Low": base - 0.5, "Close": base}, index=idx)
    df.iloc[40, df.columns.get_loc("Low")] = 5.0  # minimo marcato
    pivots = gann.find_pivots(df, windows=(30, 60, 180, 365), min_age=5)
    lows = [p for p in pivots if p.kind == LOW]
    assert any(p.date == idx[40] and p.price == 5.0 for p in lows)
    # il massimo è sull'ultima seduta: non ancora confermato
    assert not [p for p in pivots if p.kind == HIGH]


def test_decide_sums_agreeing_weights():
    p = pivot()
    signals = {
        "angolo_1x1": Signal("angolo_1x1", BUY, 0.1, p, ""),
        "squadratura": Signal("squadratura", SELL, 0.1, p, ""),
        "quadrato_nove": Signal("quadrato_nove", BUY, 0.1, p, ""),
    }
    assert decide(signals, "NEUTRALE") == (BUY, 55)
    assert decide({}, "RIALZISTA") == (None, 0)


def test_decide_tie_uses_weekly_trend():
    p = pivot()
    signals = {
        "squadratura": Signal("squadratura", SELL, 0.1, p, ""),
        "quadrato_nove": Signal("quadrato_nove", BUY, 0.9, p, ""),
    }
    assert decide(signals, "RIALZISTA") == (BUY, 25)
    assert decide(signals, "NEUTRALE") == (SELL, 25)


def test_trading_calendar_excludes_weekends_and_holidays():
    cal = TradingCalendar("2026-12-01", "2027-01-31")
    # dal 23/12/2026 al 31/12/2026 Borsa Italiana è chiusa il 24, 25 e 31
    # dicembre e nel fine settimana: restano le sedute del 28, 29 e 30
    assert cal.trading_days_between("2026-12-23", "2026-12-31") == 3
    assert natural_days_between("2026-12-23", "2026-12-31") == 8
