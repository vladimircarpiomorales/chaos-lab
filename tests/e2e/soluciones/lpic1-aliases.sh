#!/usr/bin/env bash
# Solución e2e de lpic1-aliases (reto r102-aliases); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-aliases "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-aliases
printf 'soporte: marta, pablo\nwebmaster: root\n' >> /etc/aliases
newaliases
su - pablo -c 'echo marta > ~/.forward'
chown -R alumno:alumno "$RETO"
SOL
