#!/usr/bin/env bash
# Solución e2e de lpie-comprimir (reto r010-comprimir); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r010-comprimir "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r010-comprimir
tar czf copia.tar.gz docs
bzip2 grande.txt
tar xf paquete.tar config/red.conf
zip -r para-windows.zip docs
chown -R alumno:alumno "$RETO"
SOL
