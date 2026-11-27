#!/usr/bin/env bash
# Solución e2e de lpie-red-basica (reto r010-red-basica); la ejecuta tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r010-red-basica "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r010-red-basica
ip -br addr show lo > lo.txt
getent ahostsv4 localhost | awk 'NR==1{print $1}' > resuelve.txt
grep -m1 localhost /etc/hosts > hosts.txt
awk '/^nameserver/{print $2; exit}' /etc/resolv.conf > dns.txt
grep '^hosts:' /etc/nsswitch.conf > orden.txt
chown -R alumno:alumno "$RETO"
SOL
