#!/usr/bin/env bash
# Solución e2e de lpic1-ssh-claves (reto r102-ssh-claves); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-ssh-claves "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-ssh-claves
ssh-keygen -t ed25519 -N "" -f /home/alumno/.ssh/id_ed25519
chmod 700 /home/alumno/.ssh
chmod 600 /home/alumno/.ssh/id_ed25519
cat /home/alumno/.ssh/id_ed25519.pub > /home/alumno/.ssh/authorized_keys
chmod 600 /home/alumno/.ssh/authorized_keys
cat > /home/alumno/.ssh/config <<'EOF'
Host servidor-lab
    HostName 10.0.0.50
    User operador
    Port 2222
EOF
chmod 600 /home/alumno/.ssh/config
chown -R alumno:alumno /home/alumno/.ssh
chown -R alumno:alumno "$RETO"
SOL
