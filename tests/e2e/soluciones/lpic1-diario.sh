#!/usr/bin/env bash
# Solución e2e de lpic1-diario (reto r102-diario); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-diario "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-diario
journalctl -D diario -t copias -p err -o cat > errores.txt
journalctl -D diario -p warning..warning -o cat > avisos.txt
journalctl -D diario -t sshd -r -n 3 -o cat > ultimas.txt
chown -R alumno:alumno "$RETO"
SOL
