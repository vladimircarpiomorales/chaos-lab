#!/usr/bin/env bash
# Solución e2e de red-nat-nftables (pack redes); la ejecuta tests/e2e/probar.sh o tests/e2e/redes_seco.sh
"$RT" exec "$C_FW" sh -c 'nft add table ip nat; nft add chain ip nat postrouting "{ type nat hook postrouting priority srcnat; }"; nft add rule ip nat postrouting oifname "eth1" masquerade; nft add table inet filtro; nft add chain inet filtro forward "{ type filter hook forward priority filter; policy drop; }"; nft add rule inet filtro forward ct state established,related accept; nft add rule inet filtro forward iifname "eth0" oifname "eth1" tcp dport 80 accept'
