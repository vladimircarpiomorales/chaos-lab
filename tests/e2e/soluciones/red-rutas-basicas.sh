#!/usr/bin/env bash
# Solución e2e de red-rutas-basicas (pack redes); la ejecuta tests/e2e/probar.sh o tests/e2e/redes_seco.sh
"$RT" exec "$C_R1" sysctl -w net.ipv4.ip_forward=1
"$RT" exec "$C_CLIENTE" ip route add 10.6.2.0/24 via 10.6.1.1
"$RT" exec "$C_WEB" ip route add 10.6.1.0/24 via 10.6.2.1
