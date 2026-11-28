"""
Copiloto SRE Socrático opcional sobre Ollama local + Generador de informes Post-Mortem.
Funciona 100% offline; si Ollama está apagado ofrece análisis heurístico local.
"""

from __future__ import annotations

import datetime
import json
import subprocess
import urllib.error
import urllib.request
from typing import Any
from .runtime import RUNTIME

OLLAMA_BASE = "http://127.0.0.1:11434"
PREFERRED_MODELS = [
    "qwen3.5",
    "qwen2.5-coder",
    "qwen3",
    "deepseek-coder-v2",
    "qwen2.5",
    "llama3.1",
]


def detect_ollama() -> dict[str, Any]:
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        models = [m.get("name", "") for m in payload.get("models", []) if m.get("name")]
        chosen = None
        for pref in PREFERRED_MODELS:
            for m in models:
                if m.startswith(pref):
                    chosen = m
                    break
            if chosen:
                break
        if not chosen and models:
            chosen = models[0]
        return {"online": True, "model": chosen, "models": models}
    except Exception:
        return {"online": False, "model": None, "models": []}


def collect_timeline(active: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Correlación SecOps para el Modo Guardia: ejecuta las `signals` del escenario sec-* en los
    nodos reales y devuelve una línea de tiempo ordenada de señales (hora local HH:MM:SS).
    No incluye la solución: las IPs salen enmascaradas y solo hay observaciones.
    """
    inst = active["instance"]
    by_role = {n["role"]: n for n in active["nodes_runtime"]}
    events: list[dict[str, Any]] = []
    en_signals = (((inst.get("i18n") or {}).get("en") or {}).get("signals")) or []
    for i, sig in enumerate(inst.get("signals") or []):
        node = by_role.get(sig["node"])
        if not node:
            continue
        try:
            proc = subprocess.run(
                [RUNTIME, "exec", node["container"], node["shell"], "-c", sig["cmd"]],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except Exception:
            continue
        lines = [ln for ln in (proc.stdout or "").strip().splitlines() if ln.strip()]
        if proc.returncode != 0 or not lines:
            continue
        parts = lines[-1].split("|")
        try:
            epoch = int(parts[0])
            text = sig["text"].format(*parts)
        except (ValueError, IndexError):
            continue
        try:  # misma plantilla en inglés (i18n.en.signals[i]); si falta o falla, la UI usa el español
            text_en = en_signals[i].format(*parts) if i < len(en_signals) and isinstance(en_signals[i], str) else ""
        except (ValueError, IndexError):
            text_en = ""
        events.append(
            {
                "epoch": epoch,
                "t": datetime.datetime.fromtimestamp(epoch).strftime("%H:%M:%S"),
                "node": sig["node"],
                "sev": sig.get("sev", "info"),
                "text": text,
                "text_en": text_en,
            }
        )
    if not events:
        return []
    events.sort(key=lambda e: e["epoch"])
    now = datetime.datetime.now()
    events.append(
        {
            "epoch": int(now.timestamp()),
            "t": now.strftime("%H:%M:%S"),
            "node": "pagerduty",
            "sev": "crit",
            "text": "PagerDuty dispara la alerta de guardia: varias señales correlacionadas apuntan a un incidente de seguridad",
            "text_en": "PagerDuty fires the on-call alert: several correlated signals point to a security incident",
        }
    )
    return events


def _en(inst: dict[str, Any]) -> dict[str, Any]:
    en = (inst.get("i18n") or {}).get("en")
    return en if isinstance(en, dict) else {}


def _tr(inst: dict[str, Any], field: str, lang: str) -> Any:
    """Campo del escenario en el idioma pedido, con respaldo al español."""
    if lang == "en":
        v = _en(inst).get(field)
        if (isinstance(v, str) and v.strip()) or (isinstance(v, list) and v):
            return v
    return inst.get(field)


def ask_socratic_mentor(active: dict[str, Any], user_question: str = "", lang: str = "es") -> dict[str, Any]:
    en = lang == "en"
    inst = active["instance"]
    blind = active["blind_mode"] and not active["solved"]
    transcript = active.get("transcript", [])[-15:]
    cmds_txt = (
        "\n".join(f"- [{t['node']}] {t['cmd']}" for t in transcript)
        if transcript
        else ("(no commands recorded in the console yet)" if en else "(aún no se registraron comandos en la consola)")
    )

    ollama = detect_ollama()
    if ollama["online"] and ollama["model"]:
        symptom = _tr(inst, "blind_alert", lang) if blind else _tr(inst, "briefing", lang)
        if en:
            prompt = (
                "You are a Principal SRE helping a teammate during an on-call shift.\n"
                "STRICT RULES:\n"
                "1. Answer in English in at most 3 direct sentences.\n"
                "2. Suggest which diagnostic command to run or which hypothesis to test, based on what they already did.\n"
                "3. NEVER give the final command that fixes the problem or reveal tokens/passwords.\n\n"
                f"INCIDENT: {symptom}\n"
                f"NODES: {', '.join(n['role'] for n in active['nodes_runtime'])}\n"
                f"COMMANDS TRIED:\n{cmds_txt}\n"
            )
        else:
            prompt = (
                "Eres un Ingeniero Principal SRE ayudando a un compañero durante una guardia.\n"
                "REGLAS ESTRICTAS:\n"
                "1. Responde en español en máximo 3 frases directas.\n"
                "2. Orienta qué comando de diagnóstico ejecutar o qué hipótesis comprobar según lo que ya hizo.\n"
                "3. PROHIBIDO dar el comando final que repara el problema o revelar tokens/contraseñas.\n\n"
                f"INCIDENTE: {symptom}\n"
                f"NODOS: {', '.join(n['role'] for n in active['nodes_runtime'])}\n"
                f"COMANDOS PROBADOS:\n{cmds_txt}\n"
            )
        if user_question.strip():
            prompt += f"\n{'OPERATOR QUESTION' if en else 'DUDA DEL OPERADOR'}: {user_question.strip()}\n"

        body = json.dumps(
            {
                "model": ollama["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
            }
        ).encode("utf-8")

        try:
            req = urllib.request.Request(
                f"{OLLAMA_BASE}/api/chat",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                res = json.loads(resp.read().decode("utf-8"))
            answer = (res.get("message", {}).get("content") or "").strip()
            if answer:
                return {
                    "ok": True,
                    "source": f"Ollama ({ollama['model']})",
                    "advice": answer,
                }
        except Exception:
            pass

    # Fallback heurístico inteligente cuando Ollama está apagado
    tried_str = " ".join(t["cmd"] for t in transcript)
    suggestions = []
    if "ss " not in tried_str and "netstat" not in tried_str:
        suggestions.append("Check listening sockets and ports with `ss -tulpn`." if en else "Inspecciona sockets y puertos a la escucha con `ss -tulpn`.")
    if "ps " not in tried_str:
        suggestions.append("Look at the running processes with `ps aux`." if en else "Revisa los procesos en ejecución con `ps aux`.")
    if len(active["nodes_runtime"]) > 1 and "ip " not in tried_str:
        suggestions.append(
            "Check IP addresses, routes (`ip a`, `ip route`) and firewall rules (`nft list ruleset` or `iptables -S`) on each node."
            if en else
            "Verifica direcciones IP, rutas (`ip a`, `ip route`) y reglas de firewall (`nft list ruleset` o `iptables -S`) en cada nodo."
        )
    if not suggestions:
        suggestions.append(
            "You already looked at processes and the network: review recently changed config files (`/etc`, `/opt`, `/srv`), permissions/ACLs (`getfacl`, `ls -la`) or scheduled jobs (`/etc/cron.d`)."
            if en else
            "Ya inspeccionaste procesos y red: revisa archivos de configuración recientes (`/etc`, `/opt`, `/srv`), permisos/ACLs (`getfacl`, `ls -la`) o tareas programadas (`/etc/cron.d`)."
        )

    return {
        "ok": True,
        "source": "Local SRE heuristics (Ollama off)" if en else "Heurística SRE Local (Ollama apagado)",
        "advice": " ".join(suggestions[:2]),
    }


def build_postmortem_markdown(active: dict[str, Any], lang: str = "es") -> str:
    inst = active["instance"]
    en = lang == "en"
    T = (lambda e, s: e) if en else (lambda e, s: s)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    status_str = T("RESOLVED", "RESUELTO") if active["solved"] else T("UNDER INVESTIGATION", "EN INVESTIGACIÓN")
    elapsed = active["solved_elapsed_s"] if active["solved"] else int(datetime.datetime.now().timestamp() - active["started_at"])
    mins, secs = divmod(max(0, elapsed), 60)

    nodes_md = "\n".join(
        f"- **`{n['role']}`** (`{n['image']}` · IP `{n['ip']}`)"
        for n in active["nodes_runtime"]
    )
    labels_en = _en(inst).get("checks") if en else None
    def _label(i: int, c: dict[str, Any]) -> str:
        if isinstance(labels_en, list) and i < len(labels_en) and isinstance(labels_en[i], str) and labels_en[i].strip():
            return labels_en[i]
        return c["label"]
    checks_md = "\n".join(
        f"- [{'x' if active['last_check_map'].get(c['id']) else ' '}] **{c['node']}**: {_label(i, c)}"
        for i, c in enumerate(inst.get("checks", []))
    )
    transcript = active.get("transcript", [])
    if transcript:
        timeline_md = "\n".join(
            f"- `+{t['ts']:03d}s` **[{t['node']}]** `{t['cmd']}`"
            for t in transcript[-30:]
        )
    else:
        timeline_md = T("- *(No commands recorded)*", "- *(Sin comandos registrados)*")

    tl = active.get("timeline") or []
    if tl:
        icons = {"crit": "🔴", "warn": "🟠", "info": "🔵"}
        signals_md = "\n".join(
            f"- `{e['t']}` {icons.get(e['sev'], '•')} **[{e['node']}]** {(e.get('text_en') if en else '') or e['text']}" for e in tl
        )
        signals_section = f"""
## 1b. {T("Timeline of Correlated Signals (on-call alert)", "Línea de Tiempo de Señales Correlacionadas (alerta de guardia)")}
{signals_md}
"""
    else:
        signals_section = ""

    root_cause = (
        _tr(inst, "solution_summary", lang)
        if active["solved"]
        else T("*(Pass all validation checks to unlock the official root-cause analysis)*",
               "*(Completa todos los checks de validación para desbloquear el análisis oficial de causa raíz)*")
    )

    return f"""# {T("SRE Post-Mortem", "Post-Mortem SRE")}: {_tr(inst, "title", lang)}

- **{T("Date", "Fecha")}:** {now_str}
- **{T("Scenario ID", "ID Escenario")}:** `{inst['id']}` ({T("mutation seed", "Semilla de mutación")} `{inst['seed']}`)
- **{T("Category / Level", "Categoría / Nivel")}:** {inst['category']} · {inst['difficulty']}
- **{T("3:00 AM On-Call Mode", "Modo Guardia 3:00 AM")}:** {T("Yes", "Sí") if active["blind_mode"] else "No"}
- **{T("Status", "Estado")}:** **{status_str}** · {T("Time", "Tiempo")} `{mins}m {secs:02d}s` · {T("Rank", "Rango")} `{active.get('rank') or '-'}` · {T("Hints used", "Pistas usadas")} `{active['hints_used']}/{len(inst['hints'])}`

## 1. {T("Reported Symptom", "Síntoma Reportado")}
> {_tr(inst, "briefing", lang)}

{signals_section}
## 2. {T("Affected Topology", "Topología Afectada")}
{nodes_md}

## 3. {T("Service Checks (SLO)", "Verificaciones de Servicio (SLO Checks)")}
{checks_md}

## 4. {T("Command Timeline", "Cronología de Comandos Ejecutados")}
{timeline_md}

## 5. {T("Root Cause and Resolution", "Causa Raíz y Resolución")}
{root_cause}
"""
