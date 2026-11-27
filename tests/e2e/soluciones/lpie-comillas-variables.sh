#!/usr/bin/env bash
# Solución e2e de lpie-comillas-variables (reto r010-comillas-variables); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r010-comillas-variables "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r010-comillas-variables
saludo=hola
export ORDEN=desc
bash -c 'echo "[$saludo][$ORDEN]"' > hijo.txt
env | grep '^ORDEN=' > entorno.txt
unset ORDEN
echo "[${ORDEN-}]" > borrada.txt
which ls > ls.txt
type cd > cd.txt
printf '%s\n' '$HOME' "\$HOME" > comillas.txt
chown -R alumno:alumno "$RETO"
SOL
