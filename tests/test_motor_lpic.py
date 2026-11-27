"""Pruebas del motor ampliado (pack LPIC): redes múltiples, tipo, workdir y check_script. Sin contenedores."""
import json
import sys
import types
from pathlib import Path

import pytest

try:
    import fastapi  # noqa: F401
except ImportError:  # entorno sin FastAPI: basta un sustituto, solo probamos build_exec_cmd
    _fake = types.ModuleType("fastapi")
    _fake.WebSocket = _fake.WebSocketDisconnect = object
    sys.modules["fastapi"] = _fake

from chaos_lab import engine, pty_bridge
from chaos_lab.engine import ChaosEngine


REPO = Path(__file__).resolve().parent.parent


class FakeRun:
    """Sustituto de _run_cmd: registra las llamadas y responde según un guion."""

    def __init__(self, responder=None):
        self.calls = []
        self.responder = responder or (lambda args, inp: (0, ""))

    def __call__(self, args, timeout=30, input_text=None):
        self.calls.append({"args": list(args), "input": input_text, "timeout": timeout})
        return self.responder(args, input_text)


def _inst(nodes, networks=None):
    d = {"nodes": nodes}
    if networks is not None:
        d["networks"] = networks
    return d


# ---------- check_script ----------

def test_parse_marcas_en_orden():
    out = "ruido\n✔ Uno\n✘ Dos\n  ✔ Tres  \notro"
    cs = engine._parse_check_output(out, "srv")
    assert [c["id"] for c in cs] == ["c1", "c2", "c3"]
    assert [c["label"] for c in cs] == ["Uno", "Dos", "Tres"]
    assert [c["passed"] for c in cs] == [True, False, True]
    assert {c["node"] for c in cs} == {"srv"}


@pytest.mark.parametrize("out", ["", "sin marcas\nnada", "Timeout (60s) ejecutando: x"])
def test_parse_vacio_es_una_sonda_fallida(out):
    cs = engine._parse_check_output(out, "srv")
    assert len(cs) == 1 and cs[0]["passed"] is False
    assert cs[0]["label"] == "El corrector no devolvió resultados"


def test_script_incluye_preambulo_y_cwd():
    txt = engine._build_check_script({"node": "a", "script": "comprueba 'x' true", "cwd": "/srv/mi dir"})
    assert txt.startswith("ok()  {")
    assert "comprueba() {" in txt
    assert "cd '/srv/mi dir'" in txt and "Falta el directorio de trabajo" in txt
    assert txt.index("cd '/srv") < txt.index("comprueba 'x' true")
    assert "cd " not in engine._build_check_script({"node": "a", "script": "ok y"})


def _motor_con_script(monkeypatch, salidas):
    """Motor con un escenario activo con check_script; `salidas` = lista de salidas sucesivas del script."""
    fake = FakeRun(lambda a, i: (0, salidas.pop(0)))
    monkeypatch.setattr(engine, "_run_cmd", fake)
    eng = ChaosEngine()
    inst = {
        "id": "x", "title": "t", "category": "c", "difficulty": "Básico", "points": 10, "estimated_min": 5,
        "tags": [], "blind_alert": "", "briefing": "", "seed": 1, "hints": [], "solution_summary": "",
        "check_script": {"node": "srv", "script": "comprueba a true"},
    }
    nodes = [{"role": "srv", "container": "chaoslab-srv", "distro": "debian", "image": "i", "shell": "/bin/sh",
              "default_user": "root", "ip": "1.1.1.1", "ips": {}}]
    inst["checks"] = eng._run_check_script(inst["check_script"], nodes)
    eng.active = {
        "id": "x", "session_id": "s", "instance": inst, "nodes_runtime": nodes, "blind_mode": False,
        "record": False, "started_at": 0, "solved": False, "solved_elapsed_s": 0, "hints_used": 0,
        "last_check_map": {c["id"]: False for c in inst["checks"]}, "transcript": [], "timeline": [],
    }
    return eng, fake


