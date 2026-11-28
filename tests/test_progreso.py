"""Exportar / importar el progreso: ida y vuelta, validación y copia del progreso anterior."""

import json

import pytest
from fastapi.testclient import TestClient

from chaos_lab import engine as engine_mod
from chaos_lab import server
from chaos_lab.engine import sanitize_progress

ORIGEN = {"Origin": "http://127.0.0.1:7820"}

VALIDO = {
    "solved": {
        "net-nginx-bad-gateway": {"best_time_s": 1050, "best_rank": "B", "count": 1, "last_solved": "2026-11-27T00:47:00"}
    },
    "history": [
        {
            "id": "net-nginx-bad-gateway",
            "title": "502 Bad Gateway",
            "blind_mode": False,
            "elapsed_s": 1050,
            "rank": "B",
            "xp": 180,
            "hints_used": 0,
            "at": "2026-11-27 00:47",
        }
    ],
    "total_xp": 180,
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(engine_mod, "STATE_FILE", tmp_path / "state.json")
    return TestClient(server.app, base_url="http://127.0.0.1:7820")


def test_ida_y_vuelta(client, tmp_path):
    (tmp_path / "state.json").write_text(json.dumps(VALIDO))
    r = client.get("/api/progress/export")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    exportado = r.json()
    assert exportado["format"] == "chaos-lab-progress" and exportado["total_xp"] == 180

    (tmp_path / "state.json").write_text(json.dumps({"solved": {}, "history": [], "total_xp": 0}))
    r = client.post("/api/progress/import", content=json.dumps(exportado), headers=ORIGEN)
    assert r.status_code == 200 and r.json()["solved"] == 1
    assert json.loads((tmp_path / "state.json").read_text())["total_xp"] == 180
    copias = list(tmp_path.glob("state.antes-de-importar-*.json"))
    assert len(copias) == 1 and json.loads(copias[0].read_text())["total_xp"] == 0


def test_acepta_state_json_copiado_tal_cual():
    assert sanitize_progress(VALIDO)["total_xp"] == 180


def test_quita_campos_desconocidos_y_corrige_rango():
    datos = json.loads(json.dumps(VALIDO))
    datos["solved"]["net-nginx-bad-gateway"]["best_rank"] = "<script>"
    datos["solved"]["net-nginx-bad-gateway"]["extra"] = "x"
    datos["admin"] = True
    limpio = sanitize_progress(datos)
    assert limpio["solved"]["net-nginx-bad-gateway"]["best_rank"] == "C"
    assert "extra" not in limpio["solved"]["net-nginx-bad-gateway"] and "admin" not in limpio


@pytest.mark.parametrize(
    "malo",
    [
        [],
        {"format": "otra-cosa"},
        {"solved": []},
        {"solved": {"../../etc/passwd": {}}},
        {"solved": {}, "history": [], "total_xp": -5},
        {"solved": {}, "history": [], "total_xp": "mucho"},
        {"solved": {}, "history": [{"id": "x", "xp": True}]},
    ],
)
def test_rechaza_progresos_no_validos(malo):
    with pytest.raises(ValueError):
        sanitize_progress(malo)


def test_import_no_json_400_y_no_toca_nada(client, tmp_path):
    (tmp_path / "state.json").write_text(json.dumps(VALIDO))
    r = client.post("/api/progress/import", content=b"esto no es json", headers=ORIGEN)
    assert r.status_code == 400 and r.json()["ok"] is False
    assert json.loads((tmp_path / "state.json").read_text())["total_xp"] == 180


def test_import_desde_otra_web_403(client):
    r = client.post("/api/progress/import", content=json.dumps(VALIDO), headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_import_demasiado_grande_413(client):
    r = client.post("/api/progress/import", content=b" " * 1_000_001, headers=ORIGEN)
    assert r.status_code == 413


@pytest.mark.parametrize("texto", ['{"total_xp": Infinity}', '{"total_xp": NaN}', '{"total_xp": 1.5}'])
def test_numeros_no_enteros_400(client, texto):
    r = client.post("/api/progress/import", content=texto, headers=ORIGEN)
    assert r.status_code == 400


def test_dos_importaciones_seguidas_no_pisan_la_copia(client, tmp_path):
    (tmp_path / "state.json").write_text(json.dumps(VALIDO))
    for _ in range(2):
        assert client.post("/api/progress/import", content=json.dumps(VALIDO), headers=ORIGEN).status_code == 200
    assert len(list(tmp_path.glob("state.antes-de-importar-*.json"))) == 2


def test_content_length_enorme_413_sin_leer(client):
    r = client.post("/api/progress/import", content=b"{}", headers={**ORIGEN, "Content-Length": "999999999"})
    assert r.status_code == 413
