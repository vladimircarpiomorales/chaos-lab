"""Packs de escenarios definidos como datos (JSON) en lugar de código.

Cada fichero `chaos_lab/packs/<pack>.json` es una lista de objetos. El constructor genérico de este módulo
los convierte en entradas de SCENARIO_CATALOG (ver `load_pack`). Hoy solo hay un tipo de pack, «reto»: un nodo
`lpic` (imagen `lpic-debian`) donde el jugador trabaja como `alumno` en un directorio de reto, con un script de
preparación y un corrector por script (`comprueba "etiqueta" comando…`).

Segundo tipo de pack, «multinodo» (p. ej. `lpic2_ldap.json`): el objeto trae `nodos` en vez de un único nodo `lpic`.
Cada elemento de `nodos`: role, distro, preparar (script como root en ese nodo; se ejecuta en el orden de la lista),
y opcionales workdir, default_user (por defecto root), shell, runs, look, caps, setup_timeout. `enlaces` (opcional)
son las flechas del esquema {from, to, via}. `comprobar` es una lista de bloques {node, script, cwd?}: uno por nodo,
cada uno con líneas `comprueba "etiqueta" comando…` (las sondas se unen en el orden de la lista). Los nodos
comparten red y se resuelven por nombre de rol.

Redes «manuales» (pack `redes.json`, estilo containerlab): el objeto añade `redes` (lista de nombres cortos, p. ej.
["lan", "transito"]; se crean como `chaoslab-<nombre>`) y `red_modo: "manual"` (redes sin IPAM: el motor no pone IPs ni
rutas, las pone el `preparar` de cada nodo). Cada nodo declara `redes` (sus redes; la i-ésima es siempre `eth{i}`),
`ips` ({red: ip} «de diseño», para el esquema y /etc/chaos_nodes.env; nunca una avería) y opcionalmente `sysctl_rw: true`
(`--security-opt systempaths=unconfined`, para `sysctl -w net.ipv4.ip_forward=1`). En `caps` van NET_ADMIN y NET_RAW.

Campos de cada objeto: id, reto (id original, es el nombre del directorio), title, briefing, hints (3),
solution_summary, difficulty, points, estimated_min, tipo, certs, tags, objetivos_lpi, category, blind_alert,
preparar, comprobar; opcional `i18n` ({"en": {title, briefing, hints[], solution_summary, blind_alert}}: traducción
al inglés, cada campo opcional; el español sigue siendo la fuente y el respaldo; lo normal es dejarla en
packs/en/<pack>.json como {id: {…}}, con además checks[] (etiquetas de las sondas en orden), nodes{rol: {runs, look[]}}
y links[] (via de cada enlace)); opcional `distro` (por defecto lpic-debian; el reto RPM usa lpic-fedora).
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Callable

PACKS_DIR = Path(__file__).parent
RETOS_BASE = "/home/alumno/retos"
ROLE = "lpic"
DEFAULT_DISTRO = "lpic-debian"
DISTRO_NOMBRE = {"lpic-debian": "Debian", "lpic-fedora": "Fedora"}


def _setup_sh(reto: str, preparar: str) -> str:
    """Envoltorio común de preparación de un reto (como root; deja el directorio del reto a nombre de alumno)."""
    d = f"{RETOS_BASE}/{reto}"
    return (
        f'set -u; export RETO={d}; rm -rf "$RETO"; mkdir -p "$RETO"; cd "$RETO"; (\n{preparar}\n); rc=$?; '
        'find "$RETO" ! -perm /6000 -exec chown -h alumno:alumno {} +; exit $rc'
    )


def _builder(item: dict[str, Any]) -> Callable[[random.Random], dict[str, Any]]:
    reto = item["reto"]
    distro = item.get("distro", DEFAULT_DISTRO)
    workdir = f"{RETOS_BASE}/{reto}"

    def build(rng: random.Random) -> dict[str, Any]:
        return {
            "vars": {},
            "nodes": [
                {
                    "role": ROLE,
                    "distro": distro,
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
                "nodes": {ROLE: {"runs": f"{DISTRO_NOMBRE.get(distro, distro)} · tu puesto de trabajo", "look": ["el directorio del reto", "el manual del comando (man)"]}},
                "links": [],
                "checks": {},
            },
            "solution_summary": item["solution_summary"],
        }

    return build


def _builder_multi(item: dict[str, Any]) -> Callable[[random.Random], dict[str, Any]]:
    """Constructor de un reto con varios nodos (ver la cabecera del módulo)."""

    def build(rng: random.Random) -> dict[str, Any]:
        nodes, topo_nodes = [], {}
        for nd in item["nodos"]:
            node = {
                "role": nd["role"],
                "distro": nd["distro"],
                "shell": nd.get("shell", "/bin/bash"),
                "default_user": nd.get("default_user", "root"),
                "setup_timeout": nd.get("setup_timeout", 120),
                "setup_sh": f"set -u\n(\n{nd['preparar']}\n)",
            }
            if nd.get("workdir"):
                node["workdir"] = nd["workdir"]
            if nd.get("caps"):
                node["caps"] = list(nd["caps"])
            if nd.get("redes"):
                node["networks"] = list(nd["redes"])
            if nd.get("ips"):
                node["design_ips"] = dict(nd["ips"])
            if nd.get("sysctl_rw"):
                node["sysctl_rw"] = True
            nodes.append(node)
            topo_nodes[nd["role"]] = {"runs": nd.get("runs", ""), "look": list(nd.get("look", []))}
        blocks = []
        for blk in item["comprobar"]:
            b = {"node": blk["node"], "script": "set -u\n" + blk["script"]}
            if blk.get("cwd"):
                b["cwd"] = blk["cwd"]
            if blk.get("marca"):
                b["marca"] = blk["marca"]
            blocks.append(b)
        extra: dict[str, Any] = {}
        if item.get("redes"):
            extra["networks"] = list(item["redes"])
        if item.get("red_modo"):
            extra["network_mode"] = item["red_modo"]
        return {
            **extra,
            "vars": {},
            "nodes": nodes,
            "checks": [],
            "check_script": blocks,
            "hints": list(item["hints"]),
            "topology": {
                "entry": None,
                "nodes": topo_nodes,
                "links": [dict(l) for l in item.get("enlaces", [])],
                "checks": {},
            },
            "solution_summary": item["solution_summary"],
        }

    return build


def load_pack(name: str) -> list[dict[str, Any]]:
    """Entradas de SCENARIO_CATALOG del pack `name` (chaos_lab/packs/<name>.json)."""
    items = json.loads((PACKS_DIR / f"{name}.json").read_text(encoding="utf-8"))
    # Traducción inglesa aparte, para no tocar el pack en español: packs/en/<name>.json = {id: {title, briefing, …}}
    en_file = PACKS_DIR / "en" / f"{name}.json"
    en_map = json.loads(en_file.read_text(encoding="utf-8")) if en_file.exists() else {}
    out = []
    for it in items:
        if not it.get("i18n") and isinstance(en_map.get(it["id"]), dict):
            it = {**it, "i18n": {"en": en_map[it["id"]]}}
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
                **({"i18n": it["i18n"]} if it.get("i18n") else {}),
                "builder": _builder_multi(it) if "nodos" in it else _builder(it),
            }
        )
    return out
