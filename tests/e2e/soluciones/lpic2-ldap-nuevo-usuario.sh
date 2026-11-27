#!/usr/bin/env bash
# Solución e2e de lpic2-ldap-nuevo-usuario (reto ldap02); la ejecuta tests/e2e/probar.sh o tests/e2e/ldap_seco.sh
"$RT" exec -i --user root -w /root/retos/ldap02 "$C_LDAP_SRV" bash -s <<'SOL'
cat > sara.ldif <<'L'
dn: uid=sara,ou=personas,dc=lpic,dc=lab
objectClass: inetOrgPerson
objectClass: posixAccount
uid: sara
cn: Sara Gil
sn: Gil
uidNumber: 10010
gidNumber: 10000
homeDirectory: /home/sara
loginShell: /bin/bash
L
ldapadd -x -D cn=admin,dc=lpic,dc=lab -w admin -f sara.ldif
ldappasswd -x -D cn=admin,dc=lpic,dc=lab -w admin -s sara uid=sara,ou=personas,dc=lpic,dc=lab
SOL
"$RT" exec -i --user root "$C_LDAP_CLI" bash -s <<'SOL'
sss_cache -E
SOL
"$RT" exec -i --user root "$C_LDAP_SRV" bash -s <<'SOL'
for i in 1 2 3; do timeout 15 sshpass -p sara ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=5 sara@ldap-cli true && exit 0; sleep 2; done; exit 1
SOL
