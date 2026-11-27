#!/usr/bin/env bash
# Solución e2e de lpic1-subredes (reto r102-subredes); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-subredes "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-subredes
ipcalc 10.0.45.200/255.255.240.0
ipcalc 192.168.100.130/26
printf '20\n10.0.32.0\n10.0.47.255\n4094\n' > red-a.txt
printf '255.255.255.192\n192.168.100.128\n192.168.100.191\n62\n' > red-b.txt
echo 11000000.10101000.01100100.10000010 > binario.txt
chown -R alumno:alumno "$RETO"
SOL
