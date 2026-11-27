#!/usr/bin/env bash
# Solución e2e de lpic2-ldap-pam-access (reto ldap09); la ejecuta tests/e2e/probar.sh o tests/e2e/ldap_seco.sh
"$RT" exec -i --user root "$C_LDAP_CLI" bash -s <<'SOL'
sed -i '/^account.*pam_access/d' /etc/pam.d/sshd
grep -q '^account.*pam_access' /etc/pam.d/sshd || sed -i '0,/^@include common-account/s//account required pam_access.so\n@include common-account/' /etc/pam.d/sshd
sed -i '/^[+-]/d' /etc/security/access.conf
printf '+:root:ALL\n+:(admins):ALL\n-:ALL:ALL\n' >> /etc/security/access.conf
sss_cache -E
SOL
