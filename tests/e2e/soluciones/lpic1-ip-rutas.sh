#!/usr/bin/env bash
# Solución e2e de lpic1-ip-rutas (reto r102-ip-rutas); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-ip-rutas "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-ip-rutas
ip link show lo
ip route
cat /sys/class/net/lo/mtu > mtu.txt
gw=$(ip route show default | awk '{print $3; exit}'); echo "${gw:-ninguna}" > puerta.txt
dev=$(ip route show default | awk '{print $5; exit}'); echo "${dev:-ninguna}" > interfaz.txt
if [ -n "$dev" ]; then ip -4 -o address show dev "$dev" | awk '{print $4; exit}' > direccion.txt; else echo ninguna > direccion.txt; fi
chown -R alumno:alumno "$RETO"
SOL
