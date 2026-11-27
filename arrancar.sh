#!/usr/bin/env bash
# Lanzador de Chaos Lab (Arena interactiva de incidentes Linux/Red sobre Podman).
# Uso:
#   ./arrancar.sh              -> Inicia en segundo plano (si no corre) y abre el navegador
#   ./arrancar.sh --no-abrir   -> Inicia sin abrir navegador
#   ./arrancar.sh --reiniciar  -> Reinicia el servidor
#   ./arrancar.sh --parar      -> Detiene servidor y limpia contenedores chaoslab-*
#   ./arrancar.sh --estado     -> Muestra estado actual
set -euo pipefail

RAIZ="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
# Configuración local opcional (no se sube): CHAOS_PORT, CHAOS_EXPORT_DIR, CHAOS_RUNTIME…
[ -f "${RAIZ}/.env" ] && set -a && . "${RAIZ}/.env" && set +a
# Motor de contenedores: CHAOS_RUNTIME=podman|docker, o el primero que haya (podman → docker)
RT="${CHAOS_RUNTIME:-}"
[ -z "$RT" ] && { command -v podman >/dev/null 2>&1 && RT=podman || RT=docker; }
export CHAOS_RUNTIME="$RT"
PUERTO="${CHAOS_PORT:-7820}"
HOST="${CHAOS_HOST:-127.0.0.1}"
URL="http://${HOST}:${PUERTO}/"
LOG_FILE="${RAIZ}/data/server.log"
mkdir -p "${RAIZ}/data"

vivo() {
    curl -sf --max-time 2 "${URL}api/health" >/dev/null 2>&1
}

parar() {
    curl -sf -X POST --max-time 4 "${URL}api/lab/stop" >/dev/null 2>&1 || true
    fuser -k "${PUERTO}/tcp" >/dev/null 2>&1 || pkill -f "chaos_lab\.server" 2>/dev/null || true
    "$RT" ps -aq --filter "name=^chaoslab-" 2>/dev/null | xargs -r "$RT" rm -f >/dev/null 2>&1 || true
    "$RT" network ls --format '{{.Name}}' 2>/dev/null | grep '^chaoslab-' | xargs -r "$RT" network rm >/dev/null 2>&1 || true
}

ACCION="${1:-}"
ABRIR=1
if [ "$ACCION" = "--no-abrir" ]; then
    ABRIR=0
elif [ "$ACCION" = "--parar" ] || [ "$ACCION" = "--stop" ]; then
    parar
    echo "⏹ Chaos Lab detenido y contenedores efímeros limpiados."
    exit 0
elif [ "$ACCION" = "--estado" ] || [ "$ACCION" = "--status" ]; then
    if vivo; then
        echo "🟢 Chaos Lab activo en ${URL}"
        curl -sf "${URL}api/health" | python3 -m json.tool
    else
        echo "⚪ Chaos Lab detenido."
    fi
    exit 0
elif [ "$ACCION" = "--reiniciar" ] || [ "$ACCION" = "-r" ]; then
    parar
    sleep 0.4
fi

if ! vivo; then
    cd "$RAIZ"
    # Python: .venv propio si existe; si no, el del sistema si ya tiene FastAPI; si no, crear .venv (una vez, necesita internet)
    PY="python3"
    if [ -x "${RAIZ}/.venv/bin/python" ]; then
        PY="${RAIZ}/.venv/bin/python"
    elif ! python3 -c "import fastapi, uvicorn, websockets" 2>/dev/null; then
        echo "🐍 Creando entorno Python en .venv (solo la primera vez)..."
        python3 -m venv "${RAIZ}/.venv" && "${RAIZ}/.venv/bin/pip" install -q -r "${RAIZ}/requirements.txt" \
            || { echo "❌ No se pudo preparar .venv. Instala python3-venv o: pip install -r requirements.txt"; exit 1; }
        PY="${RAIZ}/.venv/bin/python"
    fi
    # Primera vez: construir las imágenes propias (herramientas de serie, sin apt al desplegar). Necesita internet una vez.
    for img in debian rocky nginx redis lpic-debian lpic-fedora; do
        if ! "$RT" image inspect "localhost/chaos-${img}:1" >/dev/null 2>&1; then
            echo "🧱 Construyendo imagen chaos-${img} (solo la primera vez)..."
            "${RAIZ}/images/construir.sh" "$img" >> "$LOG_FILE" 2>&1 \
                || echo "⚠ No se pudo construir chaos-${img}: se usará la imagen oficial (ver ${LOG_FILE})"
        fi
    done
    setsid nohup env PYTHONPATH="$RAIZ" CHAOS_HOST="$HOST" CHAOS_PORT="$PUERTO" \
        "$PY" -m chaos_lab.server >> "$LOG_FILE" 2>&1 < /dev/null &
    for _ in $(seq 1 40); do
        vivo && break
        sleep 0.2
    done
fi

if vivo; then
    echo "⚡ Chaos Lab disponible en ${URL}"
    if [ "$ABRIR" -eq 1 ] && command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$URL" >/dev/null 2>&1 &
    fi
else
    echo "❌ No pudo arrancar Chaos Lab. Revisa ${LOG_FILE}" >&2
    exit 1
fi
