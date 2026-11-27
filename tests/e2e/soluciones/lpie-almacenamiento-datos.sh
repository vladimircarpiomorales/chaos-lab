#!/usr/bin/env bash
# Solución e2e de lpie-almacenamiento-datos (reto r010-almacenamiento-datos); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r010-almacenamiento-datos "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r010-almacenamiento-datos
{ which ps; which cut; } > rutas.txt
grep '^root:' /etc/passwd > etc.txt
grep '^MemTotal:' /proc/meminfo > memoria.txt
df -P /tmp | awk 'NR==2{print $6}' > montaje.txt
du -sm datos | cut -f1 > tamano.txt
chown -R alumno:alumno "$RETO"
SOL
