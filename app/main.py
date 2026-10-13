"""Web app FastAPI: API delle previsioni e dashboard a schede."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .analysis import run_forecast
from .data import DataSourceError, clear_cache

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Previsioni Gann - Borsa Italiana",
    description="Selezione di titoli FTSE MIB basata sulla teoria di W.D. Gann.",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"stato": "ok", "fonte_dati": config.DATA_SOURCE}


@app.get("/api/previsioni")
def previsioni(
    numero: int = Query(config.DEFAULT_RESULTS, ge=1, le=10, description="Numero di titoli da restituire"),
    aggiorna: bool = Query(False, description="Ignora la cache e scarica di nuovo i dati"),
):
    if aggiorna:
        clear_cache()
    try:
        return run_forecast(limit=numero)
    except DataSourceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
