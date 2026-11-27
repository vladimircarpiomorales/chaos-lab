#!/usr/bin/env bash
# Solución e2e de lpic1-rsyslog (reto r102-rsyslog); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-rsyslog "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-rsyslog
cat > /etc/rsyslog.d/60-app.conf <<'F'
local5.*      /var/log/app.log
local5.=err   /var/log/app-err.log
F
rsyslogd -N1
rsyslogd
sleep 1
logger -t app -p local5.info "arranque correcto"
logger -t app -p local5.err "fallo de disco"
logger -t app -p local5.crit "temperatura alta"
sleep 1
chown -R alumno:alumno "$RETO"
SOL
