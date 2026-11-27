port=$(podman exec "$C_PAYMENTS_API" sh -c 'grep ^PORT= /opt/payments/payments.env | cut -d= -f2')
podman exec "$C_PAYMENTS_API" bash -c 'sed -i "s/^BIND_ADDR=.*/BIND_ADDR=0.0.0.0/" /opt/payments/payments.env && restart-payments'
podman exec "$C_EDGE_PROXY" sh -c "sed -i -E 's#payments-api:[0-9]+#payments-api:$port#g' /etc/nginx/conf.d/payments.conf && nginx -s reload"
