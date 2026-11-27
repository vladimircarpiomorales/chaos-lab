#!/usr/bin/env bash
# Solución e2e de lpic1-cuenta-shadow (reto r102-cuenta-shadow); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-cuenta-shadow "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-cuenta-shadow
passwd -l lpi-shadow
chage -E -1 lpi-shadow
chown -R alumno:alumno "$RETO"
SOL
