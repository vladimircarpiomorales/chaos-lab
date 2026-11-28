"""
Servidor FastAPI + WebSocket para Chaos Lab.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .engine import ChaosEngine
from .mentor import ask_socratic_mentor, build_postmortem_markdown, detect_ollama
from .pty_bridge import stream_container_pty

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Chaos Lab — Linux & Network Incident Simulator", version="1.0.0")
engine = ChaosEngine()

# ---------- Protección del servidor local ----------
# Escuchar en 127.0.0.1 no basta: cualquier web abierta en el navegador puede intentar hablar con
# http://127.0.0.1:7820 (CSRF) o abrir ws://127.0.0.1:7820/ws/terminal/... (CSWSH) y conseguir una
# shell root en el contenedor; y un dominio con DNS rebinding puede hacerse pasar por «mismo origen».
# Defensas: 1) la cabecera Host tiene que ser un nombre permitido (frena el DNS rebinding);
#           2) si el navegador manda Origin, tiene que ser esta misma página (frena CSRF y CSWSH).
# Las herramientas locales (curl, arrancar.sh) no mandan Origin y siguen funcionando.
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _allowed_hosts() -> set[str]:
    hosts = set(_LOCAL_HOSTS)
    bind = os.environ.get("CHAOS_HOST", "").strip()
    if bind and bind not in ("0.0.0.0", "::"):
        hosts.add(bind.strip("[]").lower())
    extra = os.environ.get("CHAOS_ALLOWED_HOSTS", "")  # p. ej. «miportatil.tailnet.ts.net,100.64.0.5»
    hosts.update(h.strip().strip("[]").lower() for h in extra.split(",") if h.strip())
    return hosts


def _hostname(netloc: str) -> str:
    """Nombre sin puerto de un «host:puerto» (también IPv6 entre corchetes)."""
    try:
        return (urlsplit(f"//{netloc}").hostname or "").lower()
    except ValueError:
        return ""


def request_is_allowed(host_header: str | None, origin: str | None) -> bool:
    host_header = (host_header or "").strip().lower()
    if not host_header or _hostname(host_header) not in _allowed_hosts():
        return False
    if origin is None:
        return True  # cliente local que no es un navegador (curl, scripts)
    try:
        o = urlsplit(origin.strip())
    except ValueError:
        return False
    return o.scheme in ("http", "https") and o.netloc.lower() == host_header


@app.middleware("http")
async def local_guard(request: Request, call_next):
    if not request_is_allowed(request.headers.get("host"), request.headers.get("origin")):
        return PlainTextResponse("Origen no permitido", status_code=403)
    return await call_next(request)


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class LaunchRequest(BaseModel):
    scenario_id: str | None = None
    blind_mode: bool = False
    difficulty: str | None = None
    seed: int | None = None
    record: bool = True  # False = lanzamiento de prueba: no suma XP ni historial


class MentorRequest(BaseModel):
    question: str = ""


@app.get("/")
async def index() -> FileResponse:
    # Sin caché: si no, el navegador puede quedarse con un index.html viejo que pide un app.js?v= antiguo
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/api/health")
async def api_health() -> dict[str, Any]:
    return {
        "ok": True,
        "runtime": engine.runtime_health(),
        "ollama": detect_ollama(),
        "panel_url": os.environ.get("CHAOS_PANEL_URL") or None,  # botón «← Panel» opcional
        "active": engine.public_active_view(),
    }


@app.get("/api/catalog")
async def api_catalog() -> dict[str, Any]:
    return engine.get_catalog_view()


@app.post("/api/lab/launch")
async def api_launch(req: LaunchRequest) -> JSONResponse:
    res = engine.launch(
        scenario_id=req.scenario_id,
        blind_mode=req.blind_mode,
        difficulty_filter=req.difficulty,
        seed=req.seed,
        record=req.record,
    )
    if not res.get("ok"):
        return JSONResponse(res, status_code=400)
    return JSONResponse(res)


@app.post("/api/lab/stop")
async def api_stop() -> dict[str, Any]:
    return engine.stop_active()


@app.post("/api/lab/verify")
async def api_verify() -> JSONResponse:
    res = engine.verify()
    if not res.get("ok"):
        return JSONResponse(res, status_code=400)
    return JSONResponse(res)


@app.post("/api/lab/hint")
async def api_hint() -> JSONResponse:
    res = engine.unlock_hint()
    if not res.get("ok"):
        return JSONResponse(res, status_code=400)
    return JSONResponse(res)


@app.post("/api/lab/reveal")
async def api_reveal() -> JSONResponse:
    res = engine.reveal_blind_identity()
    if not res.get("ok"):
        return JSONResponse(res, status_code=400)
    return JSONResponse(res)


@app.post("/api/lab/mentor")
async def api_mentor(req: MentorRequest) -> JSONResponse:
    if not engine.active:
        return JSONResponse({"ok": False, "error": "No hay un laboratorio activo."}, status_code=400)
    return JSONResponse(ask_socratic_mentor(engine.active, req.question))


@app.get("/api/lab/postmortem")
async def api_postmortem() -> JSONResponse:
    if not engine.active:
        raise HTTPException(status_code=400, detail="No hay un laboratorio activo.")
    md = build_postmortem_markdown(engine.active)
    return JSONResponse(
        {
            "ok": True,
            "filename": f"postmortem-{engine.active['id']}-{engine.active['instance']['seed']}.md",
            "markdown": md,
        }
    )


BASE_EXPORT_DIR = Path(__file__).resolve().parent.parent / "exports"


@app.post("/api/lab/export-vault")
async def api_export_vault() -> JSONResponse:
    if not engine.active:
        return JSONResponse({"ok": False, "error": "No hay un laboratorio activo."}, status_code=400)
    import datetime as _dt
    import re as _re

    md = build_postmortem_markdown(engine.active)
    # Carpeta de exportación: CHAOS_EXPORT_DIR (p. ej. una carpeta de tu bóveda de Obsidian) o ./exports
    dest_dir = Path(os.path.expanduser(os.environ.get("CHAOS_EXPORT_DIR", str(BASE_EXPORT_DIR))))
    dest_dir.mkdir(parents=True, exist_ok=True)
    hoy = _dt.date.today().isoformat()
    slug = _re.sub(r"[^A-Za-z0-9\-_]+", "-", engine.active["id"]).strip("-")
    fname = f"{hoy}-chaoslab-{slug}-{engine.active['instance']['seed']}.md"
    fpath = dest_dir / fname
    front = (
        f"---\n"
        f"date: {hoy}\n"
        f"category: ChaosLab\n"
        f"scenario: {engine.active['id']}\n"
        f"tags: [chaos-lab, postmortem, sre]\n"
        f"---\n\n"
    )
    fpath.write_text(front + md, encoding="utf-8")
    return JSONResponse({"ok": True, "filename": fname, "path": str(fpath)})


@app.websocket("/ws/terminal/{role}")
async def ws_terminal(websocket: WebSocket, role: str) -> None:
    # El middleware http no pasa por los WebSocket: misma comprobación aquí, antes de aceptar.
    if not request_is_allowed(websocket.headers.get("host"), websocket.headers.get("origin")):
        await websocket.close(code=1008)  # policy violation
        return
    node = engine.get_node_runtime(role)
    if not node:
        await websocket.accept()
        await websocket.send_text('{"type":"output","data":"\\r\\n[No hay contenedor activo para este nodo]\\r\\n"}')
        await websocket.close()
        return
    await stream_container_pty(
        websocket=websocket,
        node_info=node,
        on_command_line=engine.record_command_line,
    )


def main() -> None:
    import uvicorn

    host = os.environ.get("CHAOS_HOST", "127.0.0.1")
    port = int(os.environ.get("CHAOS_PORT", "7820"))
    uvicorn.run("chaos_lab.server:app", host=host, port=port, reload=False, log_level="info")


if __name__ == "__main__":
    main()
