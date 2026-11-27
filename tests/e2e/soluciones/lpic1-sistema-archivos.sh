#!/usr/bin/env bash
# Solución e2e de lpic1-sistema-archivos (reto r101-sistema-archivos); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r101-sistema-archivos "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r101-sistema-archivos
truncate -s 64M disco.img
mkfs.ext4 -q -L DATOS disco.img
tune2fs -c 30 disco.img
blkid disco.img > info.txt
chown -R alumno:alumno "$RETO"
SOL
