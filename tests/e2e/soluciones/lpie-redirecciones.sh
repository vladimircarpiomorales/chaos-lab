#!/usr/bin/env bash
# Solución e2e de lpie-redirecciones (reto r010-redirecciones); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r010-redirecciones "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r010-redirecciones
ls /etc/hostname /no/existe > bien.txt 2> mal.txt
echo FIN >> bien.txt
sort nombres.txt | head -n 3 > top3.txt
wc -w < nombres.txt > palabras.txt
chown -R alumno:alumno "$RETO"
SOL
