#!/usr/bin/env bash
# Construye las imágenes propias de Chaos Lab (herramientas de serie en cada nodo).
# Uso: ./images/construir.sh            -> construye todas
#      ./images/construir.sh nginx      -> solo una
# Si no existen, Chaos Lab usa las imágenes oficiales (sin nano/vim/ss/dig).
set -euo pipefail
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
VERSION=1
# Motor de contenedores: CHAOS_RUNTIME=podman|docker, o el primero que haya (podman → docker)
RT="${CHAOS_RUNTIME:-}"
[ -z "$RT" ] && { command -v podman >/dev/null 2>&1 && RT=podman || RT=docker; }
for nombre in "${@:-debian rocky nginx redis}"; do
    for n in $nombre; do
        echo "→ localhost/chaos-${n}:${VERSION}"
        "$RT" build -f "${DIR}/${n}/Containerfile" -t "localhost/chaos-${n}:${VERSION}" "${DIR}/${n}"
    done
done
