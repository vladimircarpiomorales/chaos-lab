#!/usr/bin/env bash
# Prueba en seco de los retos del pack LPIC-2 LDAP (chaos_lab/packs/lpic2_ldap.json), SIN el servidor de Chaos Lab.
# Por cada escenario: red y 2 contenedores propios (ldapseco-*, nunca chaoslab-*), se ejecutan los setup_sh de los
# nodos en orden y el check_script (lista de bloques, uno por nodo) tal como los construye el motor; el corrector debe
# empezar con algún ✘, tras la solución (tests/e2e/soluciones/<id>.sh) todo ✔. Borra lo que crea al terminar.
# Uso: tests/e2e/ldap_seco.sh [id …] [-v]     (sin ids: todos los del pack; -v muestra la salida del corrector)
set -uo pipefail
AQUI="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"; REPO="$(cd "$AQUI/../.." && pwd)"
PY="${PY:-$HOME/MiPanelControl/venv/bin/python}"; [ -x "$PY" ] || PY=python3
RT="${CHAOS_RUNTIME:-}"; [ -z "$RT" ] && { command -v podman >/dev/null 2>&1 && RT=podman || RT=docker; }
export RT
VERBOSE=""; IDS=()
for a in "$@"; do [ "$a" = "-v" ] && VERBOSE=1 || IDS+=("$a"); done
if [ ${#IDS[@]} -eq 0 ]; then
    mapfile -t IDS < <(cd "$REPO" && "$PY" -I -c "import json;[print(i['id']) for i in json.load(open('chaos_lab/packs/lpic2_ldap.json'))]")
fi
NET="ldapseco-net"; TMP="$(mktemp -d)"; ROLES=()
limpiar() { for r in ldap-srv ldap-cli; do "$RT" rm -f "ldapseco-$r" >/dev/null 2>&1; done; "$RT" network rm -f "$NET" >/dev/null 2>&1; }
trap 'limpiar; rm -rf "$TMP"' EXIT

# Vuelca, desde el builder del motor, run/setup de cada nodo y los bloques del corrector
( cd "$REPO" && "$PY" -I - "$TMP" "$NET" "${IDS[@]}" <<'PY'
import sys, types, json
sys.path.insert(0, ".")
try:
    import fastapi  # noqa: F401
except ImportError:
    f = types.ModuleType("fastapi"); f.WebSocket = f.WebSocketDisconnect = object; sys.modules["fastapi"] = f
from chaos_lab import engine
from chaos_lab.scenarios import instantiate_scenario
tmp, net, ids = sys.argv[1], sys.argv[2], sys.argv[3:]
for sid in ids:
    inst = instantiate_scenario(sid, 1)
    d = f"{tmp}/{sid}"; import os; os.makedirs(d)
    roles = [n["role"] for n in inst["nodes"]]
    open(d + "/roles", "w").write("\n".join(roles) + "\n")
    for n in inst["nodes"]:
        open(f"{d}/setup-{n['role']}.sh", "w").write(f"source /etc/chaos_nodes.env 2>/dev/null || . /etc/chaos_nodes.env; {n['setup_sh']}")
        cmd = engine._build_run_cmd(n, "ldapseco-" + n["role"], engine.IMAGE_CANDIDATES[n["distro"]][0], [net])
        open(f"{d}/run-{n['role']}.txt", "w").write("\0".join(cmd[1:]))
        open(f"{d}/timeout-{n['role']}", "w").write(str(n["setup_timeout"]))
    for i, b in enumerate(engine._check_blocks(inst["check_script"])):
        open(f"{d}/check-{i:02d}.sh", "w").write(engine._build_check_script(b))
        open(f"{d}/check-{i:02d}.node", "w").write(b["node"])
    # Sondas que debe dar el corrector (líneas comprueba/ok/mal): si salen menos, una orden se ha comido el resto
    import re
    esperadas = sum(len(re.findall(r"^\s*(?:comprueba|ok|mal)\b", b["script"], re.M)) for b in engine._check_blocks(inst["check_script"]))
    open(f"{d}/esperadas", "w").write(str(esperadas))
PY
) || { echo "✘ no se pudieron construir los escenarios"; exit 2; }

corrector() {  # $1 = id ; une las sondas de todos los bloques, en orden
    local d="$TMP/$1" f
    for f in "$d"/check-*.sh; do
        timeout 60 "$RT" exec -i --user root "ldapseco-$(cat "${f%.sh}.node")" bash -s < "$f" 2>&1
    done
}
rc_total=0
for ID in "${IDS[@]}"; do
    d="$TMP/$ID"; limpiar
    "$RT" network create "$NET" >/dev/null || { echo "✘ $ID: no se crea la red"; rc_total=1; continue; }
    ok=1; : > "$d/env"
    mapfile -t ROLES < "$d/roles"
    for r in "${ROLES[@]}"; do
        mapfile -d '' RUNARGS < "$d/run-$r.txt"
        "$RT" "${RUNARGS[@]}" >/dev/null || { echo "✘ $ID: no arranca $r"; ok=0; break; }
        echo "IP_$(tr 'a-z-' 'A-Z_' <<<"$r")=$("$RT" inspect -f "{{(index .NetworkSettings.Networks \"$NET\").IPAddress}}" "ldapseco-$r")" >> "$d/env"
    done
    [ $ok = 1 ] || { rc_total=1; continue; }
    for r in "${ROLES[@]}"; do
        "$RT" exec -i "ldapseco-$r" sh -c 'cat > /etc/chaos_nodes.env' < "$d/env"
        timeout "$(cat "$d/timeout-$r")" "$RT" exec "ldapseco-$r" /bin/bash -c "$(cat "$d/setup-$r.sh")" >"$d/setup.log" 2>&1 \
            || { echo "✘ $ID: el setup de $r falló"; tail -n 10 "$d/setup.log"; ok=0; break; }
    done
    [ $ok = 1 ] || { rc_total=1; continue; }
    ANTES="$(corrector "$ID")"; a_mal=$(grep -c '^✘' <<<"$ANTES"); a_bien=$(grep -c '^✔' <<<"$ANTES")
    [ -n "$VERBOSE" ] && { echo "--- antes"; echo "$ANTES"; }
    for r in "${ROLES[@]}"; do export "C_$(tr 'a-z-' 'A-Z_' <<<"$r")=ldapseco-$r"; done
    bash "$AQUI/soluciones/$ID.sh" >"$d/sol.log" 2>&1 || echo "  (la solución devolvió error)"
    sleep 1
    DESPUES="$(corrector "$ID")"; d_mal=$(grep -c '^✘' <<<"$DESPUES"); d_bien=$(grep -c '^✔' <<<"$DESPUES")
    [ -n "$VERBOSE" ] && { echo "--- después"; echo "$DESPUES"; }
    esp=$(cat "$d/esperadas")
    if [ "$a_mal" -ge 1 ] && [ "$d_mal" -eq 0 ] && [ "$d_bien" -eq "$esp" ] && [ $((a_mal + a_bien)) -eq "$esp" ]; then
        echo "OK    $ID  antes ✘$a_mal/✔$a_bien → después ✔$d_bien"
    else
        echo "FALLA $ID  antes ✘$a_mal/✔$a_bien → después ✔$d_bien/✘$d_mal (esperadas $esp)"
        grep '^✘' <<<"$DESPUES"; tail -n 12 "$d/sol.log"; rc_total=1
    fi
done
exit $rc_total
