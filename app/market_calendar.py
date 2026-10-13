"""Conteggio dei giorni di contrattazione sul calendario di Borsa Italiana."""

import logging

import numpy as np
import pandas as pd

from . import config

logger = logging.getLogger(__name__)


class TradingCalendar:
    """Elenco delle sedute di borsa aperta in un intervallo di date."""

    def __init__(self, start, end, calendar_name: str = config.MARKET_CALENDAR):
        start = pd.Timestamp(start).normalize()
        end = pd.Timestamp(end).normalize()
        try:
            import pandas_market_calendars as mcal

            days = mcal.get_calendar(calendar_name).valid_days(start, end)
            days = pd.DatetimeIndex(days).tz_localize(None).normalize()
        except Exception:  # libreria assente o calendario non disponibile
            logger.warning(
                "Calendario %s non disponibile: uso i giorni lavorativi "
                "(lun-ven) senza festività.",
                calendar_name,
            )
            days = pd.bdate_range(start, end)
        self._days = np.asarray(days.values, dtype="datetime64[ns]")

    @property
    def days(self) -> pd.DatetimeIndex:
        return pd.DatetimeIndex(self._days)

    def trading_days_between(self, start, end) -> int:
        """Sedute successive a `start` fino a `end` incluso."""
        start = np.datetime64(pd.Timestamp(start).normalize(), "ns")
        end = np.datetime64(pd.Timestamp(end).normalize(), "ns")
        if end <= start:
            return 0
        lo = np.searchsorted(self._days, start, side="right")
        hi = np.searchsorted(self._days, end, side="right")
        return int(hi - lo)


def natural_days_between(start, end) -> int:
    """Giorni solari trascorsi tra due date."""
    return (pd.Timestamp(end).normalize() - pd.Timestamp(start).normalize()).days
