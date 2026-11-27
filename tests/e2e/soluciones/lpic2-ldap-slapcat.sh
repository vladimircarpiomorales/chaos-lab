#!/usr/bin/env bash
# Solución e2e de lpic2-ldap-slapcat (reto ldap06); la ejecuta tests/e2e/probar.sh o tests/e2e/ldap_seco.sh
"$RT" exec -i --user root -w /root/retos/ldap06 "$C_LDAP_SRV" bash -s <<'SOL'
slapd-ctl stop
slapcat -b dc=lpic,dc=lab -l /root/retos/ldap06/copia.ldif
slapd-ctl start
SOL
