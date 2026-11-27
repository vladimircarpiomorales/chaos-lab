#!/usr/bin/env bash
# Solución e2e de lpic1-redirecciones (reto r101-redirecciones); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r101-redirecciones "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r101-redirecciones
./genera.sh > salida.txt 2> errores.txt
date >> salida.txt
cat salida.txt | tr a-z A-Z > mayus.txt
chown -R alumno:alumno "$RETO"
SOL
