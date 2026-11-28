"""
Motor de ejecución de laboratorios efímeros sobre Podman (rootless) o Docker.
Soporta topologías de 1 a N nodos en red aislada, inyección de averías mutables,
verificación granular por objetivos y persistencia de progreso/rachas.
"""

from __future__ import annotations

import datetime
import json
import os
import random
import re
import shlex
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from .mentor import collect_timeline
from .scenarios import SCENARIO_CATALOG, SCENARIOS_BY_ID, instantiate_scenario
from .runtime import RUNTIME

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = BASE_DIR / "data" / "state.json"

CONTAINER_PREFIX = "chaoslab-"
# Herramientas que se buscan en cada nodo al desplegar (orden = orden en la UI)
NODE_TOOLS = ["nano", "vim", "vi", "less", "curl", "wget", "ss", "ip", "dig", "ps", "top",
              "nc", "nft", "iptables", "tcpdump", "openssl", "python3"]
NETWORK_NAME = "chaoslab-net"

IMAGE_CANDIDATES: dict[str, list[str]] = {
    # Primero las imágenes propias (images/construir.sh, las crea arrancar.sh la primera vez);
    # si faltan, las oficiales (funcionan, pero sin nano/vim/ss/dig y los SecOps necesitan red para apt).
    "debian": [
        "localhost/chaos-debian:1",
        "docker.io/library/debian:trixie",
    ],
    "lpic-debian": [
        "localhost/chaos-lpic-debian:1",
        "docker.io/library/debian:trixie",
    ],
    "lpic-fedora": [
        "localhost/chaos-lpic-fedora:1",
        "docker.io/library/fedora:44",
    ],
    # Pack LPIC-2 LDAP: servidor OpenLDAP y cliente sssd (images/ldap-srv e images/ldap-cli; comparten CA de laboratorio)
    "ldap-srv": [
        "localhost/chaos-ldap-srv:1",
    ],
    "ldap-cli": [
        "localhost/chaos-ldap-cli:1",
    ],
    # Pack de redes (images/redes): iproute2, nftables, nginx, FRR parado…
    "redes": [
        "localhost/chaos-redes:1",
        "docker.io/library/debian:trixie",
    ],
    "rocky": [
        "localhost/chaos-rocky:1",
        "docker.io/rockylinux/rockylinux:9",
    ],
    "nginx": [
        "localhost/chaos-nginx:1",
        "docker.io/library/nginx:alpine",
    ],
    "redis": [
        "localhost/chaos-redis:1",
        "docker.io/library/redis:7-alpine",
    ],
    "alpine": [
        "docker.io/library/alpine:3.22",
    ],
}


def _run_cmd(args: list[str], timeout: int = 30, input_text: str | None = None) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=input_text,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out.strip()
    except subprocess.TimeoutExpired:
        return 124, f"Timeout ({timeout}s) ejecutando: {' '.join(args[:4])}"
    except Exception as exc:
        return 1, str(exc)



# -------------------- Redes, IPs y corrector por script (funciones puras, fáciles de probar) --------------------

NETWORK_PREFIX = "chaoslab-"

# Preámbulo que se antepone a todo check_script
CHECK_PREAMBLE = (
    "ok()  { printf '✔ %s\\n' \"$1\"; }\n"
    "mal() { printf '✘ %s\\n' \"$1\"; }\n"
    "comprueba() { local d=\"$1\"; shift; if \"$@\" >/dev/null 2>&1; then ok \"$d\"; else mal \"$d\"; fi; }\n"
)
CHECK_SCRIPT_TIMEOUT = 60
CHECK_EMPTY_LABEL = "El corrector no devolvió resultados"
CHECK_NO_CWD_LABEL = "Falta el directorio de trabajo"


def _env_name(text: str) -> str:
    """Nombre de variable de entorno: mayúsculas y guiones -> _."""
    return text.upper().replace("-", "_")


def _plan_networks(inst: dict[str, Any]) -> tuple[list[str], dict[str, list[str]]]:
    """Redes reales a crear y redes de cada nodo (nombres reales `chaoslab-<corto>`).

    Sin `networks` en el escenario: comportamiento clásico (chaoslab-net si hay más de 1 nodo, ninguna con 1).
    """
    nodes = inst["nodes"]
    declared = inst.get("networks")
    if not declared:
        if len(nodes) > 1:
            return [NETWORK_NAME], {n["role"]: [NETWORK_NAME] for n in nodes}
        return [], {n["role"]: [] for n in nodes}
    nets = [f"{NETWORK_PREFIX}{short}" for short in declared]
    per_node: dict[str, list[str]] = {}
    for n in nodes:
        wanted = n.get("networks") or [declared[0]]
        per_node[n["role"]] = [f"{NETWORK_PREFIX}{short}" for short in wanted]
    return nets, per_node


def _manual_networks(inst: dict[str, Any]) -> bool:
    """¿Las redes del escenario son «manuales» (sin IPAM, estilo containerlab)? Campo `network_mode: "manual"`.

    En una red manual el motor NO reparte IPs ni rutas: el nodo las pone en su `setup_sh` (`ip addr add`,
    `ip route add`). La red i-ésima de un nodo (orden de su lista `networks`) es siempre `eth{i}`.
    """
    return inst.get("network_mode") == "manual"


