podman exec "$C_DEBIAN_VAULT" sh -c 'setfacl -b /srv/vault/close_month.sh /srv/vault/out && chmod 770 /srv/vault/close_month.sh /srv/vault/out'
