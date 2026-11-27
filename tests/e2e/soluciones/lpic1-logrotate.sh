#!/usr/bin/env bash
# Solución e2e de lpic1-logrotate (reto r102-logrotate); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-logrotate "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-logrotate
cat > /etc/logrotate.d/tienda <<'F'
/var/log/tienda/*.log {
    weekly
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
    create 640 root adm
}
F
logrotate -d /etc/logrotate.d/tienda
logrotate -f /etc/logrotate.d/tienda
ls -l /var/log/tienda
chown -R alumno:alumno "$RETO"
SOL
