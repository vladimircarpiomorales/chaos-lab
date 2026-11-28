"""i18n: traducciones inglesas de los escenarios (paso al catálogo y a la vista activa SIN spoilers) y diccionarios de la interfaz."""
import json
import re
import sys
import types
from pathlib import Path

try:
    import fastapi  # noqa: F401
except ImportError:  # entorno sin FastAPI: basta un sustituto
    _fake = types.ModuleType("fastapi")
    _fake.WebSocket = _fake.WebSocketDisconnect = object
    sys.modules["fastapi"] = _fake

from chaos_lab.engine import ChaosEngine, _active_i18n, _catalog_i18n
from chaos_lab.scenarios import SCENARIO_CATALOG, instantiate_scenario

REPO = Path(__file__).resolve().parent.parent
SID = "red-averias-4saltos"
EN = {
    "title": "EN title",
    "briefing": "EN briefing",
    "hints": ["EN hint 1", "EN hint 2", "EN hint 3"],
    "solution_summary": "EN SOLUTION",
    "blind_alert": "EN blind alert",
}


def _motor_activo(hints_used=0, blind=False, solved=False, i18n=None):
    eng = ChaosEngine()
    inst = instantiate_scenario(SID, 1)
    inst["i18n"] = {"en": EN} if i18n is None else i18n
    eng.active = {
        "id": SID, "session_id": "s", "instance": inst, "nodes_runtime": [], "blind_mode": blind,
        "record": False, "started_at": 0, "solved": solved, "solved_elapsed_s": 0, "hints_used": hints_used,
        "last_check_map": {}, "transcript": [], "timeline": [],
    }
    return eng


# ---------- Catálogo ----------

def test_ejemplo_redes_trae_ingles():
    sc = next(s for s in SCENARIO_CATALOG if s["id"] == SID)
    en = sc["i18n"]["en"]
    assert {"title", "briefing", "hints", "solution_summary", "blind_alert"} <= set(en)
    assert len(en["hints"]) == len(instantiate_scenario(SID, 1)["hints"]) == 3
    assert en["title"] != sc["title"]


def test_catalogo_solo_expone_titulo_y_briefing_en_ingles():
    view = ChaosEngine().get_catalog_view()
    s = next(x for x in view["scenarios"] if x["id"] == SID)
    assert set(s["i18n"]["en"]) <= {"title", "briefing", "nodes", "links"}
    assert s["i18n"]["en"]["title"].startswith("The intranet")
    blob = json.dumps(s["i18n"], ensure_ascii=False)
    for secreto in ("hints", "solution_summary", "blind_alert", "nftables rule on `srv`"):
        assert secreto not in blob
    # los escenarios sin traducción no llevan clave vacía engañosa: i18n es {} y el español sigue completo
    sin = [x for x in view["scenarios"] if x["id"] != SID and "i18n" in x and x["i18n"]]
    assert sin == []  # solo el ejemplo está traducido


def test_catalog_i18n_ignora_campos_vacios_o_ajenos():
    assert _catalog_i18n({}) == {}
    assert _catalog_i18n({"i18n": {"en": {"title": " ", "hints": ["x"], "solution_summary": "s"}}}) == {}
    assert _catalog_i18n({"i18n": {"en": {"title": "T", "look": ["x"], "checks": ["c"]}}}) == {"en": {"title": "T"}}


# ---------- Vista activa: mismo filtrado que el español ----------

def test_activa_sin_pistas_ni_solucion_al_empezar():
    v = _motor_activo().public_active_view()
    en = v["i18n"]["en"]
    assert en == {"title": "EN title", "description": "EN briefing"}
    assert v["hints"] == [] and v["solution_summary"] is None


def test_activa_solo_pistas_desbloqueadas():
    for n in (1, 2, 3):
        v = _motor_activo(hints_used=n).public_active_view()
        assert v["i18n"]["en"]["hints"] == EN["hints"][:n]
        assert len(v["i18n"]["en"]["hints"]) == len(v["hints"]) == n
        assert "EN SOLUTION" not in json.dumps(v["i18n"])


def test_activa_solucion_solo_tras_resolver():
    assert "solution_summary" not in _motor_activo(hints_used=3).public_active_view()["i18n"]["en"]
    v = _motor_activo(solved=True).public_active_view()
    assert v["i18n"]["en"]["solution_summary"] == "EN SOLUTION"


def test_activa_modo_guardia_solo_la_alerta():
    v = _motor_activo(blind=True).public_active_view()
    en = v["i18n"]["en"]
    assert en == {"description": "EN blind alert"}
    blob = json.dumps(v, ensure_ascii=False)
    assert "EN title" not in blob and "EN briefing" not in blob and "EN SOLUTION" not in blob
    # con pistas, siguen filtradas por las usadas; ni título ni briefing aunque se pida una pista
    v = _motor_activo(blind=True, hints_used=1).public_active_view()
    assert v["i18n"]["en"]["hints"] == ["EN hint 1"] and "title" not in v["i18n"]["en"]


