#!/usr/bin/env bash
# Prueba en seco de un reto del pack LPIC-1 102-500, SIN el servidor de Chaos Lab.
# Arranca un contenedor propio (lpicseco-<x>, nunca chaoslab-*) con la imagen del pack, ejecuta el setup_sh y el
# check_script tal como los construye el motor, comprueba que el corrector empieza con algún ✘, aplica la
# solución (tests/e2e/soluciones/<id>.sh) y comprueba que acaba todo en ✔. Borra el contenedor al terminar.
# Uso: tests/e2e/lpic_seco.sh lpic1-usuarios [-v]      (-v: muestra la salida del corrector)
set -uo pipefail
ID="${1:?uso: lpic_seco.sh <id lpic1-…> [-v]}"; VERBOSE="${2:-}"
AQUI="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"; REPO="$(cd "$AQUI/../.." && pwd)"
PY="${PY:-$HOME/MiPanelControl/venv/bin/python}"; [ -x "$PY" ] || PY=python3
RT="${CHAOS_RUNTIME:-}"; [ -z "$RT" ] && { command -v podman >/dev/null 2>&1 && RT=podman || RT=docker; }
export RT
C="lpicseco-${ID#lpic1-}"
TMP="$(mktemp -d)"
trap '"$RT" rm -f "$C" >/dev/null 2>&1; rm -rf "$TMP"' EXIT
"$RT" rm -f "$C" >/dev/null 2>&1

# Lo que ejecutaría el motor (se saca del builder, no se reescribe a mano)
( cd "$REPO" && "$PY" -I - "$ID" "$TMP" <<'PY'
import random, sys, types
sys.path.insert(0, ".")
try:
    import fastapi  # noqa: F401
except ImportError:
    f = types.ModuleType("fastapi"); f.WebSocket = f.WebSocketDisconnect = object; sys.modules["fastapi"] = f
from chaos_lab import engine
from chaos_lab.scenarios import instantiate_scenario
inst = instantiate_scenario(sys.argv[1], 1)
n = inst["nodes"][0]
open(sys.argv[2] + "/setup.sh", "w").write(f"source /etc/chaos_nodes.env 2>/dev/null || . /etc/chaos_nodes.env; {n['setup_sh']}")
open(sys.argv[2] + "/check.sh", "w").write(engine._build_check_script(inst["check_script"]))
cmd = engine._build_run_cmd(n, "NOMBRE", engine.IMAGE_CANDIDATES[n["distro"]][0], [])
open(sys.argv[2] + "/run.txt", "w").write("\0".join(cmd[1:]))
print(n["setup_timeout"], file=open(sys.argv[2] + "/timeout", "w"))
PY
) || { echo "✘ $ID: no se pudo construir el escenario"; exit 2; }

mapfile -d '' RUNARGS < "$TMP/run.txt"
RUNARGS=("${RUNARGS[@]/NOMBRE/$C}")
"$RT" "${RUNARGS[@]}" >/dev/null || { echo "✘ $ID: no arranca el contenedor"; exit 2; }
"$RT" exec "$C" sh -c "printf 'IP_LPIC=127.0.0.1\n' > /etc/chaos_nodes.env"

timeout "$(cat "$TMP/timeout")" "$RT" exec "$C" /bin/bash -c "$(cat "$TMP/setup.sh")" >"$TMP/setup.log" 2>&1
rc=$?
[ $rc -eq 0 ] || { echo "✘ $ID: el setup devolvió $rc"; tail -n 15 "$TMP/setup.log"; exit 2; }

corrector() { timeout 60 "$RT" exec -i --user root "$C" bash -s < "$TMP/check.sh" 2>&1; }
cuenta() { grep -c "^$1" <<<"$2"; }
ANTES="$(corrector)"
a_mal=$(cuenta ✘ "$ANTES"); a_bien=$(cuenta ✔ "$ANTES")
[ -n "$VERBOSE" ] && { echo "--- antes"; echo "$ANTES"; }

C_LPIC="$C" bash "$AQUI/soluciones/$ID.sh" >"$TMP/sol.log" 2>&1 || echo "  (la solución devolvió error)"
sleep 1
DESPUES="$(corrector)"
d_mal=$(cuenta ✘ "$DESPUES"); d_bien=$(cuenta ✔ "$DESPUES")
[ -n "$VERBOSE" ] && { echo "--- después"; echo "$DESPUES"; }

if [ "$a_mal" -ge 1 ] && [ "$d_mal" -eq 0 ] && [ "$d_bien" -ge 1 ]; then
    echo "OK    $ID  antes ✘$a_mal/✔$a_bien → después ✔$d_bien"
else
    echo "FALLA $ID  antes ✘$a_mal/✔$a_bien → después ✔$d_bien/✘$d_mal"
    echo "--- sonda(s) en rojo después:"; grep '^✘' <<<"$DESPUES"
    echo "--- salida de la solución:"; tail -n 12 "$TMP/sol.log"
    exit 1
fi
