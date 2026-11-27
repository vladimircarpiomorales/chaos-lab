podman exec "$C_TLS_GATEWAY" bash -c '
cd /opt/tls
printf "subjectAltName=DNS:vault.corp.internal\n" > good_ext.cnf
openssl x509 -req -in server.csr -CA /etc/ssl/corp-ca/ca.crt -CAkey /etc/ssl/corp-ca/ca.key -CAcreateserial \
  -out server.crt -days 365 -extfile good_ext.cnf
restart-tls-gw; sleep 1'
