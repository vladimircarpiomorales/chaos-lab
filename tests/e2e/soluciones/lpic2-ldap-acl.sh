#!/usr/bin/env bash
# Solución e2e de lpic2-ldap-acl (reto ldap08); la ejecuta tests/e2e/probar.sh o tests/e2e/ldap_seco.sh
"$RT" exec -i --user root -w /root/retos/ldap08 "$C_LDAP_SRV" bash -s <<'SOL'
ldapmodify -Q -Y EXTERNAL -H ldapi:/// <<'L'
dn: olcDatabase={1}mdb,cn=config
changetype: modify
add: olcAccess
olcAccess: {0}to attrs=mail by users read by * none
L
SOL
