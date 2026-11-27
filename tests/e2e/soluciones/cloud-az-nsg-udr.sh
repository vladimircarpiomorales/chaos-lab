podman exec "$C_VNET_WEB" bash -c '
net=$(ip route show type blackhole | awk "{print \$2}")
ip route del blackhole "$net"; ip route add "$net" via '"$IP_NVA_FW"
podman exec "$C_NVA_FW" bash -c 'sed -i "s/^ENABLE_IP_FORWARDING=.*/ENABLE_IP_FORWARDING=true/" /etc/nva_appliance.conf && nva-apply'
podman exec "$C_VNET_DB" bash -c 'iptables -D NSG_INBOUND 1 && iptables -L NSG_INBOUND -n --line-numbers'
