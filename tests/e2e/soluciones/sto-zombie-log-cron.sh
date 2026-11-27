podman exec "$C_DEBIAN_STORAGE" bash -c '
pgrep -x cron >/dev/null && echo "cron vivo" || echo "CRON NO CORRE"
rogue=$(grep -o "/usr/local/libexec/[a-z-]*" /etc/cron.d/ingest-watchdog | head -1)
rm -f /etc/cron.d/ingest-watchdog
pkill -f "$rogue"; sleep 0.5
truncate -s 0 /var/log/ingest/overflow.log'
