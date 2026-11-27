"$RT" exec "$C_INFECTED_HOST" bash -c '
dir=$(ls -d /var/tmp/.*/ 2>/dev/null | grep -v "/\.\./\|/\./" | head -1); echo "oculto: $dir"
grep -l "$dir" /etc/cron.d/* 2>/dev/null | xargs -r rm -v
crontab -l 2>/dev/null | grep -v "$dir" | crontab - 2>/dev/null
pkill -f "$dir"; sleep 0.5; rm -rf "$dir"
nft list table inet filter >/dev/null 2>&1 || { nft add table inet filter; nft "add chain inet filter output { type filter hook output priority 0; policy accept; }"; }
nft list chain inet filter output >/dev/null 2>&1 || nft "add chain inet filter output { type filter hook output priority 0; policy accept; }"
nft add rule inet filter output udp dport 53 ip daddr != '"$IP_CORP_DNS"' drop
nft add rule inet filter output tcp dport 53 ip daddr != '"$IP_CORP_DNS"' drop
nft list chain inet filter output; pgrep -af "$dir" || echo "sin proceso"'
