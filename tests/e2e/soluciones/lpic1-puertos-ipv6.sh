#!/usr/bin/env bash
# Solución e2e de lpic1-puertos-ipv6 (reto r102-puertos-ipv6); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-puertos-ipv6 "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-puertos-ipv6
getent services ssh
for s in ssh smtp domain imaps ldaps; do getent services $s/tcp | awk '{print $2}' | cut -d/ -f1; done > puertos.txt
getent services 995/tcp | awk '{print $1}' > servicio.txt
getent services 514/udp | awk '{print $1}' >> servicio.txt
printf 'fd42:abcd:1234::5678\n2001:dead::beef:0:0:cafe\n' > ipv6.txt
chown -R alumno:alumno "$RETO"
SOL
