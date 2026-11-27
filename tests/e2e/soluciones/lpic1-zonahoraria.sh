#!/usr/bin/env bash
# Solución e2e de lpic1-zonahoraria (reto r102-zonahoraria); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-zonahoraria "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-zonahoraria
ln -sf /usr/share/zoneinfo/America/Bogota /etc/localtime
TZ=Asia/Tokyo date +%Z > tokio.txt
date -u -d @1564013011 +%F > epoch.txt
chown -R alumno:alumno "$RETO"
SOL
