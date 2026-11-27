"$RT" exec "$C_GATEWAY_RTR" bash -c '
net=$(ip route show type blackhole | awk "{print \$2}")
ip route del blackhole "$net"
ip route add "$net" via '"$IP_BRANCH_SRV"'
ip route'
