#!/usr/bin/env bash
# Solución e2e de lpic2-ldap-clave (reto ldap04); la ejecuta tests/e2e/probar.sh o tests/e2e/ldap_seco.sh
"$RT" exec -i --user root -w /root/retos/ldap04 "$C_LDAP_SRV" bash -s <<'SOL'
ldappasswd -x -D cn=admin,dc=lpic,dc=lab -w admin -s Nueva123 uid=luis,ou=personas,dc=lpic,dc=lab
SOL
