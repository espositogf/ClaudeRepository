# Previsioni Gann · Borsa Italiana

Web app che analizza i titoli del paniere FTSE MIB secondo la teoria di
W.D. Gann e restituisce **3 o 4 titoli** con l'azione suggerita
(`COMPRARE` / `VENDERE`) e una **percentuale di confidenza**. L'interfaccia
è una dashboard a schede, senza grafici.

> Le indicazioni sono generate automaticamente a scopo di studio e non
> costituiscono consulenza finanziaria.

## Avvio rapido

Serve Python 3.10 o successivo.

```bash
python -m venv .venv
source .venv/bin/activate          # su Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Aprire <http://localhost:8000> nel browser.

Per provare l'app senza connessione a Internet si possono usare dati
sintetici (la dashboard lo segnala con un avviso):

```bash
GANN_DATA_SOURCE=demo uvicorn app.main:app --reload
```

Su Windows (PowerShell): `$env:GANN_DATA_SOURCE="demo"; uvicorn app.main:app --reload`.

## API

| Metodo | Percorso | Descrizione |
| --- | --- | --- |
| GET | `/` | Dashboard a schede |
| GET | `/api/previsioni?numero=4&aggiorna=false` | Titoli selezionati in JSON (`aggiorna=true` ignora la cache) |
| GET | `/api/health` | Stato del servizio |
| GET | `/docs` | Documentazione interattiva generata da FastAPI |

## Come funziona

### Dati di input

| Dato | Come viene ottenuto | Modulo |
| --- | --- | --- |
| Serie OHLCV giornaliere (2 anni) | `yfinance`, ticker con suffisso `.MI` | `app/data.py` |
| Conferma settimanale | ricampionamento settimanale delle serie giornaliere | `app/gann.py` |
| Pivot di ancoraggio | massimi/minimi nelle finestre di 30, 60, 180 e 365 giorni | `app/gann.py` |
| Giorni solari e di contrattazione | `datetime` e `pandas_market_calendars` (calendario `XMIL`) | `app/market_calendar.py` |
| Fattore di scala 1x1 | media dell'ATR(14) sulle ultime 252 sedute | `app/gann.py` |
| Universo dei titoli | 40 titoli FTSE MIB, modificabile | `app/universe.py` |

Un massimo o un minimo diventa pivot solo se è seguito da almeno 5 sedute
che non lo hanno superato (pivot confermato).

### Matrice di confidenza

Per ogni pivot vengono valutate quattro condizioni. Per ciascuna si tiene il
segnale più preciso tra tutti i pivot.

| Condizione | Quando è verificata | Direzione | Peso |
| --- | --- | --- | :---: |
| Intersezione Angoli 1x1 | prezzo entro ½ ATR dalla retta 1x1 (pivot ± scala × sedute) | 1x1 ascendente da un minimo = supporto → COMPRARE; discendente da un massimo = resistenza → VENDERE | 30% |
| Squadratura Prezzo/Tempo | unità di prezzo percorse (movimento / scala) ≈ giorni solari dal pivot (±5%, minimo 1 unità) | quadrato completato = possibile inversione: dopo un rialzo → VENDERE, dopo un ribasso → COMPRARE | 25% |
| Quadrato di Nove | prezzo entro ½ ATR da un livello (√pivot ± gradi/180)² a 90°, 180° o 360° | livelli sopra un minimo = resistenze → VENDERE; sotto un massimo = supporti → COMPRARE | 25% |
| Cicli Temporali Primari | 30, 60, 90 o 180 giorni solari dal pivot (±2 giorni) | fine ciclo = possibile inversione: dopo un minimo → VENDERE, dopo un massimo → COMPRARE | 20% |

L'azione è la direzione con la somma dei pesi più alta, e la **confidenza è
quella somma**: le condizioni in contrasto non vengono conteggiate e sulla
scheda sono evidenziate in giallo. In caso di parità decide la tendenza
settimanale (massimi e minimi crescenti o decrescenti nelle ultime 4
settimane rispetto alle 4 precedenti).

I titoli vengono ordinati per confidenza, poi per conferma della tendenza
settimanale, poi per precisione dei segnali. Vengono mostrati i primi 4.
Se meno titoli presentano condizioni verificate, ne vengono mostrati meno.

## Configurazione

Le soglie sono in `app/config.py`. Le principali si possono cambiare anche
con variabili d'ambiente:

| Variabile | Predefinito | Significato |
| --- | --- | --- |
| `GANN_DATA_SOURCE` | `yahoo` | `yahoo` per i dati reali, `demo` per dati sintetici |
| `GANN_TICKERS` | paniere FTSE MIB | elenco personalizzato, es. `ENI.MI,ENEL.MI,ISP.MI` |
| `GANN_RESULTS` | `4` | numero di titoli mostrati |
| `GANN_HISTORY_PERIOD` | `2y` | profondità dello storico |
| `GANN_CACHE_TTL` | `900` | durata della cache dei dati, in secondi |
| `GANN_PRICE_TOLERANCE_ATR` | `0.5` | tolleranza di contatto per 1x1 e Quadrato di Nove, in ATR |
| `GANN_SQUARING_TOLERANCE` | `0.05` | tolleranza relativa della squadratura |
| `GANN_CYCLE_TOLERANCE_DAYS` | `2` | tolleranza dei cicli, in giorni |
| `GANN_PIVOT_MIN_AGE` | `5` | sedute necessarie a confermare un pivot |

La composizione del FTSE MIB cambia con le revisioni trimestrali: verificare
periodicamente l'elenco in `app/universe.py`.

## Sviluppo

```bash
pip install -r requirements-dev.txt
pytest
```

Lo stile della dashboard usa Tailwind CSS compilato in
`app/static/tailwind.css`, così l'app non dipende da una CDN esterna. Dopo
aver cambiato le classi in `app/static/index.html`, rigenerarlo con:

```bash
npx tailwindcss@3.4.17 -c styles/tailwind.config.js -i styles/input.css -o app/static/tailwind.css --minify
```

## Struttura

```
app/
  main.py             FastAPI: dashboard e API
  analysis.py         analisi dei titoli, confidenza e classifica
  gann.py             ATR, pivot, angolo 1x1, squadratura, Quadrato di Nove, cicli
  data.py             download da Yahoo Finance, dati demo e cache
  market_calendar.py  giorni solari e di contrattazione (XMIL)
  universe.py         titoli FTSE MIB
  config.py           parametri
  static/             dashboard HTML e CSS
styles/               sorgenti Tailwind
tests/                test automatici
```
