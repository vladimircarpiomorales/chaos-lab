#!/usr/bin/env bash
# Solución e2e de lpie-listar (reto r010-listar); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r010-listar "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r010-listar
ls -A casa > ocultos.txt.tmp
grep '^\.' ocultos.txt.tmp > ocultos.txt
rm ocultos.txt.tmp
ls -S casa | head -1 > grande.txt
ls -R casa > arbol.txt
cd casa/documentos/2024
pwd > "$RETO/donde.txt"
cd "$RETO"
chown -R alumno:alumno "$RETO"
SOL
