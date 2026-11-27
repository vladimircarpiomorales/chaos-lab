#!/usr/bin/env bash
# Solución e2e de lpic1-dpkg (reto r101-dpkg); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r101-dpkg "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r101-dpkg
apt-get update -qq && apt-get install -y -qq tree >/dev/null
dpkg -L tree > archivos-tree.txt
dpkg -S /usr/bin/ls > duenno.txt
chown -R alumno:alumno "$RETO"
SOL
