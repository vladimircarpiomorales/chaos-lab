"""Packs de escenarios definidos como datos (JSON) en lugar de código.

Cada fichero `chaos_lab/packs/<pack>.json` es una lista de objetos. El constructor genérico de este módulo
los convierte en entradas de SCENARIO_CATALOG (ver `load_pack`). Hoy solo hay un tipo de pack, «reto»: un nodo
`lpic` (imagen `lpic-debian`) donde el jugador trabaja como `alumno` en un directorio de reto, con un script de
preparación y un corrector por script (`comprueba "etiqueta" comando…`).

Campos de cada objeto: id, reto (id original, es el nombre del directorio), title, briefing, hints (3),
solution_summary, difficulty, points, estimated_min, tipo, certs, tags, objetivos_lpi, category, blind_alert,
preparar, comprobar.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Callable

PACKS_DIR = Path(__file__).parent
RETOS_BASE = "/home/alumno/retos"
ROLE = "lpic"


def _setup_sh(reto: str, preparar: str) -> str:
    """Envoltorio común de preparación de un reto (como root; deja el directorio del reto a nombre de alumno)."""
    d = f"{RETOS_BASE}/{reto}"
    return (
        f'set -u; export RETO={d}; rm -rf "$RETO"; mkdir -p "$RETO"; cd "$RETO"; (\n{preparar}\n); rc=$?; '
        'find "$RETO" ! -perm /6000 -exec chown -h alumno:alumno {} +; exit $rc'
    )


def _builder(item: dict[str, Any]) -> Callable[[random.Random], dict[str, Any]]:
    reto = item["reto"]
    workdir = f"{RETOS_BASE}/{reto}"

    def build(rng: random.Random) -> dict[str, Any]:
        return {
            "vars": {},
            "nodes": [
                {
                    "role": ROLE,
                    "distro": "lpic-debian",
                    "shell": "/bin/bash",
                    "default_user": "alumno",
                    "workdir": workdir,
                    "setup_timeout": 90,
                    "setup_sh": _setup_sh(reto, item["preparar"]),
                }
            ],
            # Las sondas salen de ejecutar el corrector (el motor las rellena al lanzar)
            "checks": [],
            "check_script": {
                "node": ROLE,
                "cwd": workdir,
                "script": f"set -u\nexport RETO={workdir}\n" + item["comprobar"],
            },
            "hints": list(item["hints"]),
            "topology": {
                "entry": None,
                "nodes": {ROLE: {"runs": "Debian · tu puesto de trabajo", "look": ["el directorio del reto", "el manual del comando (man)"]}},
                "links": [],
                "checks": {},
            },
            "solution_summary": item["solution_summary"],
        }

    return build


def load_pack(name: str) -> list[dict[str, Any]]:
    """Entradas de SCENARIO_CATALOG del pack `name` (chaos_lab/packs/<name>.json)."""
    items = json.loads((PACKS_DIR / f"{name}.json").read_text(encoding="utf-8"))
    out = []
    for it in items:
        out.append(
            {
                "id": it["id"],
                "tipo": it.get("tipo", "averia"),
                "title": it["title"],
                "category": it["category"],
                "difficulty": it["difficulty"],
                "points": it["points"],
                "estimated_min": it["estimated_min"],
                "tags": it["tags"],
                "certs": it["certs"],
                "objetivos_lpi": it.get("objetivos_lpi", []),
                "blind_alert": it["blind_alert"],
                "briefing": it["briefing"],
                "builder": _builder(it),
            }
        )
    return out
