podman exec "$C_ROCKY_BILLING" bash -c '
sed -i "s/\r$//" /opt/billing/billingd.sh && chmod +x /opt/billing/billingd.sh
sed -i -E "s/^BILLING_PORT *= */BILLING_PORT=/" /etc/sysconfig/billing.env
chmod 0755 /var/run/billing
/opt/billing/billingd.sh; sleep 1'
