#!/usr/bin/env bash
# Solución e2e de lpic1-vi (reto r101-vi); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r101-vi "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r101-vi
vi -e -s -c 'g/^depurar=/d' -c '%s/tienda/almacen/g' -c 'g/^puerto=/t.|s/puerto/puerto_admin/' -c 'normal ggO# editado con vi' -c 'normal Goactivo=si' -c 'wq' tienda.conf
chown -R alumno:alumno "$RETO"
SOL
