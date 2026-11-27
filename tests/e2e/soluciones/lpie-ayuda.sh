#!/usr/bin/env bash
# Solución e2e de lpie-ayuda (reto r010-ayuda); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r010-ayuda "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r010-ayuda
type cd > tipo-cd.txt
type mkdir > tipo-mkdir.txt
updatedb
locate tesoro-perdido > ruta.txt
chown -R alumno:alumno "$RETO"
SOL
