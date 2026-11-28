#!/usr/bin/env bash
# Solución e2e de red-otra-interfaz (pack redes); la ejecuta tests/e2e/probar.sh o tests/e2e/redes_seco.sh
"$RT" exec "$C_DEV" ip route add 10.9.2.10/32 via 10.9.1.10
