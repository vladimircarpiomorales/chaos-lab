#!/usr/bin/env bash
# Solución e2e de lpic1-ficheros (reto r101-ficheros); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r101-ficheros "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r101-ficheros
cd descargas
mkdir -p logs fotos
mv *.log logs/
mv *.jpg fotos/
rm *.tmp
cp informe.txt informe.txt.bak
chown -R alumno:alumno "$RETO"
SOL
