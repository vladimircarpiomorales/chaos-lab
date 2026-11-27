rp=$(podman exec "$C_REDIS_CACHE" sh -c "grep requirepass /tmp/redis-chaos.conf | cut -d' ' -f2")
podman exec "$C_APP_NODE" bash -c "
grep -v 'cache.internal' /etc/hosts > /tmp/h; echo '$IP_REDIS_CACHE cache.internal' >> /tmp/h; cat /tmp/h > /etc/hosts
sed -i 's/^REDIS_PORT=.*/REDIS_PORT=6379/; s/^REDIS_PASSWORD=.*/REDIS_PASSWORD=$rp/' /opt/app/cache.conf"
