#!/usr/bin/env bash
# Solución e2e de lpic2-ldap-busqueda (reto ldap01); la ejecuta tests/e2e/probar.sh o tests/e2e/ldap_seco.sh
"$RT" exec -i --user root -w /root/retos/ldap01 "$C_LDAP_SRV" bash -s <<'SOL'
ldapsearch -x -LLL -b ou=personas,dc=lpic,dc=lab '(uidNumber>=10003)' uid > uids.txt
SOL
