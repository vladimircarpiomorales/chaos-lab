#!/usr/bin/env bash
# Solución e2e de lpic1-limites (reto r102-limites); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-limites "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-limites
cat > /etc/security/limits.d/90-alumnos.conf <<'FIN'
@alumnos   soft   memlock   2048
@alumnos   hard   memlock   4096
becario    hard   fsize     10240
FIN
chown -R alumno:alumno "$RETO"
SOL
