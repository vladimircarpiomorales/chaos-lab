#!/usr/bin/env bash
# Solución e2e de lpic1-script (reto r102-script); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-script "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-script
cat > cuenta.sh <<'F'
#!/bin/bash
if [ $# -eq 0 ]; then
  echo "uso: cuenta.sh FICHERO..."
  exit 1
fi
echo $#
F
chmod +x cuenta.sh
chown -R alumno:alumno "$RETO"
SOL
