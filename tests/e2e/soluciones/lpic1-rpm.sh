#!/usr/bin/env bash
# Solución e2e de lpic1-rpm (reto r101-rpm); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r101-rpm "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r101-rpm
dnf install -y -q tree >/dev/null
rpm -qf /usr/bin/bash > duenno.txt
rpm -ql tree > archivos-tree.txt
chown -R alumno:alumno "$RETO"
SOL
