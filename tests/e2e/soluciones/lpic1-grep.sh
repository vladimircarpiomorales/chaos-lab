#!/usr/bin/env bash
# Solución e2e de lpic1-grep (reto r101-grep); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r101-grep "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r101-grep
grep '^192\.168\.' acceso.log > internas.txt
grep -E ' (404|500)$' acceso.log > fallos.txt
grep -c POST acceso.log > n-post.txt
chown -R alumno:alumno "$RETO"
SOL
