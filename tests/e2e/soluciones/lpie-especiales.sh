#!/usr/bin/env bash
# Solución e2e de lpie-especiales (reto r010-especiales); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r010-especiales "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r010-especiales
chgrp equipo compartido
chmod 770 compartido
chmod g+s compartido
chmod o+t compartido
ln -s compartido atajo
SOL
