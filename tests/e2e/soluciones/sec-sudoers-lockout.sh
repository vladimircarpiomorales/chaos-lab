podman exec "$C_DEBIAN_SEC" bash -c '
ls /etc/sudoers.d/
echo "alumno ALL=(ALL) NOPASSWD: /usr/local/bin/deploy-check" > /etc/sudoers.d/90-ops
chmod 0440 /etc/sudoers.d/90-ops
usermod -s /bin/bash alumno
passwd -u alumno
visudo -c'
