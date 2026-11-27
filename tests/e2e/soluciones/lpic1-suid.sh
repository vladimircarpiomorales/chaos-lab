#!/usr/bin/env bash
# Solución e2e de lpic1-suid (reto r102-suid); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-suid "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-suid
find /usr/bin -perm -4000 -type f | sort > suid.txt
chmod u-s sospechoso/copia-de-bash
chown -R alumno:alumno "$RETO"
SOL
