#!/usr/bin/env bash
# Prueba real de un escenario: lanza, verifica (debe empezar en rojo), aplica la solución y verifica (debe acabar en verde).
# Uso: tests/e2e/probar.sh <scenario_id> <script-solucion.sh>
# El script de solución recibe el entorno: C_<ROL>=nombre del contenedor, IP_<ROL>=IP.
set -uo pipefail
URL="${CHAOS_URL:-http://127.0.0.1:7820}"
SID="$1"; SOL="$2"
# Motor de contenedores: CHAOS_RUNTIME=podman|docker, o el primero que haya (podman → docker)
RT="${CHAOS_RUNTIME:-}"
[ -z "$RT" ] && { command -v podman >/dev/null 2>&1 && RT=podman || RT=docker; }
export RT
api() { curl -s -X POST -H 'Content-Type: application/json' -H "Origin: $URL" --max-time 400 "$URL$1" ${2:+-d "$2"}; }
estado() { api /api/lab/verify | python3 -c "import json,sys; a=json.load(sys.stdin); a=a.get('active',a); print(a.get('scenario_id'), ' '.join(('✓' if c['passed'] else '✗')+c['id'] for c in a.get('checks',[])))"; }
res=$(api /api/lab/launch "{\"scenario_id\":\"$SID\",\"record\":false}")  # record=false: no ensucia el progreso del jugador
echo "$res" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('ok'), d.get('error'); [print('  nodo', n['role'], n['image']) for n in d['active']['nodes']]" || exit 1
eval "$(echo "$res" | python3 -c "
import json,sys
for n in json.load(sys.stdin)['active']['nodes']:
    r=n['role'].upper().replace('-','_'); print(f\"export C_{r}={n['container']} IP_{r}={n['ip']}\")")"
echo "  antes:   $(estado)"
bash "$SOL" >"${TMPDIR:-/tmp}/chaos-e2e-sol.log" 2>&1 || echo "  (la solución devolvió error, ver ${TMPDIR:-/tmp}/chaos-e2e-sol.log)"
sleep "${ESPERA:-1}"
echo "  después: $(estado)"
