#!/usr/bin/env bash
# Solución e2e de lpic1-permisos (reto r101-permisos); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r101-permisos "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r101-permisos
chmod 600 secreto.txt
chmod 744 script.sh
groupadd proyecto
chgrp proyecto compartida
chmod 2775 compartida
chmod 1777 publica
SOL
