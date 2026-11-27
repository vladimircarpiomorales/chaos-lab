#!/usr/bin/env bash
# Solución e2e de lpic1-usuarios (reto r102-usuarios); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-usuarios "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-usuarios
groupadd desarrollo
useradd -m -s /bin/bash -G desarrollo ana
chage -E 2027-12-31 ana
passwd -l ana
chown -R alumno:alumno "$RETO"
SOL
