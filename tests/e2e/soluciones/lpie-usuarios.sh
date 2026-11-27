#!/usr/bin/env bash
# Solución e2e de lpie-usuarios (reto r010-usuarios); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r010-usuarios "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r010-usuarios
groupadd ventas
useradd -m -s /bin/bash -G ventas pedro
grep '^pedro:' /etc/passwd > pedro.txt
id pedro > id.txt
userdel -r antiguo
chown -R alumno:alumno "$RETO"
SOL