# Docker no tiene `--ipam-driver none`: la red manual se crea `--internal` con una subred cualquiera (una distinta por
# red) y el motor vacía direcciones y rutas de sus interfaces al arrancar el nodo (ver `_manual_prep_cmd`).
DOCKER_MANUAL_SUBNET = "10.213.{i}.0/24"


def _network_create_cmd(net: str, manual: bool = False, index: int = 0, runtime: str | None = None) -> list[str]:
    """Comando para crear una red. Manual: interna (sin salida a fuera) y sin IPAM en Podman."""
    rt = runtime or RUNTIME
    if not manual:
        return [rt, "network", "create", net]
    if rt == "podman":
        return [rt, "network", "create", "--internal", "--ipam-driver", "none", net]
    return [rt, "network", "create", "--internal", "--subnet", DOCKER_MANUAL_SUBNET.format(i=index), net]


def _manual_prep_cmd(cname: str, nets: list[str], runtime: str | None = None) -> list[str] | None:
    """Docker: vacía direcciones y rutas de las interfaces eth0..ethN-1 (la subred de relleno no debe verse).
    Podman con `--ipam-driver none` no necesita nada (devuelve None). Hace falta NET_ADMIN en el nodo."""
    if (runtime or RUNTIME) == "podman" or not nets:
        return None
    script = "; ".join(f"ip -4 addr flush dev eth{i}; ip -4 route flush dev eth{i} 2>/dev/null || true" for i in range(len(nets)))
    return [runtime or RUNTIME, "exec", "--user", "root", cname, "sh", "-c", script]


def _build_run_cmd(n: dict[str, Any], cname: str, image: str, nets: list[str]) -> list[str]:
    """Comando `run` de un nodo: arranca en su primera red; las demás se conectan después.

    `sysctl_rw: true` en el nodo → `--security-opt systempaths=unconfined` (deja /proc/sys escribible: `sysctl -w
    net.ipv4.ip_forward=1` en un router). Quita una protección del contenedor: solo para nodos que lo necesiten.
    """
    role = n["role"]
    cmd = [RUNTIME, "run", "-d", "--rm", "--user", "root", "--name", cname,
           "--hostname", role, "--memory", "384m"]
    if nets:
        cmd.extend(["--network", nets[0], "--network-alias", role])
    for cap in n.get("caps", []):
        cmd.extend(["--cap-add", cap])
    for sk, sv in (n.get("sysctls") or {}).items():
        cmd.extend(["--sysctl", f"{sk}={sv}"])
    if n.get("sysctl_rw"):
        cmd.extend(["--security-opt", "systempaths=unconfined"])
    cmd.extend([image, "sh", "-c", "trap : TERM INT; while true; do sleep 30; done"])
    return cmd


def _connect_cmds(role: str, cname: str, nets: list[str]) -> list[list[str]]:
    """`network connect` para las redes adicionales (valen igual en Podman y Docker)."""
    return [[RUNTIME, "network", "connect", "--alias", role, net, cname] for net in nets[1:]]


def _parse_net_ips(inspect_json: str, nets: list[str]) -> dict[str, str]:
    """IP del contenedor en cada red, a partir de `inspect -f {{json .NetworkSettings.Networks}}`.

    Devuelve {nombre real de red: ip}. En Docker y Podman la clave es el nombre de la red; si por algún
    motivo no coincide (p. ej. Podman con un id), se reparten por orden las IPs no asignadas.
    """
    try:
        data = json.loads(inspect_json) or {}
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    found: dict[str, str] = {}
    for net in nets:
        entry = data.get(net)
        ip = (entry or {}).get("IPAddress") if isinstance(entry, dict) else None
        if ip:
            found[net] = ip
    if len(found) < len(nets):
        rest = [
            v.get("IPAddress") for k, v in data.items()
            if isinstance(v, dict) and k not in nets and v.get("IPAddress")
        ]
        for net in nets:
            if net not in found and rest:
                found[net] = rest.pop(0)
    return found


def _short_net(net: str) -> str:
    return net[len(NETWORK_PREFIX):] if net.startswith(NETWORK_PREFIX) else net


def _design_ips(n: dict[str, Any], nets: list[str]) -> dict[str, str]:
    """IPs «de diseño» de un nodo en redes manuales: {nombre corto de red: ip} (solo de sus redes, sin /prefijo).

    Son datos del encargo/diseño (el esquema y /etc/chaos_nodes.env las usan); nunca reflejan una avería.
    """
    shorts = [_short_net(net) for net in nets]
    declared = n.get("design_ips") or {}
    return {s: str(declared[s]).split("/")[0] for s in shorts if s in declared}


def _build_check_script(cs: dict[str, Any]) -> str:
    """Texto completo que se pasa por stdin a `bash -s`: preámbulo + (cd) + script del escenario."""
    parts = [CHECK_PREAMBLE, ". /etc/chaos_nodes.env 2>/dev/null\n"]
    cwd = cs.get("cwd")
    if cwd:
        parts.append(f"cd {shlex.quote(cwd)} 2>/dev/null || {{ mal {shlex.quote(CHECK_NO_CWD_LABEL)}; exit 0; }}\n")
    # Entre llaves y con stdin a /dev/null: bash lee el bloque entero antes de ejecutarlo, así ninguna orden
    # (ssh, read, cat…) se come el resto del corrector que llega por la misma entrada estándar.
    parts.append("{\n")
    parts.append(cs.get("script", ""))
    parts.append("\n} </dev/null\n")
    return "".join(parts)


