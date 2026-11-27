#!/usr/bin/env bash
# Solución e2e de lpic1-resolucion (reto r102-resolucion); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-resolucion "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-resolucion
sed -i 's/^hosts:.*/hosts:          files dns/' /etc/nsswitch.conf
echo '192.168.50.10   servidor.lab.local servidor' >> /etc/hosts
echo '192.168.50.20   backup.lab.local backup' >> /etc/hosts
getent hosts backup > backup.txt
antes=$(grep -E '^search[[:space:]]' /etc/resolv.conf | tail -n 1 | cut -d' ' -f2-)
echo "search $antes lab.local" | tr -s ' ' >> /etc/resolv.conf
cat /etc/resolv.conf
chown -R alumno:alumno "$RETO"
SOL
