#!/usr/bin/env bash
# Solución e2e de lpic1-filtros (reto r101-filtros); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r101-filtros "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r101-filtros
cut -d, -f1 ventas.csv | sort -u > ciudades.txt
grep '^Madrid,' ventas.csv > madrid.txt
wc -l < ventas.csv > cuantas.txt
chown -R alumno:alumno "$RETO"
SOL
