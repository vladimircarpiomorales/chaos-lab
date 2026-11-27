#!/usr/bin/env bash
# Solución e2e de lpic1-networkd (reto r102-networkd); la ejecuta tests/e2e/probar.sh o tests/e2e/lpic_seco.sh
"$RT" exec -i --user root -w /home/alumno/retos/r102-networkd "$C_LPIC" bash -s <<'SOL'
set -u
export RETO=/home/alumno/retos/r102-networkd
mkdir -p /etc/systemd/network /etc/wpa_supplicant
cat > /etc/systemd/network/30-lan.network <<'FIN'
[Match]
Name=en*

[Network]
Address=192.168.0.100/24
Gateway=192.168.0.1
DNS=192.168.0.1
FIN
cat > /etc/systemd/network/40-wifi.network <<'FIN'
[Match]
Name=wlo1

[Network]
DHCP=ipv4
FIN
wpa_passphrase MyWifi MyPassword > /etc/wpa_supplicant/wpa_supplicant-wlo1.conf
sed -i '/#psk=/d' /etc/wpa_supplicant/wpa_supplicant-wlo1.conf
cat /etc/wpa_supplicant/wpa_supplicant-wlo1.conf
echo wpa_supplicant@wlo1.service > servicio.txt
chown -R alumno:alumno "$RETO"
SOL
