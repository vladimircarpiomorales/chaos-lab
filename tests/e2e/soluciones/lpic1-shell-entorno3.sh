#!/usr/bin/env bash
# Solución e2e de lpic1-shell-entorno3 (reto r102-shell-entorno3); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-shell-entorno3 "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-shell-entorno3
cat >> /home/alumno/.bashrc <<'FIN'
export PATH="$HOME/bin:$PATH"
fyi() {
  echo "usuario: $(id -un)"
  echo "directorio: $HOME"
  echo "equipo: $(uname -n)"
}
alias carpeta='pwd; ls -la'
FIN
mkdir -p /home/alumno/bin
printf '#!/bin/bash\necho "hola desde ~/bin"\n' > /home/alumno/bin/saluda
chmod +x /home/alumno/bin/saluda
chown -R alumno:alumno /home/alumno/bin /home/alumno/.bashrc
chown -R alumno:alumno "$RETO"
SOL
