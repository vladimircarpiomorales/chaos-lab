#!/usr/bin/env bash
# Solución e2e de lpie-almacenamiento-datos2 (reto r010-almacenamiento-datos2); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r010-almacenamiento-datos2 "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r010-almacenamiento-datos2
sleep 1234 </dev/null >/dev/null 2>&1 &
echo $! > pid.txt
cat "/proc/$(cat pid.txt)/comm" > comm.txt
ps -p "$(cat pid.txt)" -o pid=,comm= > ps.txt
ps -o stat= -p "$(cat pid.txt)" | tr -d ' ' | cut -c1 > estado.txt
chown -R alumno:alumno "$RETO"
SOL
