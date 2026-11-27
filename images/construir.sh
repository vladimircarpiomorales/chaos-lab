#!/usr/bin/env bash
# Construye las imágenes propias de Chaos Lab (herramientas de serie en cada nodo).
# Uso: ./images/construir.sh            -> construye todas
#      ./images/construir.sh nginx      -> solo una
# Si no existen, Chaos Lab usa las imágenes oficiales (sin nano/vim/ss/dig).
set -euo pipefail
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
VERSION=1
for nombre in "${@:-debian nginx redis}"; do
    for n in $nombre; do
        echo "→ localhost/chaos-${n}:${VERSION}"
        podman build -t "localhost/chaos-${n}:${VERSION}" "${DIR}/${n}"
    done
done
