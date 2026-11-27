"""Reglas «sin spoilers» de Chaos Lab (ver CONTRIBUTING.md).

1. Lo que ve el jugador antes de resolver (etiquetas de sondas y esquema) no contiene valores secretos.
2. «Dónde mirar» (look) no repite literalmente un comando o fichero entre `backticks` de las pistas.
"""
import re

import pytest

from chaos_lab.scenarios import SCENARIO_CATALOG, instantiate_scenario

# Variables que son la respuesta o una prueba de que está resuelto. Un escenario nuevo con un dato
# secreto debe llamarlo así (o añadir el nombre aquí).
SECRET_VARS = {"real_port", "wrong_port", "rogue_name", "rpass", "c2_domain", "hidden_dir", "decoys", "token", "val_tok"}
SEEDS = [1, 2, 3, 4, 5]
IDS = [s["id"] for s in SCENARIO_CATALOG]


def _visible_texts(inst):
    """(dónde, texto) de todo lo que se ve antes de resolver."""
    out = [(f"sonda {c['id']}", c["label"]) for c in inst["checks"]]
    topo = inst.get("topology") or {}
    if topo.get("entry"):
        out.append(("entrada", topo["entry"].get("via", "")))
    for role, n in topo.get("nodes", {}).items():
        out.append((f"{role}.runs", n.get("runs", "")))
        out += [(f"{role}.look", x) for x in n.get("look", [])]
    out += [(f"flecha {i}", l.get("via", "")) for i, l in enumerate(topo.get("links", []))]
    return out


def _secret_values(inst):
    vals = []
    for k, v in inst["vars"].items():
        if k in SECRET_VARS:
            vals += [str(x) for x in v] if isinstance(v, (list, tuple)) else [str(v)]
    return [v for v in vals if len(v) >= 3]


@pytest.mark.parametrize("sid", IDS)
@pytest.mark.parametrize("seed", SEEDS)
def test_sin_valores_secretos_a_la_vista(sid, seed):
    inst = instantiate_scenario(sid, seed)
    secretos = _secret_values(inst)
    fugas = [(donde, s) for donde, txt in _visible_texts(inst) for s in secretos if s in txt]
    assert not fugas, f"{sid}: valor secreto visible antes de resolver: {fugas}"


# Ficheros comunes del laboratorio (no son pista de ningún escenario)
GENERIC_LOOK = {"/etc/chaos_nodes.env"}
BY_ID = {s["id"]: s for s in SCENARIO_CATALOG}


@pytest.mark.parametrize("sid", IDS)
def test_look_no_repite_las_pistas(sid):
    inst = instantiate_scenario(sid, 1)
    en_pistas = {m.strip() for h in inst["hints"] for m in re.findall(r"`([^`]+)`", h)}
    publico = BY_ID[sid]["briefing"] + " " + BY_ID[sid]["blind_alert"]  # lo que ya sabe el jugador
    topo = inst.get("topology") or {}
    repetidos = [
        (role, x)
        for role, n in topo.get("nodes", {}).items()
        for x in n.get("look", [])
        if x.strip() in en_pistas and x.strip() not in GENERIC_LOOK and x.strip() not in publico
    ]
    assert not repetidos, f"{sid}: «dónde mirar» repite comandos de las pistas: {repetidos}"
