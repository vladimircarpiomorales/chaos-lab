#!/usr/bin/env bash
# Solución e2e de lpic2-ldap-tls (reto ldap07); la ejecuta tests/e2e/probar.sh o tests/e2e/ldap_seco.sh
"$RT" exec -i --user root -w /root/retos/ldap07 "$C_LDAP_SRV" bash -s <<'SOL'
ldapsearch -x -LLL -ZZ -H ldap://ldap-srv '(uid=carol)' mail > starttls.txt
ldapsearch -x -LLL -H ldaps://ldap-srv '(uid=ana)' dn > ldaps.txt
openssl s_client -connect ldap-srv:636 </dev/null 2>/dev/null | openssl x509 -noout -subject > cert.txt
SOL
