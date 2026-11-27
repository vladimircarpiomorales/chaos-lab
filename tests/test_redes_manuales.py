"""Redes «manuales» (sin IPAM, estilo containerlab): comandos del motor, eth{i} deterministas, IPs de diseño."""
import re

import pytest

from chaos_lab import engine
from chaos_lab.engine import (
    _build_run_cmd, _connect_cmds, _design_ips, _manual_networks, _manual_prep_cmd, _network_create_cmd,
    _networks_map, _plan_networks, _public_topology,
)
from chaos_lab.scenarios import SCENARIO_CATALOG, instantiate_scenario

REDES = [s["id"] for s in SCENARIO_CATALOG if s["id"].startswith("red-")]


def test_red_normal_sigue_igual():
    assert _network_create_cmd("chaoslab-x", runtime="podman") == ["podman", "network", "create", "chaoslab-x"]
    assert _network_create_cmd("chaoslab-x", runtime="docker") == ["docker", "network", "create", "chaoslab-x"]


def test_red_manual_podman_sin_ipam():
    assert _network_create_cmd("chaoslab-lan", True, 0, "podman") == [
        "podman", "network", "create", "--internal", "--ipam-driver", "none", "chaoslab-lan"]


def test_red_manual_docker_interna_con_subred_distinta_por_red():
    a = _network_create_cmd("chaoslab-lan", True, 0, "docker")
    b = _network_create_cmd("chaoslab-dmz", True, 1, "docker")
    assert a[:4] == ["docker", "network", "create", "--internal"] and "--ipam-driver" not in a
    assert a[a.index("--subnet") + 1] != b[b.index("--subnet") + 1]


def test_docker_vacia_direcciones_y_rutas_de_cada_interfaz():
    cmd = _manual_prep_cmd("c1", ["chaoslab-a", "chaoslab-b"], "docker")
    assert cmd[:5] == ["docker", "exec", "--user", "root", "c1"]
    for i in (0, 1):
        assert f"ip addr flush dev eth{i}" in cmd[-1] and f"ip route flush dev eth{i}" in cmd[-1]
    assert "eth2" not in cmd[-1]


def test_podman_no_necesita_vaciar_nada():
    assert _manual_prep_cmd("c1", ["chaoslab-a"], "podman") is None


def test_sysctl_rw_abre_proc_sys():
    base = {"role": "r1", "caps": ["NET_ADMIN"]}
    assert "systempaths=unconfined" not in " ".join(_build_run_cmd(base, "c", "img", ["chaoslab-a"]))
    cmd = _build_run_cmd({**base, "sysctl_rw": True}, "c", "img", ["chaoslab-a"])
    assert cmd[cmd.index("--security-opt") + 1] == "systempaths=unconfined"
    assert cmd.index("--security-opt") < cmd.index("img")


def test_la_red_i_del_nodo_es_eth_i():
    """Arranca en su 1ª red (eth0) y las demás se conectan en orden: eth1, eth2…"""
    nets = ["chaoslab-lan", "chaoslab-transito", "chaoslab-dmz"]
    run = _build_run_cmd({"role": "r"}, "c", "img", nets)
    assert run[run.index("--network") + 1] == "chaoslab-lan"
    assert [c[-2] for c in _connect_cmds("r", "c", nets)] == ["chaoslab-transito", "chaoslab-dmz"]


def test_design_ips_solo_de_sus_redes_y_sin_prefijo():
    n = {"design_ips": {"lan": "10.5.1.1/24", "dmz": "10.5.3.1", "otra": "9.9.9.9"}}
    assert _design_ips(n, ["chaoslab-lan", "chaoslab-dmz"]) == {"lan": "10.5.1.1", "dmz": "10.5.3.1"}
    assert _design_ips({}, ["chaoslab-lan"]) == {}


def test_formato_antiguo_no_es_manual():
    assert not _manual_networks({"networks": ["lan"]})
    assert _manual_networks({"network_mode": "manual"})


def test_cleanup_borra_tambien_las_redes_manuales(monkeypatch):
    llamadas = []

    def falso(args, timeout=30, input_text=None):
        llamadas.append(args)
        if args[1:3] == ["network", "ls"]:
            return 0, "podman\nchaoslab-lan\nchaoslab-transito\notra"
        return 0, ""

    monkeypatch.setattr(engine, "_run_cmd", falso)
    engine.ChaosEngine().cleanup_containers()
    borradas = {a[-1] for a in llamadas if a[1:3] == ["network", "rm"]}
    assert {"chaoslab-lan", "chaoslab-transito"} <= borradas and "otra" not in borradas and "podman" not in borradas


def test_hay_escenario_de_redes():
    assert "red-averias-4saltos" in REDES


@pytest.mark.parametrize("sid", REDES)
def test_escenario_de_redes_coherente(sid):
    inst = instantiate_scenario(sid, 1)
    assert _manual_networks(inst)
    declared = inst["networks"]
    for n in inst["nodes"]:
        assert n["distro"] == "redes" and {"NET_ADMIN", "NET_RAW"} <= set(n["caps"])
        assert n["networks"] and set(n["networks"]) <= set(declared)
        # IP de diseño en cada red del nodo, dentro de una subred /24 propia de esa red
        assert set(n["design_ips"]) == set(n["networks"])
    por_red = {}
    for n in inst["nodes"]:
        for red, ip in n["design_ips"].items():
            por_red.setdefault(red, set()).add(ip.rsplit(".", 1)[0])
    assert all(len(v) == 1 for v in por_red.values()), por_red
    _, per_node = _plan_networks(inst)
    assert all(len(v) == len(inst["nodes"][i]["networks"]) for i, v in enumerate(per_node.values()))
    # el esquema enseña las redes y el router aparece en dos
    m = _networks_map(inst)
    assert set(m) == set(declared)
    assert sum(len(v) for v in m.values()) > len(inst["nodes"])
    assert "networks" in _public_topology(inst["topology"], blind=True, networks=m)


@pytest.mark.parametrize("sid", REDES)
def test_setup_usa_la_interfaz_que_toca(sid):
    """Los `ip addr add … dev ethN` del setup deben caer en una interfaz que el nodo tiene (eth0..eth{n-1})."""
    inst = instantiate_scenario(sid, 1)
    for n in inst["nodes"]:
        for dev in re.findall(r"dev (eth\d+)", n["setup_sh"]):
            assert int(dev[3:]) < len(n["networks"]), (n["role"], dev)
        for red, ip in n["design_ips"].items():
            i = n["networks"].index(red)
            assert re.search(rf"ip addr add {re.escape(ip)}/\d+ dev eth{i}\b", n["setup_sh"]), (n["role"], red)