def test_script_por_stdin_con_bash_s(monkeypatch):
    eng, fake = _motor_con_script(monkeypatch, ["✘ A\n✘ B"])
    call = fake.calls[0]
    assert call["args"][-2:] == ["bash", "-s"] and "-i" in call["args"]
    assert call["timeout"] == 60 and "comprueba a true" in call["input"]
    # al lanzar todo en rojo aunque el script ya diga ✔
    assert [c["label"] for c in eng.active["instance"]["checks"]] == ["A", "B"]
    assert eng.active["last_check_map"] == {"c1": False, "c2": False}


def test_verify_sustituye_checks_y_resuelve(monkeypatch):
    eng, _ = _motor_con_script(monkeypatch, ["✘ A\n✘ B", "✔ A\n✘ B\n✘ C", "✔ A\n✔ B"])
    r = eng.verify()
    assert r["total_checks"] == 3 and r["passed_count"] == 1 and not r["all_passed"]
    assert [c["id"] for c in r["active"]["checks"]] == ["c1", "c2", "c3"]
    r = eng.verify()  # cambia el número de líneas: manda lo último
    assert r["total_checks"] == 2 and r["all_passed"] and r["active"]["solved"]


def test_verify_vacio_nunca_resuelve(monkeypatch):
    eng, _ = _motor_con_script(monkeypatch, ["✘ A", ""])
    r = eng.verify()
    assert not r["all_passed"] and r["total_checks"] == 1 and not r["active"]["solved"]


def test_modo_guardia_oculta_etiquetas_del_script(monkeypatch):
    eng, _ = _motor_con_script(monkeypatch, ["✘ Secreto"])
    eng.active["blind_mode"] = True
    assert "Secreto" not in json.dumps(eng.public_active_view()["checks"])


# ---------- redes ----------

def test_sin_networks_comportamiento_clasico():
    n1, n2 = {"role": "a"}, {"role": "b"}
    assert engine._plan_networks(_inst([n1])) == ([], {"a": []})
    nets, per = engine._plan_networks(_inst([n1, n2]))
    assert nets == ["chaoslab-net"] and per == {"a": ["chaoslab-net"], "b": ["chaoslab-net"]}


def test_plan_con_varias_redes_y_sin_limite_de_nodos():
    nodes = [{"role": "gw", "networks": ["lan", "dmz"]}] + [{"role": f"h{i}", "networks": ["lan"]} for i in range(5)]
    nodes.append({"role": "web"})  # sin networks: primera del escenario
    nets, per = engine._plan_networks(_inst(nodes, ["lan", "dmz"]))
    assert nets == ["chaoslab-lan", "chaoslab-dmz"]
    assert per["gw"] == ["chaoslab-lan", "chaoslab-dmz"] and per["web"] == ["chaoslab-lan"]
    assert len(per) == 7


def test_run_arranca_en_la_primera_y_connect_el_resto():
    n = {"role": "gw", "caps": ["NET_ADMIN"]}
    nets = ["chaoslab-lan", "chaoslab-dmz"]
    cmd = engine._build_run_cmd(n, "chaoslab-gw", "img", nets)
    i = cmd.index("--network")
    assert cmd[i:i + 4] == ["--network", "chaoslab-lan", "--network-alias", "gw"]
    assert "chaoslab-dmz" not in cmd and "NET_ADMIN" in cmd
    assert engine._connect_cmds("gw", "chaoslab-gw", nets) == [
        [engine.RUNTIME, "network", "connect", "--alias", "gw", "chaoslab-dmz", "chaoslab-gw"]]
    assert engine._connect_cmds("gw", "chaoslab-gw", nets[:1]) == []
    assert "--network" not in engine._build_run_cmd({"role": "s"}, "c", "img", [])


def test_cleanup_borra_todas_las_redes(monkeypatch):
    def resp(args, inp):
        if args[1:3] == ["network", "ls"]:
            return 0, "bridge\nchaoslab-lan\nchaoslab-dmz\notra\nchaoslab-net"
        return 0, ""
    fake = FakeRun(resp)
    monkeypatch.setattr(engine, "_run_cmd", fake)
    ChaosEngine().cleanup_containers()
    borradas = [c["args"][-1] for c in fake.calls if c["args"][1:3] == ["network", "rm"]]
    assert sorted(borradas) == ["chaoslab-dmz", "chaoslab-lan", "chaoslab-net"]


