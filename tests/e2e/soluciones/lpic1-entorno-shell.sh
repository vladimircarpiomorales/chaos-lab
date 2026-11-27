#!/usr/bin/env bash
# Solución e2e de lpic1-entorno-shell (reto r101-entorno-shell); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r101-entorno-shell "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r101-entorno-shell
CURSO="LPIC 101"
export CURSO
bash -c 'printf "%s\n" "$CURSO"' > hijo.txt
touch "notas de clase.txt"
chown -R alumno:alumno "$RETO"
SOL
