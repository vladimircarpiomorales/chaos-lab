#!/usr/bin/env bash
# Solución e2e de lpic1-cron (reto r102-cron); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-cron "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-cron
echo '30 2 * * * root /home/alumno/retos/r102-cron/copia.sh' > /etc/cron.d/copia
printf 'minuto\nhora\ndia\nmes\nsemana\n' > campos.txt
chown -R alumno:alumno "$RETO"
SOL
