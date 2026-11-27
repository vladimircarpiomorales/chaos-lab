#!/usr/bin/env bash
# Solución e2e de lpic1-sudo (reto r102-sudo); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-sudo "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-sudo
cat > /etc/sudoers.d/soporte <<'FIN'
soporte ALL=(root) NOPASSWD: /usr/bin/ls /root, /usr/bin/id
soporte ALL=(www-data) NOPASSWD: /usr/bin/whoami
FIN
chmod 440 /etc/sudoers.d/soporte
visudo -cf /etc/sudoers.d/soporte > visudo.txt
chown -R alumno:alumno "$RETO"
SOL