def test_ips_por_red_docker_y_podman():
    nets = ["chaoslab-lan", "chaoslab-dmz"]
    docker = json.dumps({"chaoslab-lan": {"IPAddress": "10.1.0.2"}, "chaoslab-dmz": {"IPAddress": "10.2.0.3"}})
    assert engine._parse_net_ips(docker, nets) == {"chaoslab-lan": "10.1.0.2", "chaoslab-dmz": "10.2.0.3"}
    # Podman puede dar una IP vacía en alguna clave y otras claves (p. ej. ids)
    podman = json.dumps({"abc123": {"IPAddress": "10.1.0.9"}, "chaoslab-dmz": {"IPAddress": "10.2.0.4"}})
    got = engine._parse_net_ips(podman, nets)
    assert got["chaoslab-dmz"] == "10.2.0.4" and got["chaoslab-lan"] == "10.1.0.9"
    assert engine._parse_net_ips("basura", nets) == {}
    assert engine._short_net("chaoslab-dmz") == "dmz" and engine._env_name("mi-red") == "MI_RED"


# ---------- tipo y workdir ----------

def test_tipo_por_defecto_averia():
    from chaos_lab.scenarios import SCENARIO_CATALOG, instantiate_scenario
    view = ChaosEngine().get_catalog_view()
    from chaos_lab.scenarios import SCENARIOS_BY_ID
    # sin `tipo` en el catálogo = avería; los que lo declaran (packs) lo respetan
    assert all(s["tipo"] == SCENARIOS_BY_ID[s["id"]].get("tipo", "averia") for s in view["scenarios"])
    assert any(s["tipo"] == "averia" for s in view["scenarios"])
    assert instantiate_scenario(SCENARIO_CATALOG[0]["id"], 1)["tipo"] == "averia"


def test_vista_activa_expone_tipo_ips_y_workdir(monkeypatch):
    eng, _ = _motor_con_script(monkeypatch, ["✘ A"])
    eng.active["instance"]["tipo"] = "tarea"
    eng.active["nodes_runtime"][0].update(workdir="/srv/app", ips={"lan": "1.1.1.1"})
    v = eng.public_active_view()
    assert v["tipo"] == "tarea" and v["nodes"][0]["ips"] == {"lan": "1.1.1.1"}
    assert "-w /srv/app" in v["nodes"][0]["cli_attach"]


def test_workdir_en_el_exec_del_pty():
    base = {"container": "c", "default_user": "root"}
    con = pty_bridge.build_exec_cmd({**base, "workdir": "/srv/app"}, "PS1", ["sh", "-i"])
    assert con[con.index("-w") + 1] == "/srv/app" and con.index("-w") < con.index("c")
    assert "-w" not in pty_bridge.build_exec_cmd(base, "PS1", ["sh", "-i"])


# ---------- pack LPIC-1 102-500 ----------

def test_pack_lpic1_carga_27_escenarios():
    from chaos_lab.scenarios import SCENARIO_CATALOG, instantiate_scenario
    pack = [s for s in SCENARIO_CATALOG if s["category"] == "LPIC-1 · 102-500"]
    assert len(pack) == 27 and all(s["id"].startswith("lpic1-") for s in pack)
    assert len({s["id"] for s in SCENARIO_CATALOG}) == len(SCENARIO_CATALOG), "ids únicos en todo el catálogo"
    for s in pack:
        assert s["tipo"] in ("averia", "tarea") and s["category"] == "LPIC-1 · 102-500" and s["certs"] == ["LPIC-1"]
        assert s["difficulty"] in ("Básico", "Intermedio", "Avanzado")
        inst = instantiate_scenario(s["id"], 1)
        assert len(inst["hints"]) == 3 and all(inst["hints"])
        n = inst["nodes"][0]
        reto = "r102-" + s["id"][len("lpic1-"):]
        assert n["workdir"] == f"/home/alumno/retos/{reto}" and n["distro"] == "lpic-debian" and n["default_user"] == "alumno"
        assert inst["check_script"]["cwd"] == n["workdir"] and "comprueba" in inst["check_script"]["script"]
        assert "apt-get" not in n["setup_sh"]


