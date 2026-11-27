#!/bin/bash
# Sin systemd: este script hace de «systemd» para slapd. Si slapd se para (kill o slapd-ctl stop)
# lo vuelve a levantar, salvo que exista /run/slapd.parado.
mkdir -p /run/slapd; chown openldap:openldap /run/slapd
rm -f /run/slapd.parado
trap 'kill $(pidof slapd) 2>/dev/null; exit 0' TERM INT
while true; do
  if [ ! -e /run/slapd.parado ] && ! pidof slapd >/dev/null; then
    /usr/sbin/slapd -u openldap -g openldap -h "ldap:/// ldaps:/// ldapi:///"
  fi
  sleep 1 & wait $!
done
