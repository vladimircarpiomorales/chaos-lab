#!/bin/bash
# sin systemd: sssd y sshd a mano
mkdir -p /run/sshd /var/lib/sss/db /var/log/sssd
rm -f /var/lib/sss/db/* /run/sssd.pid 2>/dev/null
/usr/sbin/sssd --logger=files -D
exec /usr/sbin/sshd -D -e
