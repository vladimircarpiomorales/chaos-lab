"$RT" exec "$C_NS1_MASTER" bash -c '
z=/etc/bind/zones/db.corp.lan
sed -i -E "s/^(api +IN +A +).*/\1'"$IP_NS1_MASTER"'/; s/^(portal +IN +CNAME +api\.corp\.lan)$/\1./; s/2026112501 ; Serial/2026112502 ; Serial/" $z
cat $z; named-reload'
