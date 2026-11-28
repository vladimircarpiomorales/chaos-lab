#!/usr/bin/env bash
# Prueba en seco de los escenarios del pack de redes (chaos_lab/packs/redes.json), SIN el servidor de Chaos Lab.
# Por cada escenario: redes manuales y contenedores propios (redseco-*, nunca chaoslab-*), con los mismos comandos
# que usa el motor (crear red, run, network connect, vaciado en Docker), se ejecutan los setup_sh de los nodos en
# orden y el check_script (bloques por nodo); el corrector debe empezar con algún ✘ y, tras la solución
# (tests/e2e/soluciones/<id>.sh), acabar todo en ✔. Borra lo que crea al terminar.
# Uso: tests/e2e/redes_seco.sh [id …] [-v]     (sin ids: todos los del pack; -v muestra la salida del corrector)
set -uo pipefail
AQUI="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"; REPO="$(cd "$AQUI/../.." && pwd)"
PY="${PY:-$HOME/MiPanelControl/venv/bin/python}"; [ -x "$PY" ] || PY=python3
RT="${CHAOS_RUNTIME:-}"; [ -z "$RT" ] && { command -v podman >/dev/null 2>&1 && RT=podman || RT=docker; }
export RT CHAOS_RUNTIME="$RT"
VERBOSE=""; IDS=()
for a in "$@"; do [ "$a" = "-v" ] && VERBOSE=1 || IDS+=("$a"); done
if [ ${#IDS[@]} -eq 0 ]; then
    mapfile -t IDS < <(cd "$REPO" && "$PY" -I -c "import json;[print(i['id']) for i in json.load(open('chaos_lab/packs/redes.json'))]")
fi
TMP="$(mktemp -d)"; ROLES=()
limpiar() {
    "$RT" ps -aq --filter "name=^redseco-" 2>/dev/null | xargs -r "$RT" rm -f >/dev/null 2>&1
    "$RT" network ls --format '{{.Name}}' 2>/dev/null | grep '^redseco-' | xargs -r "$RT" network rm -f >/dev/null 2>&1
}
trap 'limpiar; rm -rf "$TMP"' EXIT

# Vuelca, desde el motor, redes, run/connect/setup de cada nodo, el entorno de IPs y los bloques del corrector
( cd "$REPO" && "$PY" -I - "$TMP" "${IDS[@]}" <<'PY'
import sys, types, os, re
sys.path.insert(0, ".")
try:
    import fastapi  # noqa: F401
except ImportError:
    f = types.ModuleType("fastapi"); f.WebSocket = f.WebSocketDisconnect = object; sys.modules["fastapi"] = f
from chaos_lab import engine
from chaos_lab.scenarios import instantiate_scenario
tmp, ids = sys.argv[1], sys.argv[2:]
fix = lambda s: s.replace(engine.NETWORK_PREFIX, "redseco-")
def w(path, cmd):  # una orden = argumentos separados por NUL (sin el motor delante: lo pone el .sh)
    open(path, "w").write("\0".join(cmd))
for sid in ids:
    inst = instantiate_scenario(sid, 1)
    d = f"{tmp}/{sid}"; os.makedirs(d)
    manual = engine._manual_networks(inst)
    all_nets, by_role = engine._plan_networks(inst)
    all_nets = [fix(n) for n in all_nets]
    for i, net in enumerate(all_nets):
        w(f"{d}/net-{i:02d}.txt", engine._network_create_cmd(net, manual, i)[1:])
    roles = [n["role"] for n in inst["nodes"]]
    open(d + "/roles", "w").write("\n".join(roles) + "\n")
    env = []
    for n in inst["nodes"]:
        r = n["role"]; nets = [fix(x) for x in by_role[r]]; cname = "redseco-" + r
        open(f"{d}/setup-{r}.sh", "w").write(f"source /etc/chaos_nodes.env 2>/dev/null || . /etc/chaos_nodes.env; {n['setup_sh']}")
        w(f"{d}/run-{r}.txt", engine._build_run_cmd(n, cname, engine.IMAGE_CANDIDATES[n["distro"]][0], nets)[1:])
        for j, c in enumerate(engine._connect_cmds(r, cname, nets)):
            w(f"{d}/connect-{r}-{j:02d}.txt", c[1:])
        prep = engine._manual_prep_cmd(cname, nets) if manual else None
        if prep:
            w(f"{d}/prep-{r}.txt", prep[1:])
        open(f"{d}/timeout-{r}", "w").write(str(n.get("setup_timeout", 25)))
        ips = engine._design_ips(n, [engine.NETWORK_PREFIX + s for s in (n.get("networks") or inst["networks"][:1])])
        first = (n.get("networks") or inst["networks"][:1] or [None])[0]
        base = "IP_" + engine._env_name(r)
        env.append(f"{base}={ips.get(first, '127.0.0.1')}")
        env += [f"{base}_{engine._env_name(s)}={ip}" for s, ip in ips.items()]
    open(d + "/env", "w").write("\n".join(env) + "\n")
    blocks = engine._check_blocks(inst["check_script"])
    for i, b in enumerate(blocks):
        open(f"{d}/check-{i:02d}.sh", "w").write(engine._build_check_script(b))
        open(f"{d}/check-{i:02d}.node", "w").write(b["node"])
    esperadas = sum(len(re.findall(r"^\s*(?:comprueba|ok|mal)\b", b["script"], re.M)) for b in blocks)
    open(f"{d}/esperadas", "w").write(str(esperadas))
PY
) || { echo "✘ no se pudieron construir los escenarios"; exit 2; }

corrector() {  # $1 = id ; une las sondas de todos los bloques, en orden
    local d="$TMP/$1" f
    for f in "$d"/check-*.sh; do
        timeout 60 "$RT" exec -i --user root "redseco-$(cat "${f%.sh}.node")" bash -s < "$f" 2>&1
    done
}
rc_total=0
for ID in "${IDS[@]}"; do
    d="$TMP/$ID"; limpiar; ok=1
    for f in "$d"/net-*.txt; do
        mapfile -d '' ARGS < "$f"
        "$RT" "${ARGS[@]}" >/dev/null || { echo "✘ $ID: no se crea la red (${ARGS[*]})"; ok=0; break; }
    done
    [ $ok = 1 ] || { rc_total=1; continue; }
    mapfile -t ROLES < "$d/roles"
    for r in "${ROLES[@]}"; do
        mapfile -d '' ARGS < "$d/run-$r.txt"
        "$RT" "${ARGS[@]}" >/dev/null || { echo "✘ $ID: no arranca $r"; ok=0; break; }
        for f in "$d"/connect-$r-*.txt; do
            [ -e "$f" ] || continue
            mapfile -d '' ARGS < "$f"
            "$RT" "${ARGS[@]}" >/dev/null || { echo "✘ $ID: $r no se conecta a su red"; ok=0; break 2; }
        done
        if [ -e "$d/prep-$r.txt" ]; then mapfile -d '' ARGS < "$d/prep-$r.txt"; "$RT" "${ARGS[@]}" >/dev/null || { echo "✘ $ID: no se vacía la red de $r"; ok=0; break; }; fi
    done
    [ $ok = 1 ] || { rc_total=1; continue; }
    for r in "${ROLES[@]}"; do
        "$RT" exec -i "redseco-$r" sh -c 'cat > /etc/chaos_nodes.env' < "$d/env"
        timeout "$(cat "$d/timeout-$r")" "$RT" exec "redseco-$r" /bin/bash -c "$(cat "$d/setup-$r.sh")" >"$d/setup.log" 2>&1 \
            || { echo "✘ $ID: el setup de $r falló"; tail -n 10 "$d/setup.log"; ok=0; break; }
    done
    [ $ok = 1 ] || { rc_total=1; continue; }
    ANTES="$(corrector "$ID")"; a_mal=$(grep -c '^✘' <<<"$ANTES"); a_bien=$(grep -c '^✔' <<<"$ANTES")
    [ -n "$VERBOSE" ] && { echo "--- antes"; echo "$ANTES"; }
    for r in "${ROLES[@]}"; do
        export "C_$(tr 'a-z-' 'A-Z_' <<<"$r")=redseco-$r"
        export "IP_$(tr 'a-z-' 'A-Z_' <<<"$r")=$(grep "^IP_$(tr 'a-z-' 'A-Z_' <<<"$r")=" "$d/env" | cut -d= -f2)"
    done
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
