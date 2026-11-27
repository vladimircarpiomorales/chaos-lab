#!/usr/bin/env bash
# Solución e2e de lpic1-hardware (reto r101-hardware); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r101-hardware "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r101-hardware
lsmod > modulos.txt
echo "blacklist snd_hda_intel" > /etc/modprobe.d/blacklist-audio.conf
grep -m1 'model name' /proc/cpuinfo | sed 's/.*: //' > cpu-modelo.txt
echo "dummy" > /etc/modules-load.d/red-virtual.conf
chown -R alumno:alumno "$RETO"
SOL
