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
# ldap-srv y ldap-cli comparten una CA de laboratorio que se genera en cada construcción (en un directorio
# temporal, nunca en el repo): por eso se construyen siempre juntas, aunque se pida solo una.
construir_ldap() {
    local ctx; ctx="$(mktemp -d)"
    trap 'rm -rf "$ctx"' RETURN
    "${DIR}/ldap-pki.sh" "${ctx}/pki"
    cp -r "${DIR}/ldap-srv" "${DIR}/ldap-cli" "$ctx/"
    for n in ldap-srv ldap-cli; do
        echo "→ localhost/chaos-${n}:${VERSION}"
        "$RT" build -f "${DIR}/${n}/Containerfile" -t "localhost/chaos-${n}:${VERSION}" "$ctx"
    done
}
LDAP_HECHO=0
for nombre in "${@:-debian lpic-debian lpic-fedora rocky nginx redis ldap-srv redes}"; do
    for n in $nombre; do
        case "$n" in
            ldap-srv|ldap-cli|ldap)
                [ "$LDAP_HECHO" = 1 ] || construir_ldap
                LDAP_HECHO=1;;
            *)
                echo "→ localhost/chaos-${n}:${VERSION}"
                "$RT" build -f "${DIR}/${n}/Containerfile" -t "localhost/chaos-${n}:${VERSION}" "${DIR}/${n}";;
        esac
    done
done
