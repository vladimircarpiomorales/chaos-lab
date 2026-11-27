#!/usr/bin/env bash
# Solución e2e de lpic2-ldap-indice (reto ldap05); la ejecuta tests/e2e/probar.sh o tests/e2e/ldap_seco.sh
"$RT" exec -i --user root -w /root/retos/ldap05 "$C_LDAP_SRV" bash -s <<'SOL'
ldapmodify -Q -Y EXTERNAL -H ldapi:/// <<'L'
dn: olcDatabase={1}mdb,cn=config
changetype: modify
add: olcDbIndex
olcDbIndex: mail eq
L
SOL
