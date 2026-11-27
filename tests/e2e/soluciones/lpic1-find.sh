#!/usr/bin/env bash
# Solución e2e de lpic1-find (reto r101-find); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r101-find "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r101-find
find almacen -type f -size +2M > grandes.txt
find almacen -type f -mtime +365 > viejos.txt
find almacen -type f -perm -o+w -exec chmod o-w {} \;
find almacen -type d -empty -delete
chown -R alumno:alumno "$RETO"
SOL
