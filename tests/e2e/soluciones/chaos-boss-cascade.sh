"$RT" exec "$C_VAULT_DB" sh -c 'redis-cli REPLICAOF NO ONE'
"$RT" exec "$C_CORE_API" sh -c 'iptables -F OUTPUT'
"$RT" exec "$C_EDGE_LB" sh -c "sed -i -E 's#http://127\.0\.0\.1:([0-9]+)#http://core-api:\1#' /etc/nginx/conf.d/edge.conf && grep proxy_pass /etc/nginx/conf.d/edge.conf && nginx -s reload"
