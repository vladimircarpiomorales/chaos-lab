"$RT" exec "$C_EDGE_SRV" bash -c '
sleep 4
for ip in $(grep -o "SRC=[0-9.]*" /var/log/portwatch.log | cut -d= -f2 | sort -u); do
  echo "$(grep "SRC=$ip " /var/log/portwatch.log | grep -o "DPT=[0-9]*" | sort -u | wc -l) $ip"
done | sort -rn | tee /dev/stderr | awk "NR==1{print \$2}" > /tmp/scanner
nft add rule inet filter input ip saddr $(cat /tmp/scanner) drop; nft list chain inet filter input'
