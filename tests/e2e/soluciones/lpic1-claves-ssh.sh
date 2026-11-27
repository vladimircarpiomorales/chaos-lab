#!/usr/bin/env bash
# Solución e2e de lpic1-claves-ssh (reto r102-claves-ssh); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-claves-ssh "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-claves-ssh
install -d -m 700 /root/.ssh
ssh-keygen -t ed25519 -N '' -C root@lpi-lab -f /root/.ssh/lab_ed25519
install -d -m 700 -o ina -g ina /home/ina/.ssh
cat /root/.ssh/lab_ed25519.pub >> /home/ina/.ssh/authorized_keys
chown ina:ina /home/ina/.ssh/authorized_keys
chmod 600 /home/ina/.ssh/authorized_keys
cat >> /root/.ssh/config <<'FIN'
Host servidor-lab
    HostName 127.0.0.1
    User ina
    Port 2222
    IdentityFile ~/.ssh/lab_ed25519
FIN
chmod 600 /root/.ssh/config
chown -R alumno:alumno "$RETO"
SOL
