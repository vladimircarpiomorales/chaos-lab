#!/usr/bin/env bash
# Solución e2e de lpic1-enlaces (reto r101-enlaces); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r101-enlaces "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r101-enlaces
ln original.txt duro.txt
ln -s original.txt blando.txt
ln -s /etc/hostname atajos/conf
chown -R alumno:alumno "$RETO"
SOL
