"""Las traducciones de packs/en/<pack>.json encajan con su pack en español.

- mismos escenarios, mismo número de pistas, de enlaces y de «dónde mirar» por nodo;
- `checks` es un mapa {etiqueta en español: inglés} con TODAS las etiquetas fijas del corrector;
- lo que va entre `backticks` (órdenes, ficheros, valores) no se traduce: mismo conjunto en los dos idiomas;
- cada escenario de un pack tiene su traducción (COMPLETO).
"""

import json
import re
from pathlib import Path

import pytest

PACKS = Path(__file__).resolve().parent.parent / "chaos_lab" / "packs"
PACK_NAMES = sorted(p.stem for p in PACKS.glob("*.json"))
LABEL_RE = re.compile(r"""comprueba\s+(?:"((?:[^"\\]|\\.)*)"|'([^']*)')""")
CODE_RE = re.compile(r"`([^`\n]+)`")
TEXT_FIELDS = ("title", "briefing", "blind_alert", "solution_summary")

# Plantillas de sintaxis cuyos marcadores SÍ se traducen (revisadas a mano una a una). Todo lo demás entre
# backticks (órdenes, rutas, ficheros, valores reales) tiene que quedar idéntico.
PLANTILLAS_OK = {
    "tar xf archivo miembro": "tar xf archive member",
    "wc -w < fichero": "wc -w < file",
    "0 4 * * 0 /ruta/limpia.sh": "0 4 * * 0 /path/limpia.sh",
    "--encrypt -r correo": "--encrypt -r email",
    "--quick-generate-key 'NOMBRE <correo>' default default never": "--quick-generate-key 'NAME <email>' default default never",
    "alias nombre='cmd1; cmd2'": "alias name='cmd1; cmd2'",
    "nombre() { ...; }": "name() { ...; }",
    "usuario ALL=(destino) NOPASSWD: comando": "user ALL=(target) NOPASSWD: command",
    "dominio tipo recurso valor": "domain type item value",
    "Xvfb :7 -auth FICHERO -screen 0 AxBxP &": "Xvfb :7 -auth FILE -screen 0 AxBxP &",
    "xauth -f FICHERO add :7 . CLAVE": "xauth -f FILE add :7 . KEY",
    "ipcalc DIRECCIÓN/PREFIJO": "ipcalc ADDRESS/PREFIX",
    "echo 'comando' | at now + 2 hours": "echo 'command' | at now + 2 hours",
    "echo 'echo recordatorio > RUTA/recordatorio.txt' | at now + 2 hours": "echo 'echo recordatorio > PATH/recordatorio.txt' | at now + 2 hours",
    "usuario ALL=(destino) NOPASSWD: /ruta/cmd args, /ruta/otro": "user ALL=(target) NOPASSWD: /path/cmd args, /path/other",
    "visudo -cf FICHERO": "visudo -cf FILE",
    "AAAA-MM-DD": "YYYY-MM-DD",
}


# Etiquetas que el corrector calcula al ejecutar (bucles, $VAR, $(…)) con su texto real en el contenedor:
# también se traducen y se aceptan como claves de checks.
ETIQUETAS_DE_EJECUCION = {
    "lpic1-claves-ssh": ["hay un par ed25519 en /root/.ssh/lab_ed25519, sin frase de paso, con el comentario root@lpi-lab"],
    "lpic1-logrotate": ["rotación semanal", "compresión", "compresión aplazada un ciclo",
                        "no falla si falta el fichero", "no rota ficheros vacíos"],
}


def _pack(name):
    return {x["id"]: x for x in json.loads((PACKS / f"{name}.json").read_text(encoding="utf-8"))}


def _en(name):
    f = PACKS / "en" / f"{name}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def _scripts(sc):
    c = sc.get("comprobar")
    if isinstance(c, str):
        return [c]
    return [b["script"] for b in c or []]


def static_labels(sc):
    """Etiquetas fijas del corrector (las que llevan $ se calculan al ejecutar y no se pueden mapear)."""
    out = []
    for s in _scripts(sc):
        for m in LABEL_RE.finditer(s):
            if m.group(1) is not None:  # entre comillas dobles: $ se expande al ejecutar
                lab = m.group(1).replace('\\"', '"').replace("\\\\", "\\").strip()
                if "$" in lab:
                    continue
            else:  # entre comillas simples: literal, $ incluido
                lab = m.group(2).strip()
            if lab not in out:
                out.append(lab)
    return out


def _nodes(sc):
    return {n["role"]: n for n in sc.get("nodos") or []}


CASES = [(name, sid) for name in PACK_NAMES for sid in _en(name)]


@pytest.mark.parametrize("name,sid", CASES)
def test_traduccion_encaja_con_el_original(name, sid):
    es = _pack(name)
    assert sid in es, f"{name}: la traducción {sid} no existe en el pack"
    sc, en = es[sid], _en(name)[sid]

    for f in TEXT_FIELDS:
        assert isinstance(en.get(f), str) and en[f].strip(), f"{sid}: falta {f}"
    assert len(en.get("hints") or []) == len(sc["hints"]), f"{sid}: número de pistas distinto"

    labels = static_labels(sc) + ETIQUETAS_DE_EJECUCION.get(sid, [])
    cm = en.get("checks") or {}
    assert isinstance(cm, dict), f"{sid}: checks debe ser {{etiqueta en español: inglés}}"
    faltan = [l for l in labels if not (isinstance(cm.get(l), str) and cm[l].strip())]
    sobran = [k for k in cm if k not in labels]
    assert not faltan, f"{sid}: sondas sin traducir: {faltan}"
    assert not sobran, f"{sid}: claves de checks que no son etiquetas del corrector: {sobran}"

    roles = _nodes(sc)
    for role, n in (en.get("nodes") or {}).items():
        assert role in roles, f"{sid}: nodo {role} no existe"
        assert len(n.get("look") or []) == len(roles[role].get("look") or []), f"{sid}: look de {role}"
    for role, n in roles.items():
        if n.get("runs"):
            assert ((en.get("nodes") or {}).get(role) or {}).get("runs"), f"{sid}: falta runs de {role}"
    assert len(en.get("links") or []) == len(sc.get("enlaces") or []), f"{sid}: número de enlaces"


@pytest.mark.parametrize("name,sid", CASES)
def test_lo_que_va_entre_backticks_no_se_traduce(name, sid):
    sc, en = _pack(name)[sid], _en(name)[sid]
    pares = [(f, sc[f], en[f]) for f in TEXT_FIELDS] + [
        (f"hint{i + 1}", h, (en.get("hints") or [""] * 3)[i]) for i, h in enumerate(sc["hints"])
    ]
    for campo, es_txt, en_txt in pares:
        a = {PLANTILLAS_OK.get(x, x) for x in CODE_RE.findall(es_txt)}
        b = set(CODE_RE.findall(en_txt or ""))
        assert a == b, f"{sid}.{campo}: cambia lo que va entre backticks: solo ES {sorted(a - b)} · solo EN {sorted(b - a)}"


def test_todos_los_escenarios_de_los_packs_tienen_ingles():
    sin = [f"{name}:{sid}" for name in PACK_NAMES for sid in _pack(name) if sid not in _en(name)]
    assert not sin, f"escenarios sin traducción en packs/en/: {sin}"
