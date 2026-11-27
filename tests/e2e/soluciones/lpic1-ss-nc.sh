#!/usr/bin/env bash
# Solución e2e de lpic1-ss-nc (reto r102-ss-nc); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-ss-nc "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-ss-nc
ss -tlnp
P=$(ss -Hltnp | grep '"socat"' | awk '{print $4}' | sed 's/.*://' | head -n 1)
echo "$P" > puerto.txt
ss -Hltnp "sport = :$P" | grep -o '(("[^"]*' | cut -d'"' -f2 > programa.txt
nc 127.0.0.1 "$P" < /dev/null | awk '{print $NF}' > clave.txt
kill $(ss -Hltnp "sport = :$P" | grep -o 'pid=[0-9]*' | cut -d= -f2)
for i in $(seq 50); do ss -Hltn "sport = :$P" | grep -q . || break; sleep 0.1; done
ss -tln
chown -R alumno:alumno "$RETO"
SOL
