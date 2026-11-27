#!/usr/bin/env bash
# Solución e2e de lpie-grep (reto r010-grep); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r010-grep "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r010-grep
grep -i cable inventario.txt > cables.txt
grep ' 0$' inventario.txt > sin-stock.txt
grep -v '^#' inventario.txt > no-comentarios.txt
grep -c teclado inventario.txt > n-teclados.txt
chown -R alumno:alumno "$RETO"
SOL