def test_activa_modo_guardia_resuelto_ya_no_oculta():
    v = _motor_activo(blind=True, solved=True).public_active_view()
    assert v["i18n"]["en"]["title"] == "EN title" and v["i18n"]["en"]["solution_summary"] == "EN SOLUTION"


def test_activa_sin_traduccion_no_trae_clave_en():
    assert _motor_activo(i18n={}).public_active_view()["i18n"] == {}
    assert _active_i18n({}, 3, False, True) == {}


COMPLETO = dict(
    EN,
    checks=["EN probe 1"],
    nodes={"pc1": {"runs": "EN runs", "look": ["EN look"]}},
    links=["EN via"],
    entry={"label": "EN you", "via": "EN entry via"},
    extra="SECRETO",
)


def test_activa_traduce_sondas_nodos_y_enlaces_sin_campos_ajenos():
    en = _motor_activo(i18n={"en": COMPLETO}).public_active_view()["i18n"]["en"]
    assert en["checks"] == ["EN probe 1"]
    assert en["nodes"] == {"pc1": {"runs": "EN runs", "look": ["EN look"]}}
    assert en["links"] == ["EN via"] and en["entry"] == {"label": "EN you", "via": "EN entry via"}
    assert "SECRETO" not in json.dumps(en)


def test_activa_modo_guardia_no_traduce_sondas_ni_esquema():
    v = _motor_activo(blind=True, i18n={"en": COMPLETO}).public_active_view()
    en = v["i18n"]["en"]
    assert set(en) <= {"description", "entry", "hints"}
    assert en.get("entry") == {"label": "EN you"}  # la entrada sin «via», igual que el español a ciegas
    blob = json.dumps(en)
    for x in ("EN probe", "EN runs", "EN look", "EN via", "EN entry via"):
        assert x not in blob


def test_catalogo_traduce_maquinas_y_enlaces_pero_no_look():
    out = _catalog_i18n({"i18n": {"en": COMPLETO}})["en"]
    assert out["nodes"] == {"pc1": {"runs": "EN runs"}} and out["links"] == ["EN via"]
    blob = json.dumps(out)
    assert "EN look" not in blob and "EN probe" not in blob and "SECRETO" not in blob


# ---------- Diccionarios de la interfaz ----------

STATIC = REPO / "static"


def _diccionarios():
    src = (STATIC / "i18n.js").read_text(encoding="utf-8")
    m_es = re.search(r"const es = \{(.*?)\n  \};", src, re.S)
    m_en = re.search(r"const en = \{(.*?)\n  \};", src, re.S)
    assert m_es and m_en, "no se encuentran los diccionarios es/en en i18n.js"
    pair = re.compile(r'^\s*"([^"]+)":\s*"((?:[^"\\]|\\.)*)",?\s*$', re.M)
    return dict(pair.findall(m_es.group(1))), dict(pair.findall(m_en.group(1)))


def test_es_y_en_tienen_las_mismas_claves():
    es, en = _diccionarios()
    assert set(es) == set(en), f"solo en es: {sorted(set(es) - set(en))}; solo en en: {sorted(set(en) - set(es))}"
    assert len(es) > 100


def test_mismas_variables_en_los_dos_idiomas():
    es, en = _diccionarios()
    var = re.compile(r"\{(\w+)\}")
    malas = [k for k in es if set(var.findall(es[k])) != set(var.findall(en[k]))]
    assert not malas, f"variables {{x}} distintas entre es y en: {malas}"


def test_claves_usadas_en_app_js_existen():
    es, en = _diccionarios()
    src = (STATIC / "app.js").read_text(encoding="utf-8")
    usadas = set(re.findall(r'\b(?:t|tOr|setMentorKey)\("([\w.áéíóúÁÉÍÓÚñ]+)"\s*[,)]', src))
    assert len(usadas) > 60
    faltan = sorted(k for k in usadas if k not in es or k not in en)
    assert not faltan, f"claves de app.js que faltan en es/en: {faltan}"


def test_claves_usadas_en_index_html_existen():
    es, en = _diccionarios()
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    usadas = set(re.findall(r'data-i18n(?:-html|-placeholder|-title|-aria-label)?="([^"]+)"', html))
    assert len(usadas) > 60
    faltan = sorted(k for k in usadas if k not in es or k not in en)
    assert not faltan, f"claves de index.html que faltan en es/en: {faltan}"


def test_index_carga_i18n_antes_que_app():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert html.index("/static/i18n.js") < html.index("/static/app.js")


def test_todas_las_dificultades_del_catalogo_tienen_traduccion():
    es, en = _diccionarios()
    for d in {s["difficulty"] for s in SCENARIO_CATALOG}:
        assert f"diff.{d}" in es and f"diff.{d}" in en, d
