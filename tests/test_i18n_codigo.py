"""El inglés de los escenarios definidos en código (scenarios.py / scenarios_secops.py) está completo y alineado."""
import inspect
import re
import string

import pytest

from chaos_lab import engine
from chaos_lab.engine import _catalog_i18n
from chaos_lab.i18n_codigo import EN
from chaos_lab.scenarios import SCENARIO_CATALOG, instantiate_scenario

IDS = sorted(EN)
SEEDS = [1, 2, 3, 42, 777]
SECRET_VARS = ("real_port", "wrong_port", "rogue_name", "rpass", "c2_domain", "hidden_dir", "decoys", "token", "val_tok")


def _spans(t):
    # única excepción: «`crontab de root`» es una frase en prosa, no un comando
    return sorted(x.replace("crontab de root", "root's crontab") for x in re.findall(r"`([^`]+)`", t))


def _idx(t):
    return {int(f) for _, f, _, _ in string.Formatter().parse(t) if f}


def test_todos_los_escenarios_en_codigo_tienen_ingles():
    codigo = [s["id"] for s in SCENARIO_CATALOG if s["builder"].__module__ in ("chaos_lab.scenarios", "chaos_lab.scenarios_secops")]
    assert sorted(codigo) == IDS


@pytest.mark.parametrize("sid", IDS)
@pytest.mark.parametrize("seed", SEEDS)
def test_ingles_completo_y_alineado(sid, seed):
    inst = instantiate_scenario(sid, seed)
    en = inst["i18n"]["en"]
    for k in ("title", "briefing", "blind_alert", "solution_summary"):
        assert en.get(k, "").strip(), f"{sid}: falta {k}"
    assert len(en["hints"]) == len(inst["hints"]) and all(h.strip() for h in en["hints"])
    assert all(c.get("label_en", "").strip() for c in inst["checks"]), f"{sid}: sonda sin label_en"
    topo = inst["topology"]
    assert set(en["nodes"]) == set(topo["nodes"])
    for role, nd in en["nodes"].items():
        assert nd["runs"].strip()
        assert len(nd["look"]) == len(topo["nodes"][role]["look"])
    assert len(en["links"]) == len(topo["links"]) and all(x.strip() for x in en["links"])
    if topo.get("entry"):
        assert en["entry"]["label"].strip() and en["entry"]["via"].strip()
    # los trozos entre backticks son los mismos que en español
    assert _spans(en["solution_summary"]) == _spans(inst["solution_summary"]), sid
    for i, h in enumerate(inst["hints"]):
        assert _spans(en["hints"][i]) == _spans(h), f"{sid} pista {i + 1}"
    assert _spans(en["briefing"]) == _spans(inst["briefing"])
    assert _spans(en["blind_alert"]) == _spans(inst["blind_alert"])


@pytest.mark.parametrize("sid", IDS)
def test_senales_secops(sid):
    inst = instantiate_scenario(sid, 1)
    sig = inst.get("signals")
    if not sig:
        pytest.skip("no es SecOps")
    en = inst["i18n"]["en"]["signals"]
    assert len(en) == len(sig)
    for es, e in zip(sig, en):
        assert _idx(es["text"]) == _idx(e)
        e.format(*["x"] * (max(_idx(es["text"]) | {0}) + 1))


@pytest.mark.parametrize("sid", IDS)
def test_sin_spoilers_en_ingles(sid):
    """Los valores secretos solo salen en la pista 3 / solución, igual que en español."""
    inst = instantiate_scenario(sid, 5)
    en = inst["i18n"]["en"]
    secretos = []
    for k in SECRET_VARS:
        v = inst["vars"].get(k)
        if v is not None:
            secretos += [str(x) for x in v] if isinstance(v, (list, tuple)) else [str(v)]
    secretos = [s for s in secretos if len(s) >= 3]
    visibles = [en["title"], en["briefing"], en["blind_alert"]] + [c["label_en"] for c in inst["checks"]]
    visibles += [n["runs"] for n in en["nodes"].values()] + [x for n in en["nodes"].values() for x in n["look"]] + en["links"]
    if en.get("entry"):
        visibles += list(en["entry"].values())
    assert not [(s, t) for t in visibles for s in secretos if s in t]
    es_12 = " ".join(inst["hints"][:2])
    en_12 = " ".join(en["hints"][:2])
    for s in secretos:
        if s not in es_12:
            assert s not in en_12, f"{sid}: {s} adelantado en inglés"


@pytest.mark.parametrize("sid", IDS)
def test_catalogo_en_ingles_sin_pistas(sid):
    cat = _catalog_i18n(instantiate_scenario(sid, 42))["en"]
    assert set(cat) <= {"title", "briefing", "nodes", "links"}
    assert all(set(n) == {"runs"} for n in cat["nodes"].values())
    assert cat["title"] and cat["briefing"]


def test_la_vista_de_catalogo_usa_la_muestra_para_el_ingles():
    cls = next(c for _, c in inspect.getmembers(engine, inspect.isclass) if hasattr(c, "get_catalog_view"))
    assert "_catalog_i18n(sample)" in inspect.getsource(cls.get_catalog_view)
