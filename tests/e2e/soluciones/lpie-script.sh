#!/usr/bin/env bash
# Solución e2e de lpie-script (reto r010-script); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r010-script "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r010-script
cat > saluda.sh <<'F'
#!/bin/bash
if [ $# -eq 0 ]; then
  echo "uso: saluda.sh NOMBRE..."
  exit 1
fi
for nombre in "$@"; do
  echo "Hola $nombre"
done
exit 0
F
chmod +x saluda.sh
chown -R alumno:alumno "$RETO"
SOL
