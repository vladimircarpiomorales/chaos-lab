"""
Motor de ejecución de laboratorios efímeros sobre Podman rootless.
Soporta topologías de 1 a N nodos en red aislada, inyección de averías mutables,
verificación granular por objetivos y persistencia de progreso/rachas.
"""

from __future__ import annotations

import datetime
import json
import os
import random
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from .mentor import collect_timeline
from .scenarios import SCENARIO_CATALOG, SCENARIOS_BY_ID, instantiate_scenario

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = BASE_DIR / "data" / "state.json"

CONTAINER_PREFIX = "chaoslab-"
# Herramientas que se buscan en cada nodo al desplegar (orden = orden en la UI)
NODE_TOOLS = ["nano", "vim", "vi", "less", "curl", "wget", "ss", "ip", "dig", "ps", "top",
              "nc", "nft", "iptables", "tcpdump", "openssl", "python3"]
NETWORK_NAME = "chaoslab-net"

IMAGE_CANDIDATES: dict[str, list[str]] = {
    "debian": [
        "localhost/lpi-lab-debian:trixie-v3",
        "localhost/lpi-lab-debian:trixie-v1",
        "docker.io/library/debian:trixie",
        "docker.io/library/debian:13",
        "docker.io/library/debian:12",
        "docker.io/library/ubuntu:24.04",
    ],
    "rocky": [
        "localhost/lpi-lab-rocky:9-v2",
        "localhost/lpi-lab-fedora:44-v2",
        "docker.io/rockylinux/rockylinux:9",
        "localhost/lpi-lab-debian:trixie-v3",
    ],
    "nginx": [
        "localhost/chaos-nginx:1",  # images/construir.sh: + nano, vim, ss, dig...
        "docker.io/library/nginx:alpine",
        "nginx:alpine",
    ],
    "redis": [
        "localhost/chaos-redis:1",
        "docker.io/library/redis:7-alpine",
        "docker.io/library/redis:alpine",
        "docker.io/library/redis:6.2-alpine",
    ],
    "alpine": [
        "docker.io/library/alpine:3.22",
        "localhost/lpi-lab-debian:trixie-v3",
    ],
}


