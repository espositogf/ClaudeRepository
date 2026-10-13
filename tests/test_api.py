import pytest
from fastapi.testclient import TestClient

from app import config, data
from app.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(config, "DATA_SOURCE", "demo")
    data.clear_cache()
    return TestClient(app)


def test_dashboard(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Previsioni Gann" in res.text


def test_previsioni_demo(client):
    res = client.get("/api/previsioni")
    assert res.status_code == 200
    body = res.json()
    assert body["fonte_dati"] == "demo"
    assert body["titoli_analizzati"] == 40
    assert 1 <= len(body["titoli"]) <= 4
    confidences = [t["confidenza"] for t in body["titoli"]]
    assert confidences == sorted(confidences, reverse=True)
    for t in body["titoli"]:
        assert t["azione"] in ("COMPRARE", "VENDERE")
        agreeing = sum(c["peso"] for c in t["condizioni"] if c["concorde"])
        assert agreeing == t["confidenza"]


def test_data_source_error_returns_503(client, monkeypatch):
    def fail(*args, **kwargs):
        raise data.DataSourceError("rete non disponibile")

    monkeypatch.setattr("app.analysis.get_history", fail)
    res = client.get("/api/previsioni")
    assert res.status_code == 503
    assert "rete" in res.json()["detail"]
