#!/usr/bin/env bash
# Solución e2e de lpie-permisos (reto r010-permisos); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r010-permisos "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r010-permisos
chmod 640 informe.txt
chmod u+x copia.sh
chown luis:contabilidad informe.txt
chmod 700 privado
chmod o-r notas.txt
SOL
