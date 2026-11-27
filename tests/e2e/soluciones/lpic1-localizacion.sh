#!/usr/bin/env bash
# Solución e2e de lpic1-localizacion (reto r102-localizacion); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-localizacion "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-localizacion
LC_ALL=C date -d "$(cat fecha.txt)" +%B > mes.txt
LC_ALL=C.UTF-8 locale charmap > codificacion.txt
chown -R alumno:alumno "$RETO"
SOL
