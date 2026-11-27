#!/usr/bin/env bash
# Solución e2e de lpic1-variables-entorno (reto r101-variables-entorno); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r101-variables-entorno "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r101-variables-entorno
VAR_LOCAL="solo aqui"
export VAR_EXPORTADA="hola desde el padre"
bash -c 'echo "[$VAR_LOCAL]"; echo "[$VAR_EXPORTADA]"' > hijos.txt
env | grep '^VAR_' > env.txt
printenv VAR_EXPORTADA > printenv.txt
unset VAR_EXPORTADA
echo "[${VAR_EXPORTADA-}]" > unset.txt
printf '%s\n' '$HOME' "\$HOME" > comillas.txt
chown -R alumno:alumno "$RETO"
SOL
