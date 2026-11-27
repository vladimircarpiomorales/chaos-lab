#!/usr/bin/env bash
# Solución e2e de lpic1-xvfb (reto r102-xvfb); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-xvfb "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-xvfb
xauth -f cookie add :7 . $(mcookie)
nohup Xvfb :7 -auth "$PWD/cookie" -screen 0 800x600x24 >/dev/null 2>&1 &
export DISPLAY=:7 XAUTHORITY="$PWD/cookie"
for i in $(seq 100); do xdpyinfo >/dev/null 2>&1 && break; sleep 0.1; done
xdpyinfo > pantalla.txt
chown -R alumno:alumno "$RETO"
SOL