# ---------- pack Linux Essentials 010-160 ----------

def test_pack_essentials_010_carga_14_escenarios():
    from chaos_lab.scenarios import SCENARIO_CATALOG, instantiate_scenario
    pack = [s for s in SCENARIO_CATALOG if s["id"].startswith("lpie-")]
    assert len(pack) == 14
    assert len({s["id"] for s in SCENARIO_CATALOG}) == len(SCENARIO_CATALOG), "ids únicos en todo el catálogo"
    for s in pack:
        assert s["tipo"] in ("averia", "tarea") and s["category"] == "Linux Essentials · 010-160" and s["certs"] == ["Linux Essentials"]
        assert s["difficulty"] in ("Básico", "Intermedio", "Avanzado")
        inst = instantiate_scenario(s["id"], 1)
        assert len(inst["hints"]) == 3 and all(inst["hints"])
        n = inst["nodes"][0]
        reto = "r010-" + s["id"][len("lpie-"):]
        assert n["workdir"] == f"/home/alumno/retos/{reto}" and n["distro"] == "lpic-debian" and n["default_user"] == "alumno"
        assert inst["check_script"]["cwd"] == n["workdir"] and "comprueba" in inst["check_script"]["script"]
        assert "apt-get" not in n["setup_sh"]


# ---------- pack LPIC-1 101-500 ----------

def test_pack_lpic1_101_carga_18_escenarios():
    from chaos_lab.scenarios import SCENARIO_CATALOG, instantiate_scenario
    pack = [s for s in SCENARIO_CATALOG if s["category"] == "LPIC-1 · 101-500"]
    assert len(pack) == 18 and all(s["id"].startswith("lpic1-") for s in pack)
    assert len({s["id"] for s in SCENARIO_CATALOG}) == len(SCENARIO_CATALOG), "ids únicos en todo el catálogo"
    distros = set()
    for s in pack:
        assert s["tipo"] in ("averia", "tarea") and s["certs"] == ["LPIC-1"]
        assert s["difficulty"] in ("Básico", "Intermedio", "Avanzado")
        inst = instantiate_scenario(s["id"], 1)
        assert len(inst["hints"]) == 3 and all(inst["hints"])
        n = inst["nodes"][0]
        reto = n["workdir"].rsplit("/", 1)[1]
        assert reto.startswith("r101-") and n["workdir"] == f"/home/alumno/retos/{reto}" and n["default_user"] == "alumno"
        assert n["distro"] in engine.IMAGE_CANDIDATES
        distros.add(n["distro"])
        assert inst["check_script"]["cwd"] == n["workdir"] and "comprueba" in inst["check_script"]["script"]
        assert "apt-get install" not in n["setup_sh"] and "dnf install" not in n["setup_sh"]
        assert f"/home/alumno/retos/{reto}" in inst["briefing"]
        assert (REPO / "tests/e2e/soluciones" / f"{s['id']}.sh").exists()
    assert distros == {"lpic-debian", "lpic-fedora"}


def test_pack_lpic1_101_rpm_en_fedora_y_resto_en_debian():
    from chaos_lab.scenarios import instantiate_scenario
    assert instantiate_scenario("lpic1-rpm", 1)["nodes"][0]["distro"] == "lpic-fedora"
    assert "Fedora" in instantiate_scenario("lpic1-rpm", 1)["topology"]["nodes"]["lpic"]["runs"]
    assert instantiate_scenario("lpic1-dpkg", 1)["nodes"][0]["distro"] == "lpic-debian"
    assert engine.IMAGE_CANDIDATES["lpic-fedora"][0] == "localhost/chaos-lpic-fedora:1"


# ---------- corrector multinodo y pack LPIC-2 LDAP ----------

def test_check_blocks_dict_y_lista():
    assert engine._check_blocks({"node": "a", "script": "x"}) == [{"node": "a", "script": "x"}]
    bl = [{"node": "a", "script": "x"}, {"node": "b", "script": "y"}]
    assert engine._check_blocks(bl) == bl


