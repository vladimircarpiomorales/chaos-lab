#!/usr/bin/env bash
# Solución e2e de red-ospf-frr (pack redes); la ejecuta tests/e2e/probar.sh o tests/e2e/redes_seco.sh

"$RT" exec "$C_R1" sh -c 'cat > /etc/frr/daemons <<"EOF"
zebra=yes
ospfd=yes
vtysh_enable=yes
EOF
cat > /etc/frr/frr.conf <<"EOF"
frr defaults traditional
hostname r1
ip forwarding
!
interface eth0
 ip address 10.8.1.1/24
exit
!
interface eth1
 ip address 10.8.12.1/30
 ip ospf network point-to-point
exit
!
interface eth2
 ip address 10.8.13.1/30
 ip ospf network point-to-point
exit
!
router ospf
 ospf router-id 1.1.1.1
 network 10.8.0.0/16 area 0
 passive-interface eth0
exit
!
EOF
/usr/lib/frr/frrinit.sh start'

"$RT" exec "$C_R2" sh -c 'cat > /etc/frr/daemons <<"EOF"
zebra=yes
ospfd=yes
vtysh_enable=yes
EOF
cat > /etc/frr/frr.conf <<"EOF"
frr defaults traditional
hostname r2
ip forwarding
!
interface eth0
 ip address 10.8.12.2/30
 ip ospf network point-to-point
exit
!
interface eth1
 ip address 10.8.23.1/30
 ip ospf network point-to-point
exit
!
router ospf
 ospf router-id 2.2.2.2
 network 10.8.0.0/16 area 0
exit
!
EOF
/usr/lib/frr/frrinit.sh start'

"$RT" exec "$C_R3" sh -c 'cat > /etc/frr/daemons <<"EOF"
zebra=yes
ospfd=yes
vtysh_enable=yes
EOF
cat > /etc/frr/frr.conf <<"EOF"
frr defaults traditional
hostname r3
ip forwarding
!
interface eth0
 ip address 10.8.13.2/30
 ip ospf network point-to-point
exit
!
interface eth1
 ip address 10.8.23.2/30
 ip ospf network point-to-point
exit
!
interface eth2
 ip address 10.8.3.1/24
exit
!
router ospf
 ospf router-id 3.3.3.3
 network 10.8.0.0/16 area 0
 passive-interface eth2
exit
!
EOF
/usr/lib/frr/frrinit.sh start'