def _check_blocks(cs: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bloques de corrector de un escenario: `check_script` puede ser un dict (un nodo) o una lista de dicts
    {node, cwd, script} (un bloque por nodo; las sondas se unen en el orden de la lista)."""
    return [cs] if isinstance(cs, dict) else list(cs or [])


def _map_checks_to_topology(inst: dict[str, Any]) -> None:
    """Corrector por script: las sondas de un bloque con `marca` (node:<rol>, link:<n>, entry) pintan ese
    elemento del esquema tras «Verificar». Sin marcas no cambia nada."""
    marks = {c["id"]: c["target"] for c in inst.get("checks", []) if c.get("target")}
    topo = inst.get("topology")
    if marks and isinstance(topo, dict):
        topo["checks"] = marks


# -------------------- Progreso exportable --------------------

PROGRESS_FORMAT = "chaos-lab-progress"
_RANKS = {"S+", "S", "A", "B", "C"}
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
_MAX_HISTORY = 100


def _int_ge0(v: Any, limit: int = 10**9) -> int:
    if isinstance(v, bool) or not isinstance(v, int):  # json.loads da int para enteros; 1.5, NaN o Infinity no valen
        raise ValueError("número no válido")
    n = v
    if n < 0 or n > limit:
        raise ValueError("número fuera de rango")
    return n


def _short_str(v: Any, limit: int = 200) -> str:
    if not isinstance(v, str):
        raise ValueError("texto no válido")
    return v[:limit]


def sanitize_progress(data: Any) -> dict[str, Any]:
    """Valida un fichero de progreso exportado y devuelve solo los campos conocidos, con sus tipos.
    Acepta también un `state.json` copiado tal cual (sin `format`). Lanza ValueError si no vale."""
    if not isinstance(data, dict):
        raise ValueError("El fichero no es un progreso de Chaos Lab.")
    if "format" in data and data["format"] != PROGRESS_FORMAT:
        raise ValueError("El fichero no es un progreso de Chaos Lab.")
    if not isinstance(data.get("solved", {}), dict) or not isinstance(data.get("history", []), list):
        raise ValueError("El fichero no es un progreso de Chaos Lab.")
    try:
        solved: dict[str, Any] = {}
        for sid, rec in data.get("solved", {}).items():
            if not isinstance(sid, str) or not _ID_RE.match(sid) or not isinstance(rec, dict):
                raise ValueError(f"escenario no válido: {str(sid)[:40]}")
            rank = rec.get("best_rank", "C")
            solved[sid] = {
                "best_time_s": _int_ge0(rec.get("best_time_s", 0)),
                "best_rank": rank if rank in _RANKS else "C",
                "count": max(1, _int_ge0(rec.get("count", 1))),
                "last_solved": _short_str(rec.get("last_solved", ""), 40),
            }
        history = []
        for h in data.get("history", [])[-_MAX_HISTORY:]:
            if not isinstance(h, dict) or not _ID_RE.match(str(h.get("id", ""))):
                raise ValueError("entrada de historial no válida")
            rank = h.get("rank", "C")
            history.append({
                "id": h["id"],
                "title": _short_str(h.get("title", h["id"])),
                "blind_mode": bool(h.get("blind_mode", False)),
                "elapsed_s": _int_ge0(h.get("elapsed_s", 0)),
                "rank": rank if rank in _RANKS else "C",
                "xp": _int_ge0(h.get("xp", 0), 100000),
                "hints_used": _int_ge0(h.get("hints_used", 0), 100),
                "at": _short_str(h.get("at", ""), 40),
            })
        total_xp = _int_ge0(data.get("total_xp", 0))
    except (ValueError, TypeError) as e:
        raise ValueError(f"Progreso no válido: {e}") from None
    return {"solved": solved, "history": history, "total_xp": total_xp}


def _en_text(v: Any) -> str:
    return v if isinstance(v, str) and v.strip() else ""


def _catalog_i18n(item: dict[str, Any]) -> dict[str, Any]:
    """Traducción inglesa PÚBLICA de una ficha del catálogo: solo título y briefing (nunca pistas ni solución)."""
    en = (item.get("i18n") or {}).get("en") or {}
    out = {k: _en_text(en.get(k)) for k in ("title", "briefing")}
    out = {k: v for k, v in out.items() if v}
    return {"en": out} if out else {}


def _active_i18n(inst: dict[str, Any], hints_used: int, blind: bool, solved: bool) -> dict[str, Any]:
    """Traducción inglesa del escenario activo, con el MISMO filtrado que la vista en español: en modo ciego solo la
    alerta (ni título ni briefing), solo las pistas ya desbloqueadas y la solución solo tras resolver."""
    en = (inst.get("i18n") or {}).get("en") or {}
    out: dict[str, Any] = {}
    if blind:
        if _en_text(en.get("blind_alert")):
            out["description"] = en["blind_alert"]
    else:
        if _en_text(en.get("title")):
            out["title"] = en["title"]
        if _en_text(en.get("briefing")):
            out["description"] = en["briefing"]
    hints = en.get("hints")
    if isinstance(hints, list) and hints_used > 0:
        out["hints"] = [_en_text(h) for h in hints[:hints_used]]
    if solved and _en_text(en.get("solution_summary")):
        out["solution_summary"] = en["solution_summary"]
    return {"en": out} if out else {}


def _parse_check_output(out: str, node: str, start: int = 0, empty_label: str = CHECK_EMPTY_LABEL) -> list[dict[str, Any]]:
    """Líneas ✔/✘ en orden -> sondas c<start+1>, … Sin ninguna, una sonda fallida (nunca resuelto por vacío)."""
    checks: list[dict[str, Any]] = []
    for line in out.splitlines():
        line = line.strip()
        if line[:1] in ("✔", "✘"):
            checks.append({
                "id": f"c{start + len(checks) + 1}",
                "label": line[1:].strip(),
                "node": node,
                "passed": line[0] == "✔",
            })
    if not checks:
        checks.append({"id": f"c{start + 1}", "label": empty_label, "node": node, "passed": False})
    return checks


def _networks_map(inst: dict[str, Any]) -> dict[str, list[str]]:
    """Redes declaradas por el escenario -> roles que están en cada una (nombres cortos).

    Vacío si el escenario no declara `networks` (red única clásica). Un rol en 2+ redes (router) sale en todas.
    """
    declared = inst.get("networks") or []
    out: dict[str, list[str]] = {short: [] for short in declared}
    for n in inst.get("nodes") or []:
        for short in (n.get("networks") or ([declared[0]] if declared else [])):
            if short in out:
                out[short].append(n["role"])
    return out


def _public_topology(topo, blind: bool, networks: dict[str, list[str]] | None = None):
    """Esquema de la topología para la UI. En Modo Guardia oculta qué corre en cada nodo y dónde mirar.

    `networks` (estructura, no pista) se expone también a ciegas.
    """
    if not topo:
        return None
    if not blind:
        return {**topo, "networks": networks} if networks else topo
    return {
        "entry": {k: v for k, v in (topo.get("entry") or {}).items() if k != "via"} or None,
        "nodes": {role: {} for role in (topo.get("nodes") or {})},
        "links": [{"from": l["from"], "to": l["to"]} for l in topo.get("links") or []],
        "checks": {},
        **({"networks": networks} if networks else {}),
    }

class ChaosEngine:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.active: dict[str, Any] | None = None
        self._cached_local_images: set[str] | None = None
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    # -------------------- Persistencia --------------------

    def _load_state(self) -> dict[str, Any]:
        try:
            if STATE_FILE.exists():
                data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            else:
                data = {}
        except Exception:
            data = {}
        data.setdefault("solved", {})
        data.setdefault("history", [])
        data.setdefault("total_xp", 0)
        return data

    def _save_state(self, data: dict[str, Any]) -> None:
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(STATE_FILE)

    # -------------------- Exportar / importar el progreso --------------------

    def export_progress(self) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
        return {
            "format": PROGRESS_FORMAT,
            "version": 1,
            "exported_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "solved": state["solved"],
            "history": state["history"],
            "total_xp": state["total_xp"],
        }

    def import_progress(self, data: Any) -> dict[str, Any]:
        """Sustituye el progreso por el de un fichero exportado. Valida y limpia todo; guarda copia del actual."""
        clean = sanitize_progress(data)  # ValueError si no es un fichero de progreso válido
        with self._lock:
            if STATE_FILE.exists():
                stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")  # con microsegundos: nunca pisa otra copia
                backup = STATE_FILE.with_name(f"state.antes-de-importar-{stamp}.json")
                backup.write_text(STATE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
            self._save_state(clean)
        return {"solved": len(clean["solved"]), "history": len(clean["history"]), "total_xp": clean["total_xp"]}

    # -------------------- Imágenes (Podman o Docker) --------------------

    def _local_images(self, refresh: bool = False) -> set[str]:
        if self._cached_local_images is not None and not refresh:
            return self._cached_local_images
        rc, out = _run_cmd([RUNTIME, "images", "--format", "{{.Repository}}:{{.Tag}}"], timeout=8)
        if rc == 0:
            imgs = {line.strip() for line in out.splitlines() if line.strip() and "<none>" not in line}
            self._cached_local_images = imgs
            return imgs
        return set()

    def resolve_image(self, distro: str) -> str:
        local = self._local_images()
        candidates = IMAGE_CANDIDATES.get(distro, IMAGE_CANDIDATES["debian"])
        for cand in candidates:
            if cand in local:
                return cand
            short = cand.replace("docker.io/library/", "").replace("docker.io/", "")
            for existing in local:
                if existing.endswith(short):
                    return existing
        return candidates[0]

    def _probe_tools(self, container: str) -> list[str]:
        """Herramientas que hay de verdad en el nodo (se muestran en «🧰 Herramientas» de la UI)."""
        probe = "for t in " + " ".join(NODE_TOOLS) + "; do command -v $t >/dev/null 2>&1 && echo $t; done; true"
        rc, out = _run_cmd([RUNTIME, "exec", container, "sh", "-c", probe], timeout=8)
        return out.split() if rc == 0 else []

    def runtime_health(self) -> dict[str, Any]:
        rc, out = _run_cmd([RUNTIME, "--version"], timeout=5)
        imgs = self._local_images()
        return {
            "engine": RUNTIME,
            "podman_ok": rc == 0,  # nombre histórico: «motor OK» (Podman o Docker)
            "podman_version": out if rc == 0 else None,
            "cached_images_count": len(imgs),
            "error": None if rc == 0 else out,
        }

    # -------------------- Limpieza e Infra --------------------

    def cleanup_containers(self) -> None:
        rc, out = _run_cmd(
            [RUNTIME, "ps", "-a", "--filter", f"name=^{CONTAINER_PREFIX}", "--format", "{{.Names}}"],
            timeout=10,
        )
        if rc == 0 and out:
            names = [n.strip() for n in out.splitlines() if n.strip()]
            if names:
                _run_cmd([RUNTIME, "rm", "-f", *names], timeout=20)
        rc_n, out_n = _run_cmd([RUNTIME, "network", "ls", "--format", "{{.Name}}"], timeout=10)
        nets = []
        if rc_n == 0 and out_n:
            nets = [n.strip() for n in out_n.splitlines() if n.strip().startswith(NETWORK_PREFIX)]
        if NETWORK_NAME not in nets:
            nets.append(NETWORK_NAME)
        for net in nets:
            _run_cmd([RUNTIME, "network", "rm", "-f", net], timeout=10)

    def stop_active(self) -> dict[str, Any]:
        with self._lock:
            prev = self.active["id"] if self.active else None
            self.cleanup_containers()
            self.active = None
            return {"ok": True, "stopped": prev}

    # -------------------- Catálogo y Estado --------------------

    def get_catalog_view(self) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            solved_map = state["solved"]
            scenarios_out = []
            for item in SCENARIO_CATALOG:
                sid = item["id"]
                s_info = solved_map.get(sid)
                # Previsualizar nodos sin mutar
                sample = instantiate_scenario(sid, seed=42)
                scenarios_out.append(
                    {
                        "id": sid,
                        "title": item["title"],
                        "category": item["category"],
                        "difficulty": item["difficulty"],
                        "points": item["points"],
                        "estimated_min": item["estimated_min"],
                        "tags": item["tags"],
                        "certs": item.get("certs", []),
                        "briefing": item["briefing"],
                        "i18n": _catalog_i18n(item),
                        "tipo": item.get("tipo", "averia"),
                        "node_count": len(sample["nodes"]),
                        "nodes": [n["role"] for n in sample["nodes"]],
                        # Vista previa (sin desplegar): lo mismo que se ve al lanzar, sin pistas ni dónde mirar
                        "machines": [
                            {"role": n["role"], "runs": ((sample.get("topology") or {}).get("nodes") or {}).get(n["role"], {}).get("runs", "")}
                            for n in sample["nodes"]
                        ],
                        "links": [
                            {k: l.get(k, "") for k in ("from", "to", "via")}
                            for l in ((sample.get("topology") or {}).get("links") or [])
                        ],
                        "entry": (sample.get("topology") or {}).get("entry"),
                        "networks": _networks_map(sample),
                        "objetivos_lpi": item.get("objetivos_lpi", []),
                        "solved": bool(s_info),
                        "best_time_s": s_info.get("best_time_s") if s_info else None,
                        "best_rank": s_info.get("best_rank") if s_info else None,
                        "times_solved": s_info.get("count", 0) if s_info else 0,
                    }
                )
            return {
                "scenarios": scenarios_out,
                "stats": {
                    "total_scenarios": len(SCENARIO_CATALOG),
                    "solved_count": len(solved_map),
                    "total_xp": state.get("total_xp", 0),
                    "history": state.get("history", [])[-15:][::-1],
                },
                "active": self.public_active_view(),
            }

    def public_active_view(self) -> dict[str, Any] | None:
        with self._lock:
            if not self.active:
                return None
            act = self.active
            inst = act["instance"]
            blind = act["blind_mode"] and not act["solved"]
            revealed_hints = inst["hints"][: act["hints_used"]]

            checks_view = []
            for idx, chk in enumerate(inst.get("checks", []), start=1):
                last_ok = act["last_check_map"].get(chk["id"], False)
                checks_view.append(
                    {
                        "id": chk["id"],
                        "label": f" Sonda de salud #{idx} (oculta en Modo Guardia)" if blind else chk["label"],
                        "node": chk["node"],
                        "passed": last_ok,
                    }
                )

            return {
                "session_id": act["session_id"],
                "scenario_id": "mystery-incident" if blind else inst["id"],
                "real_scenario_id": inst["id"] if not blind else None,
                "title": "🚨 INCIDENTE EN GUARDIA (Causa Raíz Oculta)" if blind else inst["title"],
                "category": "Modo Guardia 3:00 AM" if blind else inst["category"],
                "difficulty": inst["difficulty"],
                "points": int(inst["points"] * 1.25) if act["blind_mode"] else inst["points"],
                "tipo": inst.get("tipo", "averia"),
                "blind_mode": act["blind_mode"],
                "blind_masked": blind,
                "seed": inst["seed"],
                "description": inst["blind_alert"] if blind else inst["briefing"],
                "started_at": act["started_at"],
                "elapsed_s": int(time.time() - act["started_at"]) if not act["solved"] else act["solved_elapsed_s"],
                "solved": act["solved"],
                "rank": act.get("rank"),
                "earned_xp": act.get("earned_xp"),
                "hints_used": act["hints_used"],
                "total_hints": len(inst["hints"]),
                "hints": revealed_hints,
                "nodes": [
                    {
                        "role": n["role"],
                        "container": n["container"],
                        "distro": n["distro"],
                        "image": n["image"],
                        "ip": n.get("ip", "127.0.0.1"),
                        "ips": n.get("ips", {}),
                        "workdir": n.get("workdir"),
                        "shell": n["shell"],
                        "tools": n.get("tools", []),
                        "cli_attach": (
                            f"{RUNTIME} exec -it --user {n['default_user']}"
                            + (f" -w {shlex.quote(n['workdir'])}" if n.get("workdir") else "")
                            + f" {n['container']} {n['shell']}"
                        ),
                    }
                    for n in act["nodes_runtime"]
                ],
                "checks": checks_view,
                "topology": _public_topology(inst.get("topology"), blind, _networks_map(inst)),
                "timeline": act.get("timeline") or [],
                "solution_summary": inst["solution_summary"] if act["solved"] else None,
                "i18n": _active_i18n(inst, act["hints_used"], blind, act["solved"]),
            }

    # -------------------- Lanzamiento --------------------

    def launch(
        self,
        scenario_id: str | None = None,
        blind_mode: bool = False,
        difficulty_filter: str | None = None,
        seed: int | None = None,
        record: bool = True,
    ) -> dict[str, Any]:
        with self._lock:
            if blind_mode and not scenario_id:
                # Una «tarea» (configurar desde cero) no es un incidente: la guardia sortea solo averías
                pool = [s for s in SCENARIO_CATALOG if s.get("tipo", "averia") == "averia"]
                if difficulty_filter and difficulty_filter != "Todos":
                    filtered = [s for s in pool if s["difficulty"] == difficulty_filter]
                    if filtered:
                        pool = filtered
                chosen = random.choice(pool)
                scenario_id = chosen["id"]

            if not scenario_id or scenario_id not in SCENARIOS_BY_ID:
                return {"ok": False, "error": f"Escenario inválido: {scenario_id}"}

            # Limpiar sesión previa
            self.cleanup_containers()
            self.active = None
            self._local_images(refresh=True)

            inst = instantiate_scenario(scenario_id, seed=seed)
            all_nets, nets_by_role = _plan_networks(inst)

            manual = _manual_networks(inst)
            for i, net in enumerate(all_nets):
                rc_net, out_net = _run_cmd(_network_create_cmd(net, manual, i), timeout=12)
                if rc_net != 0:
                    self.cleanup_containers()
                    return {"ok": False, "error": f"No se pudo crear la red {RUNTIME} ({net}): {out_net}"}

            nodes_runtime: list[dict[str, Any]] = []
            session_id = f"{int(time.time())}-{inst['seed']}"

            for n in inst["nodes"]:
                role = n["role"]
                cname = f"{CONTAINER_PREFIX}{role}"
                image = self.resolve_image(n["distro"])

                nets = nets_by_role.get(role, [])
                cmd = _build_run_cmd(n, cname, image, nets)

                rc_run, out_run = _run_cmd(cmd, timeout=35)
                if rc_run != 0:
                    self.cleanup_containers()
                    return {
                        "ok": False,
                        "error": f"Fallo al arrancar nodo '{role}' ({image}): {out_run[:260]}",
                    }

                connect_err = None
                for ccmd in _connect_cmds(role, cname, nets):
                    rc_c, out_c = _run_cmd(ccmd, timeout=15)
                    if rc_c != 0:
                        connect_err = out_c
                        break
                if connect_err is not None:
                    self.cleanup_containers()
                    return {
                        "ok": False,
                        "error": f"No se pudo conectar el nodo '{role}' a sus redes: {connect_err[:260]}",
                    }

                if manual:
                    prep = _manual_prep_cmd(cname, nets)
                    if prep:
                        rc_p, out_p = _run_cmd(prep, timeout=15)
                        if rc_p != 0:
                            self.cleanup_containers()
                            return {"ok": False, "error": f"No se pudo vaciar la red de '{role}': {out_p[:260]}"}

                ip_addr = "127.0.0.1"
                ips: dict[str, str] = {}
                if manual:
                    # Sin IPAM no hay IPs que leer: se enseñan las «de diseño» que declara el escenario
                    ips = _design_ips(n, nets)
                    ip_addr = ips.get(_short_net(nets[0]), ip_addr) if nets else ip_addr
                elif nets:
                    rc_ip, out_ip = _run_cmd(
                        [RUNTIME, "inspect", "-f", "{{json .NetworkSettings.Networks}}", cname],
                        timeout=8,
                    )
                    if rc_ip == 0:
                        by_net = _parse_net_ips(out_ip, nets)
                        ips = {_short_net(net): ip for net, ip in by_net.items()}
                        if nets[0] in by_net:
                            ip_addr = by_net[nets[0]]

                nodes_runtime.append(
                    {
                        "role": role,
                        "container": cname,
                        "distro": n["distro"],
                        "image": image,
                        "shell": n.get("shell", "/bin/sh"),
                        "default_user": n.get("default_user", "root"),
                        "ip": ip_addr,
                        "ips": ips,
                        "workdir": n.get("workdir"),
                        "setup_sh": n["setup_sh"],
                    }
                )

            # Escribir /etc/chaos_nodes.env en cada contenedor y configurar prompt claro
            env_lines = []
            for nr in nodes_runtime:
                base = f"IP_{_env_name(nr['role'])}"
                env_lines.append(f"{base}={nr['ip']}")
                for short, ip in nr.get("ips", {}).items():
                    env_lines.append(f"{base}_{_env_name(short)}={ip}")
            env_payload = "\n".join(env_lines) + "\n"

            # Los escenarios SecOps instalan sshd/rsyslog con apt dentro del contenedor: más margen
            n_timeouts = {n["role"]: n.get("setup_timeout", 25) for n in inst["nodes"]}
            for nr in nodes_runtime:
                bootstrap_env = (
                    f"cat << 'EOF' > /etc/chaos_nodes.env\n{env_payload}EOF\n"
                    f"chmod 0644 /etc/chaos_nodes.env\n"
                )
                _run_cmd([RUNTIME, "exec", nr["container"], "sh", "-c", bootstrap_env], timeout=10)

                # Ejecutar setup_sh inyectando avería
                shell_bin = nr["shell"]
                rc_setup, out_setup = _run_cmd(
                    [
                        RUNTIME,
                        "exec",
                        nr["container"],
                        shell_bin,
                        "-c",
                        f"source /etc/chaos_nodes.env 2>/dev/null || . /etc/chaos_nodes.env; {nr['setup_sh']}",
                    ],
                    timeout=int(n_timeouts.get(nr["role"], 25)),
                )
                if rc_setup != 0:
                    self.cleanup_containers()
                    return {
                        "ok": False,
                        "error": f"Error al inyectar escenario en '{nr['role']}': {out_setup[:300]}",
                    }
                nr["tools"] = self._probe_tools(nr["container"])

            # Corrector por script: una primera ejecución para conocer las etiquetas (el jugador empieza en rojo)
            if inst.get("check_script"):
                inst["checks"] = self._run_check_script(inst["check_script"], nodes_runtime)
                _map_checks_to_topology(inst)

            self.active = {
                "id": inst["id"],
                "session_id": session_id,
                "instance": inst,
                "nodes_runtime": nodes_runtime,
                "blind_mode": blind_mode,
                "record": record,
                "started_at": time.time(),
                "solved": False,
                "solved_elapsed_s": 0,
                "hints_used": 0,
                "last_check_map": {c["id"]: False for c in inst.get("checks", [])},
                "transcript": [],  # comandos capturados para el mentor/post-mortem
                "timeline": [],  # señales correlacionadas de la alerta (solo escenarios sec-* en Guardia)
            }
            if blind_mode and inst["id"].startswith("sec-") and inst.get("signals"):
                try:
                    self.active["timeline"] = collect_timeline(self.active)
                except Exception:
                    self.active["timeline"] = []
            return {"ok": True, "active": self.public_active_view()}

    # -------------------- Pistas y Revelado --------------------

    def unlock_hint(self) -> dict[str, Any]:
        with self._lock:
            if not self.active:
                return {"ok": False, "error": "No hay ningún laboratorio activo."}
            inst = self.active["instance"]
            if self.active["hints_used"] < len(inst["hints"]):
                self.active["hints_used"] += 1
            return {"ok": True, "active": self.public_active_view()}

    def reveal_blind_identity(self) -> dict[str, Any]:
        with self._lock:
            if not self.active:
                return {"ok": False, "error": "No hay laboratorio activo."}
            self.active["blind_mode"] = False
            return {"ok": True, "active": self.public_active_view()}

    def record_command_line(self, role: str, line: str) -> None:
        clean = line.strip()
        if not clean:
            return
        with self._lock:
            if self.active is not None:
                self.active["transcript"].append(
                    {
                        "ts": int(time.time() - self.active["started_at"]),
                        "node": role,
                        "cmd": clean[:300],
                    }
                )
                self.active["transcript"] = self.active["transcript"][-80:]

    def get_node_runtime(self, role: str | None = None) -> dict[str, Any] | None:
        with self._lock:
            if not self.active:
                return None
            nodes = self.active["nodes_runtime"]
            if not role:
                return nodes[0]
            for n in nodes:
                if n["role"] == role:
                    return n
            return None

    # -------------------- Verificación Multi-Check --------------------

    def _run_check_script(self, cs: dict[str, Any], nodes_runtime: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ejecuta el corrector (bash -s por stdin, como root, un bloque por nodo si es una lista) y devuelve
        las sondas con su estado: ids únicos c1, c2… seguidos a lo largo de todos los bloques."""
        blocks = _check_blocks(cs)
        multi = len(blocks) > 1
        checks: list[dict[str, Any]] = []
        for blk in blocks:
            role = blk.get("node") or (nodes_runtime[0]["role"] if nodes_runtime else "")
            empty = f"{CHECK_EMPTY_LABEL} ({role})" if multi else CHECK_EMPTY_LABEL
            nr = next((n for n in nodes_runtime if n["role"] == role), None)
            if nr is None:
                checks.extend(_parse_check_output("", role, len(checks), empty))
                continue
            _rc, out = _run_cmd(
                [RUNTIME, "exec", "-i", "--user", "root", nr["container"], "bash", "-s"],
                timeout=CHECK_SCRIPT_TIMEOUT,
                input_text=_build_check_script(blk),
            )
            if multi and not re.search(r"\b(comprueba|ok|mal)\b", blk.get("script", "")):
                # Bloque auxiliar (p. ej. vaciar la caché de sssd antes de las sondas de otro nodo): no da sondas
                continue
            parsed = _parse_check_output(out, role, len(checks), empty)
            if blk.get("marca"):
                for c in parsed:
                    c["target"] = blk["marca"]
            checks.extend(parsed)
        if not checks:
            checks = _parse_check_output("", blocks[0].get("node", "") if blocks else "", 0)
        return checks

    def verify(self) -> dict[str, Any]:
        with self._lock:
            if not self.active:
                return {"ok": False, "error": "No hay ningún escenario en ejecución."}

            act = self.active
            inst = act["instance"]
            node_by_role = {n["role"]: n for n in act["nodes_runtime"]}

            passed_count = 0
            if inst.get("check_script"):
                # Se reejecuta el script: manda lo último (etiquetas y estados)
                fresh = self._run_check_script(inst["check_script"], act["nodes_runtime"])
                inst["checks"] = [{k: v for k, v in c.items() if k != "passed"} for c in fresh]
                _map_checks_to_topology(inst)
                act["last_check_map"] = {c["id"]: c["passed"] for c in fresh}
                passed_count = sum(1 for c in fresh if c["passed"])
            for chk in ([] if inst.get("check_script") else inst.get("checks", [])):
                nr = node_by_role[chk["node"]]
                shell_bin = nr["shell"]
                rc, _out = _run_cmd(
                    [
                        RUNTIME,
                        "exec",
                        nr["container"],
                        shell_bin,
                        "-c",
                        chk["cmd"],
                    ],
                    timeout=12,
                )
                is_ok = rc == 0
                act["last_check_map"][chk["id"]] = is_ok
                if is_ok:
                    passed_count += 1

            total_checks = len(inst.get("checks", []))
            all_passed = total_checks > 0 and passed_count == total_checks

            if all_passed and not act["solved"]:
                elapsed = max(1, int(time.time() - act["started_at"]))
                act["solved"] = True
                act["solved_elapsed_s"] = elapsed

                base_pts = int(inst["points"] * 1.25) if act["blind_mode"] else inst["points"]
                penalty = act["hints_used"] * int(base_pts * 0.15)
                earned_xp = max(int(base_pts * 0.4), base_pts - penalty)

                target_s = inst["estimated_min"] * 60
                if act["hints_used"] == 0 and elapsed <= target_s:
                    rank = "S+" if act["blind_mode"] else "S"
                elif act["hints_used"] <= 1 and elapsed <= target_s * 1.5:
                    rank = "A"
                elif act["hints_used"] <= 2:
                    rank = "B"
                else:
                    rank = "C"

                act["rank"] = rank
                act["earned_xp"] = earned_xp

                # Persistir progreso (salvo lanzamientos de prueba: record=False, p. ej. tests/e2e)
                if act.get("record", True):
                    state = self._load_state()
                    prev = state["solved"].get(inst["id"]) or {}
                    best_t = min(elapsed, prev.get("best_time_s", elapsed))
                    rank_order = {"S+": 5, "S": 4, "A": 3, "B": 2, "C": 1}
                    prev_rank = prev.get("best_rank", "C")
                    best_rank = rank if rank_order.get(rank, 0) >= rank_order.get(prev_rank, 0) else prev_rank

                    state["solved"][inst["id"]] = {
                        "best_time_s": best_t,
                        "best_rank": best_rank,
                        "count": int(prev.get("count", 0)) + 1,
                        "last_solved": datetime.datetime.now().isoformat(timespec="seconds"),
                    }
                    state["total_xp"] = int(state.get("total_xp", 0)) + earned_xp
                    state["history"].append(
                        {
                            "id": inst["id"],
                            "title": inst["title"],
                            "blind_mode": act["blind_mode"],
                            "elapsed_s": elapsed,
                            "rank": rank,
                            "xp": earned_xp,
                            "hints_used": act["hints_used"],
                            "at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        }
                    )
                    state["history"] = state["history"][-100:]
                    self._save_state(state)

            return {
                "ok": True,
                "all_passed": all_passed,
                "passed_count": passed_count,
                "total_checks": total_checks,
                "active": self.public_active_view(),
            }