def test_parse_con_inicio_numera_a_continuacion():
    cs = engine._parse_check_output("✔ A\n✘ B", "b", start=3)
    assert [c["id"] for c in cs] == ["c4", "c5"]
    assert engine._parse_check_output("", "b", start=3)[0]["id"] == "c4"


def test_corrector_multinodo_une_sondas_en_orden_con_ids_unicos(monkeypatch):
    salidas = {"chaoslab-a": ["✔ A1\n✘ A2", "✘ A3"], "chaoslab-b": ["✔ B1"]}
    orden = []

    def resp(args, inp):
        c = args[args.index("bash") - 1]
        orden.append((c, inp))
        return 0, salidas[c].pop(0)

    monkeypatch.setattr(engine, "_run_cmd", FakeRun(resp))
    nodes = [{"role": r, "container": f"chaoslab-{r}"} for r in ("a", "b")]
    cs = [
        {"node": "a", "script": "comprueba 1 true", "cwd": "/x"},
        {"node": "b", "script": "comprueba 2 true"},
        {"node": "a", "script": "comprueba 3 true"},
    ]
    out = ChaosEngine()._run_check_script(cs, nodes)
    assert [c["id"] for c in out] == ["c1", "c2", "c3", "c4"]
    assert [(c["node"], c["label"], c["passed"]) for c in out] == [
        ("a", "A1", True), ("a", "A2", False), ("b", "B1", True), ("a", "A3", False)]
    assert [o[0] for o in orden] == ["chaoslab-a", "chaoslab-b", "chaoslab-a"]
    assert "cd /x " in orden[0][1] and "comprueba 2 true" in orden[1][1]


def test_corrector_multinodo_bloque_vacio_o_nodo_inexistente_falla(monkeypatch):
    monkeypatch.setattr(engine, "_run_cmd", FakeRun(lambda a, i: (0, "")))
    nodes = [{"role": "a", "container": "chaoslab-a"}]
    out = ChaosEngine()._run_check_script(
        [{"node": "a", "script": "comprueba x true"}, {"node": "zz", "script": "y"}], nodes)
    assert [c["id"] for c in out] == ["c1", "c2"] and not any(c["passed"] for c in out)
    assert out[1]["node"] == "zz" and "(zz)" in out[1]["label"]


def test_corrector_multinodo_bloque_auxiliar_sin_sondas_no_cuenta(monkeypatch):
    salidas = {"chaoslab-a": ["", "✔ A1"], "chaoslab-b": ["✔ B1"]}
    monkeypatch.setattr(engine, "_run_cmd", FakeRun(lambda a, i: (0, salidas[a[a.index("bash") - 1]].pop(0))))
    nodes = [{"role": r, "container": f"chaoslab-{r}"} for r in ("a", "b")]
    out = ChaosEngine()._run_check_script([
        {"node": "a", "script": "sss_cache -E >/dev/null 2>&1; true"},
        {"node": "b", "script": "comprueba B true"},
        {"node": "a", "script": "comprueba A true"},
    ], nodes)
    assert [(c["id"], c["label"], c["passed"]) for c in out] == [("c1", "B1", True), ("c2", "A1", True)]
    # Si ningún bloque da sondas, sigue saliendo una fallida (nunca resuelto por vacío)
    monkeypatch.setattr(engine, "_run_cmd", FakeRun(lambda a, i: (0, "")))
    out = ChaosEngine()._run_check_script([{"node": "a", "script": "true"}, {"node": "b", "script": "true"}], nodes)
    assert len(out) == 1 and not out[0]["passed"]


def test_corrector_una_orden_que_lee_stdin_no_se_come_el_resto():
    """El corrector llega por stdin a `bash -s`: una orden que lee stdin (ssh, cat…) no debe tragarse las sondas siguientes."""
    import subprocess
    script = engine._build_check_script({"script": 'comprueba "uno" bash -c "cat >/dev/null"\ncomprueba "dos" true'})
    out = subprocess.run(["bash", "-s"], input=script, capture_output=True, text=True, timeout=10).stdout
    assert [c["label"] for c in engine._parse_check_output(out, "a")] == ["uno", "dos"]
