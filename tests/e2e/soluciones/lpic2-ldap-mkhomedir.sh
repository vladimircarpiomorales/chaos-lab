#!/usr/bin/env bash
# Solución e2e de lpic2-ldap-mkhomedir (reto ldap10); la ejecuta tests/e2e/probar.sh o tests/e2e/ldap_seco.sh
"$RT" exec -i --user root "$C_LDAP_CLI" bash -s <<'SOL'
sed -i 's/^\(session[[:space:]]\+optional[[:space:]]\+pam_mkhomedir.so\).*/\1 umask=0027/' /etc/pam.d/common-session
sss_cache -E
SOL
"$RT" exec -i --user root "$C_LDAP_SRV" bash -s <<'SOL'
for i in 1 2 3; do timeout 15 sshpass -p marta ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=5 marta@ldap-cli true && exit 0; sleep 2; done; exit 1
SOL
