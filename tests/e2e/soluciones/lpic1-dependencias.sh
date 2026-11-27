#!/usr/bin/env bash
# Solución e2e de lpic1-dependencias (reto r101-dependencias); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r101-dependencias "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r101-dependencias
ldd /bin/bash > bash-dependencias.txt
grep 'libc.so.6 =>' bash-dependencias.txt > glibc.txt
ldconfig -p | grep 'libc.so.6' > cache-glibc.txt
chown -R alumno:alumno "$RETO"
SOL
