"""Universo dei titoli da monitorare.

La lista predefinita riproduce il paniere FTSE MIB. La composizione
dell'indice cambia con le revisioni trimestrali: aggiornare la lista qui
oppure passare un elenco personalizzato con la variabile d'ambiente
GANN_TICKERS (codici separati da virgola, es. "ENI.MI,ENEL.MI,ISP.MI").
"""

import os

FTSE_MIB = {
    "A2A.MI": "A2A",
    "AMP.MI": "Amplifon",
    "AZM.MI": "Azimut",
    "BAMI.MI": "Banco BPM",
    "BGN.MI": "Banca Generali",
    "BMED.MI": "Banca Mediolanum",
    "BMPS.MI": "Banca Monte dei Paschi",
    "BPE.MI": "BPER Banca",
    "BPSO.MI": "Banca Popolare di Sondrio",
    "BC.MI": "Brunello Cucinelli",
    "CPR.MI": "Campari",
    "DIA.MI": "DiaSorin",
    "ENEL.MI": "Enel",
    "ENI.MI": "Eni",
    "RACE.MI": "Ferrari",
    "FBK.MI": "FinecoBank",
    "G.MI": "Generali",
    "HER.MI": "Hera",
    "INW.MI": "Inwit",
    "IP.MI": "Interpump",
    "ISP.MI": "Intesa Sanpaolo",
    "IG.MI": "Italgas",
    "IVG.MI": "Iveco",
    "LDO.MI": "Leonardo",
    "MB.MI": "Mediobanca",
    "MONC.MI": "Moncler",
    "NEXI.MI": "Nexi",
    "PIRC.MI": "Pirelli",
    "PST.MI": "Poste Italiane",
    "PRY.MI": "Prysmian",
    "REC.MI": "Recordati",
    "SPM.MI": "Saipem",
    "SRG.MI": "Snam",
    "STLAM.MI": "Stellantis",
    "STMMI.MI": "STMicroelectronics",
    "TIT.MI": "Telecom Italia",
    "TEN.MI": "Tenaris",
    "TRN.MI": "Terna",
    "UCG.MI": "UniCredit",
    "UNI.MI": "Unipol",
}


def get_universe() -> dict[str, str]:
    """Restituisce il dizionario ticker -> nome dei titoli da analizzare."""
    custom = os.getenv("GANN_TICKERS")
    if not custom:
        return dict(FTSE_MIB)
    tickers = [t.strip().upper() for t in custom.split(",") if t.strip()]
    return {t: FTSE_MIB.get(t, t.removesuffix(".MI")) for t in tickers}
