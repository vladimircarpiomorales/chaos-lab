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
    podman ps -aq --filter "name=^chaoslab-" 2>/dev/null | xargs -r podman rm -f >/dev/null 2>&1 || true
    podman network rm -f chaoslab-net >/dev/null 2>&1 || true
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
    # Primera vez: construir las imágenes propias (herramientas de serie, sin apt al desplegar). Necesita internet una vez.
    for img in debian rocky nginx redis; do
        if ! podman image exists "localhost/chaos-${img}:1" 2>/dev/null; then
            echo "🧱 Construyendo imagen chaos-${img} (solo la primera vez)..."
            "${RAIZ}/images/construir.sh" "$img" >> "$LOG_FILE" 2>&1 \
                || echo "⚠ No se pudo construir chaos-${img}: se usará la imagen oficial (ver ${LOG_FILE})"
        fi
    done
    setsid nohup env PYTHONPATH="$RAIZ" CHAOS_HOST="$HOST" CHAOS_PORT="$PUERTO" \
        python3 -m chaos_lab.server >> "$LOG_FILE" 2>&1 < /dev/null &
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