def _run_cmd(args: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out.strip()
    except subprocess.TimeoutExpired:
        return 124, f"Timeout ({timeout}s) ejecutando: {' '.join(args[:4])}"
    except Exception as exc:
        return 1, str(exc)



def _public_topology(topo, blind: bool):
    """Esquema de la topología para la UI. En Modo Guardia oculta qué corre en cada nodo y dónde mirar."""
    if not topo:
        return None
    if not blind:
        return topo
    return {
        "entry": {k: v for k, v in (topo.get("entry") or {}).items() if k != "via"} or None,
        "nodes": {role: {} for role in (topo.get("nodes") or {})},
        "links": [{"from": l["from"], "to": l["to"]} for l in topo.get("links") or []],
        "checks": {},
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

    # -------------------- Imágenes Podman --------------------

    def _local_images(self, refresh: bool = False) -> set[str]:
        if self._cached_local_images is not None and not refresh:
            return self._cached_local_images
        rc, out = _run_cmd(["podman", "images", "--format", "{{.Repository}}:{{.Tag}}"], timeout=8)
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
        rc, out = _run_cmd(["podman", "exec", container, "sh", "-c", probe], timeout=8)
        return out.split() if rc == 0 else []

    def runtime_health(self) -> dict[str, Any]:
        rc, out = _run_cmd(["podman", "--version"], timeout=5)
        imgs = self._local_images()
        return {
            "podman_ok": rc == 0,
            "podman_version": out if rc == 0 else None,
            "cached_images_count": len(imgs),
            "error": None if rc == 0 else out,
        }

    # -------------------- Limpieza e Infra --------------------

    def cleanup_containers(self) -> None:
        rc, out = _run_cmd(
            ["podman", "ps", "-a", "--filter", f"name=^{CONTAINER_PREFIX}", "--format", "{{.Names}}"],
            timeout=10,
        )
        if rc == 0 and out:
            names = [n.strip() for n in out.splitlines() if n.strip()]
            if names:
                _run_cmd(["podman", "rm", "-f", *names], timeout=20)
        _run_cmd(["podman", "network", "rm", "-f", NETWORK_NAME], timeout=10)

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
                        "briefing": item["briefing"],
                        "node_count": len(sample["nodes"]),
                        "nodes": [n["role"] for n in sample["nodes"]],
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
            for idx, chk in enumerate(inst["checks"], start=1):
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
                        "shell": n["shell"],
                        "tools": n.get("tools", []),
                        "cli_attach": f"podman exec -it --user {n['default_user']} {n['container']} {n['shell']}",
                    }
                    for n in act["nodes_runtime"]
                ],
                "checks": checks_view,
                "topology": _public_topology(inst.get("topology"), blind),
                "timeline": act.get("timeline") or [],
                "solution_summary": inst["solution_summary"] if act["solved"] else None,
            }

    # -------------------- Lanzamiento --------------------

    def launch(
        self,
        scenario_id: str | None = None,
        blind_mode: bool = False,
        difficulty_filter: str | None = None,
        seed: int | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if blind_mode and not scenario_id:
                pool = SCENARIO_CATALOG
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
            multi_node = len(inst["nodes"]) > 1

            if multi_node:
                rc_net, out_net = _run_cmd(["podman", "network", "create", NETWORK_NAME], timeout=12)
                if rc_net != 0:
                    return {"ok": False, "error": f"No se pudo crear la red Podman ({NETWORK_NAME}): {out_net}"}

            nodes_runtime: list[dict[str, Any]] = []
            session_id = f"{int(time.time())}-{inst['seed']}"

            for n in inst["nodes"]:
                role = n["role"]
                cname = f"{CONTAINER_PREFIX}{role}"
                image = self.resolve_image(n["distro"])

                cmd = [
                    "podman",
                    "run",
                    "-d",
                    "--rm",
                    "--user",
                    "root",
                    "--name",
                    cname,
                    "--hostname",
                    role,
                    "--memory",
                    "384m",
                ]
                if multi_node:
                    cmd.extend(["--network", NETWORK_NAME, "--network-alias", role])
                for cap in n.get("caps", []):
                    cmd.extend(["--cap-add", cap])
                for sk, sv in (n.get("sysctls") or {}).items():
                    cmd.extend(["--sysctl", f"{sk}={sv}"])

                cmd.extend(
                    [
                        image,
                        "sh",
                        "-c",
                        "trap : TERM INT; while true; do sleep 30; done",
                    ]
                )

                rc_run, out_run = _run_cmd(cmd, timeout=35)
                if rc_run != 0:
                    self.cleanup_containers()
                    return {
                        "ok": False,
                        "error": f"Fallo al arrancar nodo '{role}' ({image}): {out_run[:260]}",
                    }

                ip_addr = "127.0.0.1"
                if multi_node:
                    rc_ip, out_ip = _run_cmd(
                        [
                            "podman",
                            "inspect",
                            "-f",
                            "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
                            cname,
                        ],
                        timeout=8,
                    )
                    if rc_ip == 0 and out_ip.strip():
                        ip_addr = out_ip.strip()

                nodes_runtime.append(
                    {
                        "role": role,
                        "container": cname,
                        "distro": n["distro"],
                        "image": image,
                        "shell": n.get("shell", "/bin/sh"),
                        "default_user": n.get("default_user", "root"),
                        "ip": ip_addr,
                        "setup_sh": n["setup_sh"],
                    }
                )

            # Escribir /etc/chaos_nodes.env en cada contenedor y configurar prompt claro
            env_lines = [
                f"IP_{nr['role'].upper().replace('-', '_')}={nr['ip']}"
                for nr in nodes_runtime
            ]
            env_payload = "\n".join(env_lines) + "\n"

            # Los escenarios SecOps instalan sshd/rsyslog con apt dentro del contenedor: más margen
            n_timeouts = {n["role"]: n.get("setup_timeout", 25) for n in inst["nodes"]}
            for nr in nodes_runtime:
                bootstrap_env = (
                    f"cat << 'EOF' > /etc/chaos_nodes.env\n{env_payload}EOF\n"
                    f"chmod 0644 /etc/chaos_nodes.env\n"
                )
                _run_cmd(["podman", "exec", nr["container"], "sh", "-c", bootstrap_env], timeout=10)

                # Ejecutar setup_sh inyectando avería
                shell_bin = nr["shell"]
                rc_setup, out_setup = _run_cmd(
                    [
                        "podman",
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

            self.active = {
                "id": inst["id"],
                "session_id": session_id,
                "instance": inst,
                "nodes_runtime": nodes_runtime,
                "blind_mode": blind_mode,
                "started_at": time.time(),
                "solved": False,
                "solved_elapsed_s": 0,
                "hints_used": 0,
                "last_check_map": {c["id"]: False for c in inst["checks"]},
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

    def verify(self) -> dict[str, Any]:
        with self._lock:
            if not self.active:
                return {"ok": False, "error": "No hay ningún escenario en ejecución."}

            act = self.active
            inst = act["instance"]
            node_by_role = {n["role"]: n for n in act["nodes_runtime"]}

            passed_count = 0
            for chk in inst["checks"]:
                nr = node_by_role[chk["node"]]
                shell_bin = nr["shell"]
                rc, _out = _run_cmd(
                    [
                        "podman",
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

            total_checks = len(inst["checks"])
            all_passed = passed_count == total_checks

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

                # Persistir progreso
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
