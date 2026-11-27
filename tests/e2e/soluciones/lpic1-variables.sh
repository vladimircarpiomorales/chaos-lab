#!/usr/bin/env bash
# Solución e2e de lpic1-variables (reto r102-variables); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-variables "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-variables
echo 'export PRACTICA=lpi' >> /home/alumno/.bashrc
echo "alias ll='ls -l'" >> /home/alumno/.bashrc
echo "$PATH" > ruta.txt
chown -R alumno:alumno "$RETO"
SOL
