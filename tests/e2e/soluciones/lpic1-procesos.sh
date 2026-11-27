#!/usr/bin/env bash
# Solución e2e de lpic1-procesos (reto r101-procesos); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r101-procesos "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r101-procesos
pgrep -x copianocturna > pid.txt
renice -n 15 -p "$(cat pid.txt)"
kill "$(pgrep -x minerocripto)"
nohup nice -n 10 informe 3600 >/dev/null 2>&1 &
chown -R alumno:alumno "$RETO"
SOL
