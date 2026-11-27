"""Pruebas de estructura de los escenarios SecOps y de la correlación del Modo Guardia (sin Podman)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from chaos_lab import mentor
from chaos_lab.scenarios import SCENARIOS_BY_ID, instantiate_scenario

SECOPS = ["sec-ssh-bruteforce", "sec-portscan-detect", "sec-dns-exfil"]


@pytest.mark.parametrize("sid", SECOPS)
@pytest.mark.parametrize("seed", [1, 7, 42, 1234, 99999])
def test_estructura(sid, seed):
    inst = instantiate_scenario(sid, seed)
    assert sid in SCENARIOS_BY_ID and inst["category"].startswith("Seguridad")
    roles = [n["role"] for n in inst["nodes"]]
    assert len(roles) == 3 and len(set(roles)) == 3
    for n in inst["nodes"]:
        assert n["setup_sh"].strip() and "%%" not in n["setup_sh"]
    ids = [c["id"] for c in inst["checks"]]
    assert len(ids) == len(set(ids)) >= 4
    for c in inst["checks"]:
        assert c["node"] in roles and c["cmd"].strip() and "%%" not in c["cmd"]
    assert len(inst["hints"]) == 3 and inst["solution_summary"]
    for s in inst["signals"]:
        assert s["node"] in roles and s["cmd"].strip() and "{0}" not in s["text"]


@pytest.mark.parametrize("sid", SECOPS)
def test_mutator_varia(sid):
    cmds = {instantiate_scenario(sid, s)["nodes"][0]["setup_sh"] for s in range(1, 12)}
    assert len(cmds) > 1


def test_timeline_en_postmortem(monkeypatch):
    class P:
        returncode = 0
        stdout = "1795732800|40|10.0.0.x\n"

    monkeypatch.setattr(mentor.subprocess, "run", lambda *a, **k: P())
    inst = instantiate_scenario("sec-ssh-bruteforce", 3)
    active = {
        "instance": inst,
        "nodes_runtime": [{"role": n["role"], "container": "x", "shell": "/bin/bash", "image": "i", "ip": "1.1.1.1"} for n in inst["nodes"]],
        "blind_mode": True,
        "solved": False,
        "solved_elapsed_s": 0,
        "started_at": 0,
        "hints_used": 0,
        "last_check_map": {},
        "transcript": [],
    }
    active["timeline"] = mentor.collect_timeline(active)
    assert active["timeline"] and active["timeline"][-1]["node"] == "pagerduty"
    md = mentor.build_postmortem_markdown(active)
    assert "Línea de Tiempo de Señales Correlacionadas" in md and "10.0.0.x" in md
