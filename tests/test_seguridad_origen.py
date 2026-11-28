"""El servidor local rechaza peticiones de otras webs (CSRF/CSWSH) y Host ajenos (DNS rebinding)."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from chaos_lab import server
from chaos_lab.server import request_is_allowed

client = TestClient(server.app, base_url="http://127.0.0.1:7820")


@pytest.mark.parametrize(
    "host, origin, ok",
    [
        ("127.0.0.1:7820", None, True),  # curl / arrancar.sh
        ("127.0.0.1:7820", "http://127.0.0.1:7820", True),  # la propia página
        ("localhost:7820", "http://localhost:7820", True),
        ("[::1]:7820", "http://[::1]:7820", True),
        ("127.0.0.1:7820", "https://web-maliciosa.example", False),  # CSRF / CSWSH
        ("127.0.0.1:7820", "http://localhost:7820", False),  # otro origen aunque sea local
        ("127.0.0.1:7820", "http://127.0.0.1:9999", False),  # otro puerto = otro origen
        ("127.0.0.1:7820", "null", False),  # iframe sandbox / file://
        ("ataque.example:7820", "http://ataque.example:7820", False),  # DNS rebinding
        ("ataque.example:7820", None, False),
        ("", None, False),
        (None, None, False),
    ],
)
def test_request_is_allowed(host, origin, ok):
    assert request_is_allowed(host, origin) is ok


def test_hosts_extra_por_entorno(monkeypatch):
    monkeypatch.setenv("CHAOS_ALLOWED_HOSTS", "portatil.tailnet.ts.net, 100.64.0.5")
    assert request_is_allowed("portatil.tailnet.ts.net:7820", "http://portatil.tailnet.ts.net:7820")
    assert request_is_allowed("100.64.0.5:7820", None)
    assert not request_is_allowed("otro.example:7820", None)


def test_http_misma_pagina_pasa():
    assert client.get("/api/catalog").status_code == 200


def test_http_post_desde_otra_web_403():
    r = client.post("/api/lab/stop", headers={"Origin": "https://web-maliciosa.example"})
    assert r.status_code == 403


def test_http_host_ajeno_403():
    r = client.get("/api/catalog", headers={"Host": "ataque.example:7820"})
    assert r.status_code == 403


def test_websocket_desde_otra_web_se_cierra():
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect(
            "ws://127.0.0.1:7820/ws/terminal/main", headers={"Origin": "https://web-maliciosa.example"}
        ) as ws:
            ws.receive_text()
    assert e.value.code == 1008


def test_websocket_misma_pagina_se_acepta():
    # Sin laboratorio activo el servidor acepta, avisa y cierra: lo importante es que llega a aceptar.
    with client.websocket_connect(
        "ws://127.0.0.1:7820/ws/terminal/main", headers={"Origin": "http://127.0.0.1:7820"}
    ) as ws:
        assert "No hay contenedor activo" in ws.receive_text()
