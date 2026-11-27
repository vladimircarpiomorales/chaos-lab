"$RT" exec "$C_HQ_VPN_GW" bash -c '
port=$(wg-apply | grep -o "escucha en [0-9]*" | grep -o "[0-9]*")
oct=$(grep -o "^Address = 10\.[0-9]*" /etc/wireguard/wg0.conf | cut -d. -f2)
sed -i -E "s/^(Endpoint = [^:]+):[0-9]+/\1:$port/; s|^AllowedIPs = .*|AllowedIPs = 10.$oct.0.0/24|; s/^MTU = .*/MTU = 1420/" /etc/wireguard/wg0.conf
cat /etc/wireguard/wg0.conf; wg-apply'
