#!/usr/bin/env bash
# Solución e2e de lpic1-chrony (reto r102-chrony); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-chrony "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-chrony
sed -i 's/^pool /#pool /; s/^makestep .*/makestep 0.5 5/' /etc/chrony/chrony.conf
printf 'server 0.es.pool.ntp.org iburst\nserver 1.es.pool.ntp.org iburst\n' >> /etc/chrony/chrony.conf
chronyd -p > config.txt
chown -R alumno:alumno "$RETO"
SOL
