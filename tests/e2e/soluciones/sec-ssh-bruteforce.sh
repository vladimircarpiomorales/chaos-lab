podman exec "$C_SSH_VICTIM" bash -c '
sleep 3
atk=$(grep "Failed password" /var/log/auth.log | sed -E "s/.* from ([0-9.]+) port.*/\1/" | sort | uniq -c | sort -rn | awk "NR==1{print \$2}")
echo "atacante: $atk"
nft add rule inet filter input ip saddr "$atk" drop
sed -i "/type filter hook input priority/a\\		ip saddr $atk drop" /etc/nftables.conf
nft -c -f /etc/nftables.conf && echo "conf OK"; grep -n "saddr" /etc/nftables.conf'
