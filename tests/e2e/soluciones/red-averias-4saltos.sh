#!/usr/bin/env bash
# Solución e2e de red-averias-4saltos (pack redes); la ejecuta tests/e2e/probar.sh o tests/e2e/redes_seco.sh
# 1) pc1: puerta de enlace que existe
"$RT" exec "$C_PC1" ip route replace 10.5.0.0/16 via 10.5.1.1
# 2) r2: ruta de vuelta hacia la lan
"$RT" exec "$C_R2" ip route add 10.5.1.0/24 via 10.5.12.1
# 3) srv: quitar el filtrado del puerto 80
"$RT" exec "$C_SRV" nft flush ruleset
# 4) pc1: web.lab a su IP real (/etc/hosts está montado: se reescribe por dentro, sin sed -i)
"$RT" exec "$C_PC1" sh -c 'grep -v " web.lab" /etc/hosts > /tmp/h; echo "10.5.3.10 web.lab" >> /tmp/h; cat /tmp/h > /etc/hosts'
