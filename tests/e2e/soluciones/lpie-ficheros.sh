#!/usr/bin/env bash
# Solución e2e de lpie-ficheros (reto r010-ficheros); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r010-ficheros "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r010-ficheros
mkdir -p proyecto/src/viejo
cp -r plantilla proyecto/doc
mv borrador.txt final.txt
mv dia?.log proyecto/src/
rm -r basura
chown -R alumno:alumno "$RETO"
SOL
