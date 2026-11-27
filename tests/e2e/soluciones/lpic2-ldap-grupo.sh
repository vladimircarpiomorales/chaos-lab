#!/usr/bin/env bash
# Solución e2e de lpic2-ldap-grupo (reto ldap03); la ejecuta tests/e2e/probar.sh o tests/e2e/ldap_seco.sh
"$RT" exec -i --user root -w /root/retos/ldap03 "$C_LDAP_SRV" bash -s <<'SOL'
ldapmodify -x -D cn=admin,dc=lpic,dc=lab -w admin <<'L'
dn: cn=admins,ou=grupos,dc=lpic,dc=lab
changetype: modify
add: memberUid
memberUid: pedro
L
SOL
"$RT" exec -i --user root "$C_LDAP_CLI" bash -s <<'SOL'
sss_cache -E
SOL
