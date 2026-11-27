#!/usr/bin/env bash
# Solución e2e de lpic1-esquema-particionado (reto r101-esquema-particionado); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r101-esquema-particionado "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r101-esquema-particionado
truncate -s 1G disco.img
sfdisk disco.img << 'EOF'
label: dos
size=200M, type=83
size=256M, type=82
size=300M, type=83
type=83
EOF
cat > fstab.nuevo << 'EOF'
/dev/sdb1 /boot ext4 defaults 0 2
/dev/sdb2 none swap sw 0 0
/dev/sdb3 / ext4 defaults 0 1
/dev/sdb4 /var ext4 defaults 0 2
EOF
chown -R alumno:alumno "$RETO"
SOL
