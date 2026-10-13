"""Parametri di configurazione dell'algoritmo e dell'applicazione.

I valori principali possono essere sovrascritti con variabili d'ambiente,
così da non dover modificare il codice.
"""

import os


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


# --- Dati ---------------------------------------------------------------

# "yahoo" (dati reali tramite yfinance) oppure "demo" (serie sintetiche,
# utili per provare l'app senza accesso a Internet).
DATA_SOURCE = os.getenv("GANN_DATA_SOURCE", "yahoo").lower()

# Profondità dello storico scaricato (sintassi di yfinance).
HISTORY_PERIOD = os.getenv("GANN_HISTORY_PERIOD", "2y")

# Durata della cache in memoria dei dati scaricati, in secondi.
CACHE_TTL_SECONDS = _env_int("GANN_CACHE_TTL", 900)

# Codice del calendario di borsa usato da pandas_market_calendars.
MARKET_CALENDAR = "XMIL"

# Numero minimo di sedute necessarie per analizzare un titolo.
MIN_BARS = 60


# --- Output -------------------------------------------------------------

# Numero di titoli restituiti (le specifiche chiedono 3 o 4).
DEFAULT_RESULTS = _env_int("GANN_RESULTS", 4)


# --- Parametri di Gann --------------------------------------------------

# Finestre (in giorni solari) per la ricerca dei pivot di ancoraggio.
PIVOT_WINDOWS = (30, 60, 180, 365)

# Sedute che devono seguire un massimo/minimo perché sia un pivot confermato.
PIVOT_MIN_AGE = _env_int("GANN_PIVOT_MIN_AGE", 5)

# Periodo dell'Average True Range e numero di sedute su cui farne la media
# per ottenere il fattore di scala prezzo/tempo (1x1).
ATR_PERIOD = 14
SCALE_LOOKBACK = 252

# Tolleranza di "contatto" con una retta o un livello di prezzo, espressa
# come frazione dell'ATR corrente.
PRICE_TOLERANCE_ATR = _env_float("GANN_PRICE_TOLERANCE_ATR", 0.5)

# Tolleranza della squadratura prezzo/tempo: scarto relativo ammesso tra
# unità di prezzo percorse e giorni trascorsi (minimo 1 unità).
SQUARING_TOLERANCE = _env_float("GANN_SQUARING_TOLERANCE", 0.05)

# Angoli del Quadrato di Nove considerati.
SQUARE_OF_NINE_DEGREES = (90, 180, 360)

# Cicli temporali primari (giorni solari) e tolleranza in giorni.
TIME_CYCLES = (30, 60, 90, 180)
CYCLE_TOLERANCE_DAYS = _env_int("GANN_CYCLE_TOLERANCE_DAYS", 2)

# Pesi della matrice di confidenza (somma = 100).
WEIGHTS = {
    "angolo_1x1": 30,
    "squadratura": 25,
    "quadrato_nove": 25,
    "cicli": 20,
}
