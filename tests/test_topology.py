"""El esquema de topología debe cuadrar con los nodos y sondas reales del escenario."""
import pytest

from chaos_lab.engine import _public_topology
from chaos_lab.scenarios import SCENARIO_CATALOG, instantiate_scenario

CON_ESQUEMA = [s["id"] for s in SCENARIO_CATALOG if instantiate_scenario(s["id"], 1).get("topology")]


def test_hay_escenarios_piloto():
    assert {"net-nginx-bad-gateway", "chaos-boss-cascade"} <= set(CON_ESQUEMA)


@pytest.mark.parametrize("sid", CON_ESQUEMA)
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_esquema_coherente(sid, seed):
    inst = instantiate_scenario(sid, seed)
    topo = inst["topology"]
    roles = {n["role"] for n in inst["nodes"]}
    assert set(topo["nodes"]) == roles
    if topo["entry"] is None:
        assert "entry" not in topo["checks"].values(), "sin entrada no puede haber sonda en la entrada"
    else:
        assert topo["entry"]["to"] in roles
    for l in topo["links"]:
        assert l["from"] in roles and l["to"] in roles
    check_ids = {c["id"] for c in inst["checks"]}
    assert set(topo["checks"]) == check_ids, "cada sonda debe colocarse en el esquema"
    for target in topo["checks"].values():
        kind, _, ref = target.partition(":")
        if kind == "node":
            assert ref in roles
        elif kind == "link":
            assert int(ref) < len(topo["links"])
        else:
            assert target == "entry"


@pytest.mark.parametrize("sid", CON_ESQUEMA)
def test_guardia_oculta_detalles(sid):
    pub = _public_topology(instantiate_scenario(sid, 1)["topology"], blind=True)
    assert all(v == {} for v in pub["nodes"].values())
    assert all("via" not in l for l in pub["links"])
    assert "via" not in (pub["entry"] or {})
    assert pub["checks"] == {}


# ---- Redes (varias cajas + router) ----
import json
from pathlib import Path

from chaos_lab.engine import ChaosEngine, _networks_map

MULTIRED = json.loads((Path(__file__).parent / "fixtures" / "topologia_multired.json").read_text(encoding="utf-8"))


def test_networks_map_con_router():
    assert _networks_map(MULTIRED) == {"lan": ["pc1", "pc2", "router"], "dmz": ["router", "web", "db"]}


def test_networks_map_sin_declarar_es_vacio():
    assert _networks_map({"nodes": [{"role": "a"}, {"role": "b"}]}) == {}


def test_networks_map_nodo_sin_redes_va_a_la_primera():
    inst = {"networks": ["x", "y"], "nodes": [{"role": "a"}, {"role": "b", "networks": ["y"]}]}
    assert _networks_map(inst) == {"x": ["a"], "y": ["b"]}


def test_topologia_publica_expone_redes_tambien_a_ciegas():
    nets = _networks_map(MULTIRED)
    claro = _public_topology(MULTIRED["topology"], blind=False, networks=nets)
    ciego = _public_topology(MULTIRED["topology"], blind=True, networks=nets)
    assert claro["networks"] == ciego["networks"] == nets
    assert ciego["checks"] == {} and all(v == {} for v in ciego["nodes"].values())
    # sin redes declaradas no aparece la clave y no se muta el original
    assert "networks" not in _public_topology(MULTIRED["topology"], blind=False)
    assert "networks" not in MULTIRED["topology"]


def test_catalogo_incluye_entry_y_networks():
    for s in ChaosEngine().get_catalog_view()["scenarios"]:
        assert isinstance(s["networks"], dict) and "entry" in s
