"""
Catálogo de escenarios dinámicos de Chaos Lab.
Cada escenario usa un generador con semilla aleatoria (Chaos Mutator) para variar
puertos, tokens, subredes o nombres en cada despliegue, evitando soluciones memorizadas.
"""

from __future__ import annotations

import random
from typing import Any

from .packs import load_pack
from .scenarios_secops import build_dns_exfil, build_portscan_detect, build_ssh_bruteforce


def _tok(rng: random.Random, prefix: str = "OK") -> str:
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    suffix = "".join(rng.choice(chars) for _ in range(6))
    return f"{prefix}_{suffix}"


def _build_nginx_bad_gateway(rng: random.Random) -> dict[str, Any]:
    real_port = rng.choice([9015, 9025, 9040, 9055, 9070, 9085])
    wrong_port = real_port + rng.choice([3, 7, 11])
    token = _tok(rng, "PAY_LIVE")

    api_setup = f"""
mkdir -p /opt/payments /var/log/payments
cat << 'EOF' > /opt/payments/server.py
import http.server, json, os, socketserver

BIND = os.environ.get("BIND_ADDR", "127.0.0.1")
PORT = int(os.environ.get("PORT", "{real_port}"))
TOKEN = "{token}"

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/health") or self.path.startswith("/api/pay"):
            body = json.dumps({{"status": "UP", "token": TOKEN, "port": PORT}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, fmt, *args):
        pass

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer((BIND, PORT), Handler) as httpd:
    httpd.serve_forever()
EOF

cat << 'EOF' > /opt/payments/payments.env
# Configuracion de red del microservicio de pagos
BIND_ADDR=127.0.0.1
PORT={real_port}
EOF

cat << 'EOF' > /usr/local/bin/restart-payments
#!/bin/bash
set -e
pkill -f '/opt/payments/server.py' 2>/dev/null || true
sleep 0.3
set -a
source /opt/payments/payments.env
set +a
nohup python3 /opt/payments/server.py >/var/log/payments/app.log 2>&1 &
sleep 0.4
echo "payments-api reiniciado en ${{BIND_ADDR}}:${{PORT}}"
EOF
chmod +x /usr/local/bin/restart-payments
/usr/local/bin/restart-payments
"""

    proxy_setup = f"""
rm -f /etc/nginx/conf.d/*.conf
cat << 'EOF' > /etc/nginx/conf.d/payments.conf
server {{
    listen 8080;
    server_name _;

    location /health {{
        proxy_pass http://payments-api:{wrong_port}/health;
        proxy_connect_timeout 2s;
        proxy_read_timeout 3s;
    }}

    location /api/ {{
        proxy_pass http://payments-api:{wrong_port}/api/;
    }}
}}
EOF
nginx -g 'daemon off;' >/var/log/nginx/chaos.log 2>&1 &
sleep 0.5
"""

    return {
        "vars": {"real_port": real_port, "wrong_port": wrong_port, "token": token},
        "nodes": [
            {
                "role": "edge-proxy",
                "distro": "nginx",
                "shell": "/bin/sh",
                "default_user": "root",
                "setup_sh": proxy_setup,
            },
            {
                "role": "payments-api",
                "distro": "debian",
                "shell": "/bin/bash",
                "default_user": "root",
                "setup_sh": api_setup,
            },
        ],
        "checks": [
            {
                "id": "api-listen",
                "label": "payments-api acepta conexiones que llegan desde otros nodos",
                "node": "payments-api",
                "cmd": f"ss -tln | grep -E '0\\.0\\.0\\.0:{real_port}|\\*:{real_port}'",
            },
            {
                "id": "nginx-valid",
                "label": "La configuración de Nginx es válida y lleva hasta payments-api",
                "node": "edge-proxy",
                "cmd": f"nginx -t >/dev/null 2>&1 && grep -q 'payments-api:{real_port}' /etc/nginx/conf.d/payments.conf",
            },
            {
                "id": "e2e-http",
                "label": "GET http://127.0.0.1:8080/health desde edge-proxy devuelve HTTP 200 y token activo",
                "node": "edge-proxy",
                "cmd": f"wget -qO- http://127.0.0.1:8080/health | grep -q '{token}'",
            },
        ],
        "hints": [
            "Comprueba en `edge-proxy` qué devuelve `wget -S -O- http://127.0.0.1:8080/health` y revisa `/etc/nginx/conf.d/payments.conf`.",
            "Cambia a la pestaña `payments-api` y ejecuta `ss -tlnp`: fíjate tanto en el número de puerto real como en la dirección IP de escucha (`127.0.0.1` vs `0.0.0.0`).",
            f"Edita `/opt/payments/payments.env` (`BIND_ADDR=0.0.0.0`), ejecuta `restart-payments`, corrige el puerto `{real_port}` en `/etc/nginx/conf.d/payments.conf` y aplica `nginx -s reload`.",
        ],
        "topology": {
            "entry": {"label": "tú (curl)", "to": "edge-proxy", "via": "HTTP :8080 /health"},
            "nodes": {
                "edge-proxy": {"runs": "nginx · reverse proxy :8080", "look": ["/etc/nginx/conf.d/", "nginx -t", "/var/log/nginx/chaos.log"]},
                "payments-api": {"runs": "python · API de pagos", "look": ["ps aux", "/opt/payments/", "/var/log/payments/app.log"]},
            },
            "links": [
                {"from": "edge-proxy", "to": "payments-api", "via": "proxy_pass → puerto del backend"},
            ],
            "checks": {"api-listen": "node:payments-api", "nginx-valid": "link:0", "e2e-http": "entry"},
        },
        "solution_summary": (
            f"1. En `payments-api`, `/opt/payments/payments.env` forzaba `BIND_ADDR=127.0.0.1` en el puerto `{real_port}`, impidiendo conexiones externas desde `edge-proxy`. Cambiar a `BIND_ADDR=0.0.0.0` y ejecutar `restart-payments`.\n"
            f"2. En `edge-proxy`, `/etc/nginx/conf.d/payments.conf` apuntaba al puerto erróneo `{wrong_port}`. Actualizar `proxy_pass` a `http://payments-api:{real_port}` y ejecutar `nginx -s reload`."
        ),
    }


def _build_firewall_drop(rng: random.Random) -> dict[str, Any]:
    port = rng.choice([9110, 9125, 9145, 9160, 9180])
    token = _tok(rng, "METRIC_NODE")

    srv_setup = f"""
mkdir -p /opt/exporter
cat << 'EOF' > /opt/exporter/exporter.py
import http.server, socketserver

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'node_health_ok{{cluster="prod",token="{token}"}} 1\\n')
    def log_message(self, *a):
        pass

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("0.0.0.0", {port}), H) as s:
    s.serve_forever()
EOF
nohup python3 /opt/exporter/exporter.py >/var/log/exporter.log 2>&1 &
sleep 0.3

# Inyectar bloqueo silencioso de firewall excepto loopback
if iptables -L >/dev/null 2>&1; then
    iptables -I INPUT 1 -i lo -j ACCEPT
    iptables -A INPUT -p tcp --dport {port} -j REJECT --reject-with tcp-reset
elif nft list ruleset >/dev/null 2>&1; then
    nft add table inet filter
    nft 'add chain inet filter input {{ type filter hook input priority 0 ; policy accept ; }}'
    nft add rule inet filter input iifname "lo" accept
    nft add rule inet filter input tcp dport {port} reject
fi
"""

    probe_setup = f"""
mkdir -p /opt/probe
cat << 'EOF' > /opt/probe/README.txt
Objetivo: recolectar metricas HTTP desde el host 'metrics-srv' en su puerto de telemetria.
Prueba conectividad con curl, ping o ss/nc.
EOF
"""

    return {
        "vars": {"port": port, "token": token},
        "nodes": [
            {
                "role": "client-probe",
                "distro": "debian",
                "shell": "/bin/bash",
                "default_user": "root",
                "setup_sh": probe_setup,
            },
            {
                "role": "metrics-srv",
                "distro": "debian",
                "shell": "/bin/bash",
                "default_user": "root",
                "caps": ["NET_ADMIN"],
                "setup_sh": srv_setup,
            },
        ],
        "checks": [
            {
                "id": "exporter-alive",
                "label": f"Demonio exporter escuchando localmente en metrics-srv:{port}",
                "node": "metrics-srv",
                "cmd": f"curl -sf --max-time 2 http://127.0.0.1:{port}/metrics | grep -q '{token}'",
            },
            {
                "id": "fw-clean",
                "label": f"Nada en metrics-srv bloquea el tráfico TCP que llega al puerto {port}",
                "node": "metrics-srv",
                "cmd": f"! (iptables -S INPUT 2>/dev/null | grep -E 'dport {port}.*(DROP|REJECT)')",
            },
            {
                "id": "remote-scrape",
                "label": f"client-probe descarga métricas desde http://metrics-srv:{port}/metrics",
                "node": "client-probe",
                "cmd": f"curl -sf --max-time 2 http://metrics-srv:{port}/metrics | grep -q '{token}'",
            },
        ],
        "hints": [
            f"Desde `metrics-srv` prueba `curl http://127.0.0.1:{port}/metrics` y luego prueba desde `client-probe` `curl -v http://metrics-srv:{port}/metrics`. ¿Por qué recibe `Connection refused` / RST si escucha en `0.0.0.0`?",
            "En `metrics-srv` inspecciona el cortafuegos local con `iptables -L -n -v` o `nft list ruleset`.",
            f"Elimina la regla que bloquea el puerto `{port}` en `metrics-srv` (`iptables -D INPUT -p tcp --dport {port} -j REJECT --reject-with tcp-reset` o `iptables -F INPUT`).",
        ],
        "topology": {
            "entry": {"label": "tú (shell)", "to": "client-probe", "via": "curl /metrics"},
            "nodes": {
                "client-probe": {"runs": "recolector de métricas (curl)", "look": ["/opt/probe/README.txt", "getent hosts metrics-srv"]},
                "metrics-srv": {"runs": f"python · exporter de métricas :{port}", "look": ["ss -tlnp", "/opt/exporter/exporter.py", "/var/log/exporter.log"]},
            },
            "links": [
                {"from": "client-probe", "to": "metrics-srv", "via": f"HTTP :{port} /metrics"},
            ],
            "checks": {"exporter-alive": "node:metrics-srv", "fw-clean": "node:metrics-srv", "remote-scrape": "link:0"},
        },
        "solution_summary": (
            f"El proceso `exporter.py` escuchaba correctamente en `0.0.0.0:{port}`, pero una regla `REJECT` en la cadena `INPUT` de `iptables` descartaba paquetes externos mientras aceptaba `lo`. "
            f"Eliminar la regla con `iptables -D INPUT ...` restablece el scraping desde `client-probe`."
        ),
    }


def _build_acl_vault(rng: random.Random) -> dict[str, Any]:
    token = _tok(rng, "AUDIT_SEAL")
    setup = f"""
groupadd -f auditores
usermod -aG auditores alumno
mkdir -p /srv/vault/out

cat << 'EOF' > /srv/vault/close_month.sh
#!/bin/bash
set -euo pipefail
echo "{token}" > /srv/vault/out/report.ok
echo "Cierre mensual completado: {token}"
EOF

chown -R root:auditores /srv/vault
chmod 0770 /srv/vault /srv/vault/out
chmod 0770 /srv/vault/close_month.sh

# Trampa de ACLs: aunque chmod muestra rwxrwx---, las ACL bloquean a alumno y limitan mask
setfacl -m u:alumno:--- /srv/vault/close_month.sh
setfacl -m m::r-- /srv/vault/close_month.sh
setfacl -m u:alumno:r-x /srv/vault/out
"""
    return {
        "vars": {"token": token},
        "nodes": [
            {
                "role": "debian-vault",
                "distro": "debian",
                "shell": "/bin/bash",
                "default_user": "root",
                "setup_sh": setup,
            }
        ],
        "checks": [
            {
                "id": "acl-script",
                "label": "alumno puede leer y ejecutar /srv/vault/close_month.sh",
                "node": "debian-vault",
                "cmd": "su - alumno -c 'test -r /srv/vault/close_month.sh && test -x /srv/vault/close_month.sh'",
            },
            {
                "id": "acl-outdir",
                "label": "Directorio /srv/vault/out permite escritura efectiva a alumno sin sudo",
                "node": "debian-vault",
                "cmd": "su - alumno -c 'test -w /srv/vault/out'",
            },
            {
                "id": "run-as-alumno",
                "label": "Ejecutar /srv/vault/close_month.sh como usuario alumno genera /srv/vault/out/report.ok",
                "node": "debian-vault",
                "cmd": f"rm -f /srv/vault/out/report.ok && su - alumno -c '/srv/vault/close_month.sh' && grep -qx '{token}' /srv/vault/out/report.ok",
            },
        ],
        "hints": [
            "Fíjate en el signo `+` al final de los permisos en `ls -la /srv/vault /srv/vault/out`. Los permisos POSIX clásicos no cuentan toda la historia.",
            "Inspecciona las listas de control de acceso con `getfacl /srv/vault/close_month.sh /srv/vault/out`: hay entradas explícitas para `user:alumno` y una máscara (`mask::r--`) que recorta permisos de grupo.",
            "Limpia las ACLs conflictivas con `setfacl -b /srv/vault/close_month.sh /srv/vault/out` (y verifica `chmod 770`) y prueba con `su - alumno -c /srv/vault/close_month.sh`.",
        ],
        "topology": {
            "entry": None,
            "nodes": {
                "debian-vault": {"runs": "bash · script de cierre mensual", "look": ["id alumno", "ls -l /srv/vault /srv/vault/out", "/srv/vault/close_month.sh"]},
            },
            "links": [],
            "checks": {"acl-script": "node:debian-vault", "acl-outdir": "node:debian-vault", "run-as-alumno": "node:debian-vault"},
        },
        "solution_summary": (
            "Aunque `alumno` pertenecía al grupo `auditores` con modo `0770`, existían entradas ACL explícitas (`user:alumno:---` y `mask::r--`) en `/srv/vault/close_month.sh` y `user:alumno:r-x` en `/srv/vault/out`. "
            "Eliminar las ACLs anómalas con `setfacl -b` restaura los permisos efectivos del grupo `auditores`."
        ),
    }


def _build_rocky_crlf_env(rng: random.Random) -> dict[str, Any]:
    port = rng.choice([8410, 8420, 8435, 8450])
    token = _tok(rng, "BILLING_RHEL")
    setup = f"""
mkdir -p /opt/billing /etc/sysconfig /var/run/billing

cat << 'EOF' > /etc/sysconfig/billing.env
# Archivo de variables del demonio de facturacion
BILLING_PORT = {port}
BILLING_TOKEN="{token}"
RUN_DIR=/var/run/billing
EOF

cat << 'EOF' > /opt/billing/billingd.sh
#!/bin/bash
set -euo pipefail
source /etc/sysconfig/billing.env
if [ ! -w "$RUN_DIR" ]; then
    echo "RUN_DIR no escribible: $RUN_DIR" >&2
    exit 1
fi
pkill -f 'billing_http.py' 2>/dev/null || true
nohup python3 /opt/billing/billing_http.py "$BILLING_PORT" "$BILLING_TOKEN" >"$RUN_DIR/billing.log" 2>&1 &
echo $! > "$RUN_DIR/billing.pid"
EOF
sed -i 's/$/\\r/' /opt/billing/billingd.sh

cat << 'EOF' > /opt/billing/billing_http.py
import http.server, socketserver, sys
port = int(sys.argv[1])
tok = sys.argv[2]
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write((tok + "\\n").encode())
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", port), H) as s:
    s.serve_forever()
EOF

chmod 0644 /opt/billing/billingd.sh
chmod 0500 /var/run/billing
chown -R alumno:alumno /opt/billing
"""
    return {
        "vars": {"port": port, "token": token},
        "nodes": [
            {
                "role": "rocky-billing",
                "distro": "rocky",
                "shell": "/bin/bash",
                "default_user": "root",
                "setup_sh": setup,
            }
        ],
        "checks": [
            {
                "id": "no-crlf",
                "label": "/opt/billing/billingd.sh es ejecutable y Bash lo interpreta sin errores de formato",
                "node": "rocky-billing",
                "cmd": "test -x /opt/billing/billingd.sh && ! grep -q $'\\r' /opt/billing/billingd.sh",
            },
            {
                "id": "valid-env",
                "label": "/etc/sysconfig/billing.env se carga sin errores y el demonio puede escribir en su directorio de ejecución",
                "node": "rocky-billing",
                "cmd": "bash -c 'set -e; source /etc/sysconfig/billing.env && test \"$BILLING_PORT\" = \"" + str(port) + "\"' && test -w /var/run/billing",
            },
            {
                "id": "service-up",
                "label": f"Servicio de facturación activo en 127.0.0.1:{port} devolviendo el token válido",
                "node": "rocky-billing",
                "cmd": f"curl -sf --max-time 2 http://127.0.0.1:{port}/ | grep -qx '{token}'",
            },
        ],
        "hints": [
            "Intenta ejecutar `/opt/billing/billingd.sh` o revisa su formato con `file /opt/billing/billingd.sh`: fue subido desde Windows con finales de línea CRLF (`\\r\\n`).",
            "Tras limpiar CRLF (`sed -i 's/\\r$//' /opt/billing/billingd.sh` y `chmod +x`), revisa `/etc/sysconfig/billing.env`: en Bash las asignaciones no admiten espacios alrededor del `=`.",
            "Corrige `BILLING_PORT=...` sin espacios, otorga permisos de escritura a `/var/run/billing` (`chmod 0755 /var/run/billing`) y lanza `/opt/billing/billingd.sh`.",
        ],
        "topology": {
            "entry": {"label": "tú (curl)", "to": "rocky-billing", "via": f"HTTP 127.0.0.1:{port}"},
            "nodes": {
                "rocky-billing": {"runs": f"billingd.sh → python · facturación :{port}", "look": ["/opt/billing/billingd.sh", "/etc/sysconfig/billing.env", "ls -l /opt/billing /var/run/billing"]},
            },
            "links": [],
            "checks": {"no-crlf": "node:rocky-billing", "valid-env": "node:rocky-billing", "service-up": "entry"},
        },
        "solution_summary": (
            "Tres fallos encadenados tras despliegue manual en Rocky Linux 9: "
            "(1) finales de línea CRLF y falta de `+x` en `/opt/billing/billingd.sh`, "
            "(2) espacios inválidos en `BILLING_PORT = ...` dentro de `/etc/sysconfig/billing.env`, y "
            "(3) `/var/run/billing` con modo `0500` sin permiso de escritura."
        ),
    }


def _build_zombie_log_cron(rng: random.Random) -> dict[str, Any]:
    rogue_name = rng.choice(["telemetry-leak", "trace-dumper", "audit-flooder"])
    setup = f"""
mkdir -p /usr/local/libexec /var/log/ingest /etc/cron.d /var/run

cat << 'EOF' > /usr/local/libexec/core-dispatcher
#!/bin/bash
while true; do sleep 10; done
EOF

cat << 'EOF' > /usr/local/libexec/{rogue_name}
#!/bin/bash
while true; do
    head -c 65536 /dev/zero | tr '\\0' 'X' >> /var/log/ingest/overflow.log
    sleep 1
done
EOF

chmod +x /usr/local/libexec/core-dispatcher /usr/local/libexec/{rogue_name}
nohup /usr/local/libexec/core-dispatcher >/dev/null 2>&1 &
echo $! > /var/run/core-dispatcher.orig.pid

nohup /usr/local/libexec/{rogue_name} >/dev/null 2>&1 &

cat << 'EOF' > /etc/cron.d/ingest-watchdog
# Watchdog de recoleccion
* * * * * root pgrep -f /usr/local/libexec/{rogue_name} >/dev/null || nohup /usr/local/libexec/{rogue_name} >/dev/null 2>&1 &
EOF
cron 2>/dev/null || true
sleep 1.2
"""
    return {
        "vars": {"rogue_name": rogue_name},
        "nodes": [
            {
                "role": "debian-storage",
                "distro": "debian",
                "shell": "/bin/bash",
                "default_user": "root",
                "setup_sh": setup,
            }
        ],
        "checks": [
            {
                "id": "cron-disarmed",
                "label": "La persistencia que revivía al proceso fugitivo está desactivada",
                "node": "debian-storage",
                "cmd": f"! grep -Eq '^[^#].*{rogue_name}' /etc/cron.d/* 2>/dev/null",
            },
            {
                "id": "rogue-stopped-truncated",
                "label": "Proceso fugitivo detenido y /var/log/ingest/overflow.log truncado (<1 KB) sin borrarlo",
                "node": "debian-storage",
                "cmd": f"! pgrep -f '/usr/local/libexec/[{rogue_name[0]}]{rogue_name[1:]}' >/dev/null && test -f /var/log/ingest/overflow.log && [ $(wc -c < /var/log/ingest/overflow.log) -lt 1024 ]",
            },
            {
                "id": "core-untouched",
                "label": "El worker crítico core-dispatcher mantiene su PID original intacto (sin reinicios)",
                "node": "debian-storage",
                "cmd": "kill -0 $(cat /var/run/core-dispatcher.orig.pid) 2>/dev/null",
            },
        ],
        "hints": [
            "Usa `ps aux` y `ls -lh /var/log/ingest/` para identificar qué binario está inflando `overflow.log`, teniendo cuidado de NO matar `core-dispatcher`.",
            "¡Ojo! Antes o justo después de matar el proceso fugitivo, revisa `/etc/cron.d/`: hay un watchdog de cron que lo relanza cada minuto.",
            f"Elimina o comenta `/etc/cron.d/ingest-watchdog`, mata únicamente `{rogue_name}` (`pkill -f {rogue_name}`) y trunca el archivo en caliente con `truncate -s 0 /var/log/ingest/overflow.log` (o `: > /var/log/ingest/overflow.log`).",
        ],
        "topology": {
            "entry": None,
            "nodes": {
                "debian-storage": {"runs": "core-dispatcher (no reiniciar) · logs", "look": ["df -h /var/log", "du -sh /var/log/ingest", "top", "/var/run/core-dispatcher.orig.pid"]},
            },
            "links": [],
            "checks": {"cron-disarmed": "node:debian-storage", "rogue-stopped-truncated": "node:debian-storage", "core-untouched": "node:debian-storage"},
        },
        "solution_summary": (
            f"1. Desactivar el cron `/etc/cron.d/ingest-watchdog` que resucitaba `{rogue_name}` cada minuto.\n"
            f"2. Detener exclusivamente `{rogue_name}` preservando el PID original de `core-dispatcher`.\n"
            "3. Truncar `/var/log/ingest/overflow.log` a 0 bytes sin eliminar el inodo."
        ),
    }


def _build_dns_redis_split(rng: random.Random) -> dict[str, Any]:
    rpass = _tok(rng, "RPASS")
    val_tok = _tok(rng, "SESSION_OK")

    redis_setup = f"""
cat << 'EOF' > /tmp/redis-chaos.conf
bind 0.0.0.0
port 6379
requirepass {rpass}
protected-mode no
EOF
redis-server /tmp/redis-chaos.conf --daemonize yes
sleep 0.4
redis-cli -a "{rpass}" SET chaos:health "{val_tok}" >/dev/null 2>&1
"""

    app_setup = f"""
# Desviar cache.internal a una IP loopback equivocada en /etc/hosts
echo "127.0.0.1 cache.internal" >> /etc/hosts

mkdir -p /opt/app
cat << 'EOF' > /opt/app/cache.conf
REDIS_HOST=cache.internal
REDIS_PORT=6380
REDIS_PASSWORD=OLD_EXPIRED_PASS
EOF

cat << 'EOF' > /usr/local/bin/rcli
#!/usr/bin/env python3
import socket, sys

host, port, pw, cmd = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4:]
with socket.create_connection((host, port), timeout=2.5) as s:
    def send(parts):
        buf = f"*{{len(parts)}}\\r\\n".encode()
        for p in parts:
            b = p.encode()
            buf += f"${{len(b)}}\\r\\n".encode() + b + b"\\r\\n"
        s.sendall(buf)
        return s.recv(4096).decode(errors="replace")
    if pw:
        r = send(["AUTH", pw])
        if r.startswith("-"):
            print(r.strip(), file=sys.stderr)
            sys.exit(2)
    out = send(cmd)
    if out.startswith("-"):
        print(out.strip(), file=sys.stderr)
        sys.exit(3)
    print(out.strip())
EOF
chmod +x /usr/local/bin/rcli

cat << 'EOF' > /opt/app/healthcheck.sh
#!/bin/bash
set -euo pipefail
source /opt/app/cache.conf
rcli "$REDIS_HOST" "$REDIS_PORT" "$REDIS_PASSWORD" GET chaos:health
EOF
chmod +x /opt/app/healthcheck.sh
"""

    return {
        "vars": {"rpass": rpass, "val_tok": val_tok},
        "nodes": [
            {
                "role": "app-node",
                "distro": "debian",
                "shell": "/bin/bash",
                "default_user": "root",
                "setup_sh": app_setup,
            },
            {
                "role": "redis-cache",
                "distro": "redis",
                "shell": "/bin/sh",
                "default_user": "root",
                "setup_sh": redis_setup,
            },
        ],
        "checks": [
            {
                "id": "dns-resolution",
                "label": "Desde app-node, cache.internal resuelve primero a la IP de redis-cache",
                "node": "app-node",
                "cmd": "source /etc/chaos_nodes.env && getent hosts cache.internal | awk 'NR==1{print $1}' | grep -qx \"$IP_REDIS_CACHE\"",
            },
            {
                "id": "conf-updated",
                "label": "Los parámetros de conexión de /opt/app/cache.conf coinciden con el Redis activo",
                "node": "app-node",
                "cmd": f"source /opt/app/cache.conf && [ \"$REDIS_PORT\" = \"6379\" ] && [ \"$REDIS_PASSWORD\" = \"{rpass}\" ]",
            },
            {
                "id": "healthcheck-ok",
                "label": "/opt/app/healthcheck.sh recupera la clave testigo desde Redis",
                "node": "app-node",
                "cmd": f"/opt/app/healthcheck.sh | grep -q '{val_tok}'",
            },
        ],
        "hints": [
            "Ejecuta `/opt/app/healthcheck.sh` en `app-node`. Primero verás `Connection refused`: revisa a qué IP resuelve `cache.internal` (`getent hosts cache.internal`, `/etc/hosts`) comparándola con la IP de `redis-cache` (`ip a` en la pestaña `redis-cache` o `dig redis-cache`).",
            "En la pestaña `redis-cache`, revisa cómo arrancó Redis (`ps aux` y `/tmp/redis-chaos.conf`) para ver el puerto real y la directiva `requirepass`.",
            "Apunta `cache.internal` en `/etc/hosts` a la IP de `redis-cache` (edítalo con `nano` o `vim`: en un contenedor `/etc/hosts` está montado y `sed -i` falla con «Device or resource busy»), actualiza `REDIS_PORT=6379` y `REDIS_PASSWORD` en `/opt/app/cache.conf`, y verifica con `/opt/app/healthcheck.sh`.",
        ],
        "topology": {
            "entry": {"label": "tú (shell)", "to": "app-node", "via": "/opt/app/healthcheck.sh"},
            "nodes": {
                "app-node": {"runs": "bash · healthcheck.sh (cliente rcli)", "look": ["/opt/app/healthcheck.sh", "/opt/app/cache.conf", "/etc/chaos_nodes.env"]},
                "redis-cache": {"runs": "redis-server · caché de sesiones", "look": ["ss -tlnp", "redis-cli ping"]},
            },
            "links": [
                {"from": "app-node", "to": "redis-cache", "via": "TCP cache.internal → Redis"},
            ],
            "checks": {"dns-resolution": "node:app-node", "conf-updated": "node:app-node", "healthcheck-ok": "link:0"},
        },
        "solution_summary": (
            "1. `/etc/hosts` en `app-node` secuestraba `cache.internal` hacia `127.0.0.1` en lugar de la IP del nodo `redis-cache`.\n"
            f"2. `/opt/app/cache.conf` tenía puerto `6380` (en vez de `6379`) y una contraseña caducada en lugar de `{rpass}`."
        ),
    }


def _build_sudoers_lockout(rng: random.Random) -> dict[str, Any]:
    token = _tok(rng, "DEPLOY_AUTH")
    setup = f"""
cat << 'EOF' > /usr/local/bin/deploy-check
#!/bin/bash
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: requiere privilegios root via sudo" >&2
    exit 1
fi
echo "{token}"
EOF
chmod 0755 /usr/local/bin/deploy-check

# Romper cuenta alumno y sudoers
rm -f /etc/sudoers.d/lpi-alumno /etc/sudoers.d/alumno
# Sudoers corrupto (falta dos puntos tras NOPASSWD y permisos 0666 inseguros)
echo "alumno ALL=(ALL) NOPASSWD /usr/local/bin/deploy-check" > /etc/sudoers.d/90-ops
chmod 0666 /etc/sudoers.d/90-ops

usermod -s /usr/sbin/nologin alumno
passwd -l alumno >/dev/null 2>&1 || true
"""
    return {
        "vars": {"token": token},
        "nodes": [
            {
                "role": "debian-sec",
                "distro": "debian",
                "shell": "/bin/bash",
                "default_user": "root",
                "setup_sh": setup,
            }
        ],
        "checks": [
            {
                "id": "sudoers-valid",
                "label": "La configuración de sudo es válida y /etc/sudoers.d/90-ops tiene permisos seguros",
                "node": "debian-sec",
                "cmd": "visudo -cf /etc/sudoers >/dev/null 2>&1 && [ \"$(stat -c '%a' /etc/sudoers.d/90-ops)\" = \"440\" ]",
            },
            {
                "id": "user-unlocked",
                "label": "La cuenta alumno está desbloqueada y puede abrir una sesión interactiva",
                "node": "debian-sec",
                "cmd": "sh=$(getent passwd alumno | cut -d: -f7) && grep -qx \"$sh\" /etc/shells && ! passwd -S alumno | awk '{print $2}' | grep -q 'L'",
            },
            {
                "id": "sudo-exec",
                "label": "alumno ejecuta 'sudo -n /usr/local/bin/deploy-check' sin contraseña con éxito",
                "node": "debian-sec",
                "cmd": f"su - alumno -c 'sudo -n /usr/local/bin/deploy-check' | grep -qx '{token}'",
            },
        ],
        "hints": [
            "Estás en consola de emergencia como `root`. Ejecuta `visudo -c` para diagnosticar por qué `sudo` rechaza `/etc/sudoers.d/90-ops`.",
            "En `sudoers`, `NOPASSWD:` lleva dos puntos obligatorios y los archivos en `/etc/sudoers.d/` exigen permisos `0440`. Además, revisa `getent passwd alumno` y `passwd -S alumno`.",
            "Corrige `/etc/sudoers.d/90-ops` a `alumno ALL=(ALL) NOPASSWD: /usr/local/bin/deploy-check`, aplica `chmod 0440 /etc/sudoers.d/90-ops`, restaura shell `usermod -s /bin/bash alumno` y desbloquea con `passwd -u alumno`.",
        ],
        "topology": {
            "entry": None,
            "nodes": {
                "debian-sec": {"runs": "sudo · deploy-check (rescate root)", "look": ["ls -l /etc/sudoers.d", "/etc/sudoers.d/90-ops", "/etc/passwd", "su - alumno"]},
            },
            "links": [],
            "checks": {"sudoers-valid": "node:debian-sec", "user-unlocked": "node:debian-sec", "sudo-exec": "node:debian-sec"},
        },
        "solution_summary": (
            "1. Corregir el error sintáctico `NOPASSWD:` en `/etc/sudoers.d/90-ops` y ajustar permisos a `0440`.\n"
            "2. Restaurar la shell `/bin/bash` (`usermod -s /bin/bash alumno`) y desbloquear la cuenta (`passwd -u alumno`)."
        ),
    }


def _build_routing_blackhole(rng: random.Random) -> dict[str, Any]:
    oct2 = rng.choice([44, 66, 77, 88, 99])
    subnet = f"10.{oct2}.88.0/24"
    vip = f"10.{oct2}.88.1"
    token = _tok(rng, "BGP_EDGE")

    branch_setup = f"""
ip addr add {vip}/32 dev lo
cat << 'EOF' > /tmp/branch_api.py
import http.server, socketserver
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{token}\\n")
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("{vip}", 8090), H) as s:
    s.serve_forever()
EOF
nohup python3 /tmp/branch_api.py >/var/log/branch.log 2>&1 &
sleep 0.3
"""

    gw_setup = f"""
# Inyectar ruta blackhole hacia la subred loopback remota de branch-srv
ip route add blackhole {subnet}
"""

    return {
        "vars": {"subnet": subnet, "vip": vip, "token": token},
        "nodes": [
            {
                "role": "gateway-rtr",
                "distro": "debian",
                "shell": "/bin/bash",
                "default_user": "root",
                "caps": ["NET_ADMIN"],
                "setup_sh": gw_setup,
            },
            {
                "role": "branch-srv",
                "distro": "debian",
                "shell": "/bin/bash",
                "default_user": "root",
                "caps": ["NET_ADMIN"],
                "setup_sh": branch_setup,
            },
        ],
        "checks": [
            {
                "id": "no-blackhole",
                "label": f"gateway-rtr ya no descarta el tráfico hacia {subnet}",
                "node": "gateway-rtr",
                "cmd": f"! (ip route show | grep -E 'blackhole {subnet}')",
            },
            {
                "id": "route-via-branch",
                "label": f"gateway-rtr enruta {subnet} a través de branch-srv",
                "node": "gateway-rtr",
                "cmd": f"source /etc/chaos_nodes.env && ip route get {vip} | grep -q \"via $IP_BRANCH_SRV\"",
            },
            {
                "id": "reach-vip",
                "label": f"gateway-rtr alcanza el servicio en http://{vip}:8090/",
                "node": "gateway-rtr",
                "cmd": f"curl -sf --max-time 2 http://{vip}:8090/ | grep -qx '{token}'",
            },
        ],
        "hints": [
            f"El servicio escucha en la IP virtual `{vip}:8090` (configurada en `lo` dentro de `branch-srv`). Prueba `ip route show` e `ip route get {vip}` desde `gateway-rtr`.",
            f"Verás una ruta `blackhole {subnet}` bloqueando los paquetes en `gateway-rtr`. Además, averigua la IP de red de `branch-srv` (`ping -c1 branch-srv` o `ip -4 addr` en `branch-srv`).",
            f"Ejecuta en `gateway-rtr`: `ip route del blackhole {subnet}` seguido de `ip route add {subnet} via <IP_DE_BRANCH_SRV>` y comprueba con `curl http://{vip}:8090/`.",
        ],
        "topology": {
            "entry": {"label": "tú (curl)", "to": "gateway-rtr", "via": f"HTTP {vip}:8090"},
            "nodes": {
                "gateway-rtr": {"runs": "router Linux · cliente HTTP", "look": [f"ping -c1 {vip}", "/etc/chaos_nodes.env", "ip -br addr"]},
                "branch-srv": {"runs": f"python · API {vip}:8090 (en lo)", "look": ["ip addr show lo", "ss -tlnp", "/var/log/branch.log"]},
            },
            "links": [
                {"from": "gateway-rtr", "to": "branch-srv", "via": f"IPv4 → subred {subnet}"},
            ],
            "checks": {"no-blackhole": "node:gateway-rtr", "route-via-branch": "link:0", "reach-vip": "entry"},
        },
        "solution_summary": (
            f"En `gateway-rtr` existía una ruta `blackhole {subnet}` que descartaba el tráfico hacia la VIP `{vip}` alojada en `branch-srv`. "
            f"Eliminar la ruta blackhole y añadir `ip route add {subnet} via <IP_BRANCH_SRV>` restablece el enrutamiento L3."
        ),
    }


def _build_nginx_vhost_collision(rng: random.Random) -> dict[str, Any]:
    token = _tok(rng, "PORTAL_V2")
    setup = f"""
rm -f /etc/nginx/conf.d/*.conf
mkdir -p /var/www/portal /var/www/maint

echo "MODO_MANTENIMIENTO_FANTASMA" > /var/www/maint/index.html
echo "{token}" > /var/www/portal/index.html

# Permisos rotos para el worker nginx
chown -R root:root /var/www/portal
chmod 0700 /var/www/portal
chmod 0600 /var/www/portal/index.html

# Vhost trampa que captura con server_name exacto o wildcard conflictivo + portal mal configurado
cat << 'EOF' > /etc/nginx/conf.d/00-trap.conf
server {{
    listen 80 default_server;
    server_name portal.corp.local _;
    root /var/www/maint;
    index index.html;
}}
EOF

cat << 'EOF' > /etc/nginx/conf.d/10-portal.conf
server {{
    listen 80;
    server_name portal.corp.local;
    root /var/www/portal;
    index index.html;

    location / {{
        return 503;
    }}
}}
EOF
nginx -g 'daemon off;' >/var/log/nginx/chaos.log 2>&1 &
sleep 0.5
"""
    return {
        "vars": {"token": token},
        "nodes": [
            {
                "role": "nginx-vhost",
                "distro": "nginx",
                "shell": "/bin/sh",
                "default_user": "root",
                "setup_sh": setup,
            }
        ],
        "checks": [
            {
                "id": "nginx-syntax",
                "label": "Configuración de Nginx sin colisiones de server_name y sintaxis OK",
                "node": "nginx-vhost",
                "cmd": "nginx -t >/dev/null 2>&1 && ! (nginx -T 2>&1 | grep -q 'conflicting server name')",
            },
            {
                "id": "docroot-perms",
                "label": "Permisos de /var/www/portal accesibles por el proceso worker de Nginx",
                "node": "nginx-vhost",
                "cmd": "su -s /bin/sh nginx -c 'test -r /var/www/portal/index.html'",
            },
            {
                "id": "vhost-serves",
                "label": "Host: portal.corp.local responde HTTP 200 con el contenido real del portal",
                "node": "nginx-vhost",
                "cmd": f"wget -qO- --header='Host: portal.corp.local' http://127.0.0.1/ | grep -qx '{token}'",
            },
        ],
        "hints": [
            "Ejecuta `nginx -t`: verás un warning de `conflicting server name \"portal.corp.local\"`. Revisa todos los archivos en `/etc/nginx/conf.d/`.",
            "Además del conflicto en `00-trap.conf`, revisa `10-portal.conf` (tiene un `return 503;` harcodeado) y los permisos de `/var/www/portal` (`ls -ld /var/www/portal /var/www/portal/index.html`).",
            "Quita `portal.corp.local` de `00-trap.conf`, cambia `return 503;` por `try_files $uri $uri/ =404;` en `10-portal.conf`, aplica `chmod 755 /var/www/portal && chmod 644 /var/www/portal/index.html` y recarga con `nginx -s reload`.",
        ],
        "topology": {
            "entry": {"label": "tú (curl)", "to": "nginx-vhost", "via": "HTTP :80 Host: portal.corp.local"},
            "nodes": {
                "nginx-vhost": {"runs": "nginx · vhost portal.corp.local :80", "look": ["nginx -T", "/var/www/portal", "/var/log/nginx/chaos.log"]},
            },
            "links": [],
            "checks": {"nginx-syntax": "node:nginx-vhost", "docroot-perms": "node:nginx-vhost", "vhost-serves": "entry"},
        },
        "solution_summary": (
            "1. `00-trap.conf` declaraba `server_name portal.corp.local _;`, robando las peticiones antes que `10-portal.conf`.\n"
            "2. `10-portal.conf` forzaba `return 503;` en `location /`.\n"
            "3. `/var/www/portal` tenía modo `0700` (`root:root`), produciendo `403 Forbidden` para el usuario worker `nginx`."
        ),
    }


def _build_boss_cascade(rng: random.Random) -> dict[str, Any]:
    api_port = rng.choice([8610, 8620, 8640])
    token = _tok(rng, "CASCADE_CLEAR")

    db_setup = """
cat << 'EOF' > /tmp/redis-boss.conf
bind 0.0.0.0
port 6379
protected-mode no
# Nodo quedado enganchado como replica de solo lectura tras failover fallido
replicaof 10.254.254.254 6379
replica-read-only yes
EOF
redis-server /tmp/redis-boss.conf --daemonize yes
sleep 0.4
"""

    api_setup = f"""
mkdir -p /opt/core
cat << 'EOF' > /opt/core/core.env
DB_HOST=vault-db
DB_PORT=6379
API_PORT={api_port}
RELEASE_TOKEN={token}
EOF

cat << 'EOF' > /opt/core/app.py
import http.server, json, os, socket, socketserver

DB_HOST = os.environ.get("DB_HOST", "vault-db")
DB_PORT = int(os.environ.get("DB_PORT", "6379"))
API_PORT = int(os.environ.get("API_PORT", "{api_port}"))
TOKEN = os.environ.get("RELEASE_TOKEN", "{token}")

def redis_cmd(*parts):
    with socket.create_connection((DB_HOST, DB_PORT), timeout=2.0) as s:
        buf = f"*{{len(parts)}}\\r\\n".encode()
        for p in parts:
            b = str(p).encode()
            buf += f"${{len(b)}}\\r\\n".encode() + b + b"\\r\\n"
        s.sendall(buf)
        return s.recv(4096).decode(errors="replace")

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/tx"):
            try:
                w = redis_cmd("SET", "tx:last", TOKEN)
                if w.startswith("-"):
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(("DB_WRITE_ERR: " + w).encode())
                    return
                r = redis_cmd("GET", "tx:last")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({{"ok": True, "tx": TOKEN, "raw": r.strip()}}).encode())
            except Exception as e:
                self.send_response(502)
                self.end_headers()
                self.wfile.write(f"DB_CONN_ERR: {{e}}".encode())
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, *a): pass

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("0.0.0.0", API_PORT), H) as srv:
    srv.serve_forever()
EOF

set -a
source /opt/core/core.env
set +a
nohup python3 /opt/core/app.py >/var/log/core-api.log 2>&1 &
sleep 0.3

# Fallo 2: regla OUTPUT en core-api bloqueando salida TCP hacia 6379
iptables -A OUTPUT -p tcp --dport 6379 -j REJECT --reject-with tcp-reset
"""

    edge_setup = f"""
rm -f /etc/nginx/conf.d/*.conf
# Fallo 1: upstream apunta a un host mal escrito 'core-api-legacy'
cat << 'EOF' > /etc/nginx/conf.d/edge.conf
server {{
    listen 8080;
    server_name _;

    location /api/ {{
        proxy_pass http://127.0.0.1:{api_port}/api/;
        proxy_connect_timeout 2s;
    }}
}}
EOF
nginx -g 'daemon off;' >/var/log/nginx/chaos.log 2>&1 &
sleep 0.5
"""

    return {
        "vars": {"api_port": api_port, "token": token},
        "nodes": [
            {
                "role": "edge-lb",
                "distro": "nginx",
                "shell": "/bin/sh",
                "default_user": "root",
                "setup_sh": edge_setup,
            },
            {
                "role": "core-api",
                "distro": "debian",
                "shell": "/bin/bash",
                "default_user": "root",
                "caps": ["NET_ADMIN"],
                "setup_sh": api_setup,
            },
            {
                "role": "vault-db",
                "distro": "redis",
                "shell": "/bin/sh",
                "default_user": "root",
                "setup_sh": db_setup,
            },
        ],
        "checks": [
            {
                "id": "db-writable",
                "label": "vault-db acepta escrituras",
                "node": "vault-db",
                "cmd": "redis-cli INFO replication | grep -q 'role:master'",
            },
            {
                "id": "api-egress",
                "label": "core-api llega a vault-db (TCP :6379)",
                "node": "core-api",
                "cmd": f"curl -sf --max-time 2 http://127.0.0.1:{api_port}/api/tx | grep -q '{token}'",
            },
            {
                "id": "edge-upstream",
                "label": "edge-lb hace llegar /api/ hasta core-api",
                "node": "edge-lb",
                "cmd": f"nginx -t >/dev/null 2>&1 && grep -q 'core-api:{api_port}' /etc/nginx/conf.d/edge.conf",
            },
            {
                "id": "full-tx",
                "label": "Transacción end-to-end GET http://127.0.0.1:8080/api/tx en edge-lb devuelve HTTP 200",
                "node": "edge-lb",
                "cmd": f"wget -qO- http://127.0.0.1:8080/api/tx | grep -q '{token}'",
            },
        ],
        "hints": [
            "Sigue el recorrido de la petición capa por capa: `edge-lb (:8080)` -> `core-api` -> `vault-db (:6379)`. En `edge-lb`, mira a dónde apunta `proxy_pass` en `/etc/nginx/conf.d/edge.conf`.",
            "En `core-api`, prueba `curl -i http://127.0.0.1:" + str(api_port) + "/api/tx`. Primero verás `DB_CONN_ERR` (revisa `iptables -S OUTPUT`). Cuando abras el firewall, verás `READONLY You can't write against a read only replica`.",
            "Promueve `vault-db` a primario con `redis-cli REPLICAOF NO ONE` (y actualiza `/tmp/redis-boss.conf` si quieres), limpia `iptables -F OUTPUT` en `core-api`, y apunta `edge-lb` a `http://core-api:" + str(api_port) + "/api/` con `nginx -s reload`.",
        ],
        "topology": {
            "entry": {"label": "tú (curl)", "to": "edge-lb", "via": "HTTP :8080 /api/tx"},
            "nodes": {
                "edge-lb": {"runs": "nginx · balanceador :8080", "look": ["/etc/nginx/conf.d/", "nginx -t", "/var/log/nginx/chaos.log"]},
                "core-api": {"runs": "python · API transaccional", "look": ["ss -tlnp", "/var/log/core-api.log", "ss -tnp"]},
                "vault-db": {"runs": "redis :6379", "look": ["redis-cli SET prueba 1", "ps aux"]},
            },
            "links": [
                {"from": "edge-lb", "to": "core-api", "via": "proxy_pass /api/"},
                {"from": "core-api", "to": "vault-db", "via": "TCP :6379 (lee y escribe)"},
            ],
            "checks": {"edge-upstream": "link:0", "api-egress": "link:1", "db-writable": "node:vault-db", "full-tx": "entry"},
        },
        "solution_summary": (
            f"Incidente triple en cascada:\n"
            f"1. `edge-lb`: `/etc/nginx/conf.d/edge.conf` apuntaba a `127.0.0.1:{api_port}` en lugar de `http://core-api:{api_port}`.\n"
            "2. `core-api`: una regla `iptables OUTPUT` bloqueaba el puerto destino `6379`.\n"
            "3. `vault-db`: Redis estaba bloqueado como réplica de solo lectura (`replicaof 10.254.254.254 6379`); promover con `redis-cli REPLICAOF NO ONE`."
        ),
    }


def _build_wireguard_overlay(rng: random.Random) -> dict[str, Any]:
    real_port = rng.choice([51820, 51825, 51830])
    wrong_port = real_port + 10
    subnet_oct = rng.choice([77, 88, 99])
    token = _tok(rng, "WG_TUNNEL")

    branch_setup = f"""
mkdir -p /etc/wireguard /opt/intranet
echo "PUBKEY_BRANCH_9F3A21C0" > /etc/wireguard/branch.pub
echo "PUBKEY_HQ_4D88B1E2" > /etc/wireguard/hq.pub

ip link add wg0 type vxlan id 100 remote "${{IP_HQ_VPN_GW}}" local "${{IP_BRANCH_VPN_GW}}" dstport 4789 2>/dev/null || ip link add wg0 type dummy
ip link set wg0 mtu 1420 up
ip addr add 10.{subnet_oct}.0.2/24 dev wg0

cat << 'EOF' > /opt/intranet/api.py
import http.server, socketserver

PAYLOAD = ("WG_OK:{token}:" + ("X" * 2200)).encode()

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(PAYLOAD)
    def log_message(self, *a): pass

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("10.{subnet_oct}.0.2", 8440), H) as srv:
    srv.serve_forever()
EOF
nohup python3 /opt/intranet/api.py >/var/log/branch-api.log 2>&1 &
sleep 0.3
"""

    hq_setup = f"""
mkdir -p /etc/wireguard
echo "PUBKEY_BRANCH_9F3A21C0" > /etc/wireguard/branch.pub
echo "PUBKEY_HQ_4D88B1E2" > /etc/wireguard/hq.pub

# Configuracion rota: puerto de Endpoint equivocado, AllowedIPs en /32 erronea y MTU gigante (1580 > 1420)
cat << EOF > /etc/wireguard/wg0.conf
[Interface]
PrivateKey = PRIVKEY_HQ_REDACTED
Address = 10.{subnet_oct}.0.1/24
MTU = 1580

[Peer]
PublicKey = PUBKEY_BRANCH_9F3A21C0
Endpoint = ${{IP_BRANCH_VPN_GW}}:{wrong_port}
AllowedIPs = 10.{subnet_oct}.99.2/32
PersistentKeepalive = 25
EOF

cat << 'EOF' > /usr/local/bin/wg-apply
#!/bin/bash
set -e
source /etc/chaos_nodes.env
CONF="/etc/wireguard/wg0.conf"
PORT_CFG=$(grep -E '^Endpoint\\s*=' "$CONF" | awk -F: '{{print $2}}' | tr -d ' ')
ALLOWED=$(grep -E '^AllowedIPs\\s*=' "$CONF" | awk -F= '{{print $2}}' | tr -d ' ')
MTU_CFG=$(grep -E '^MTU\\s*=' "$CONF" | awk -F= '{{print $2}}' | tr -d ' ')
PUB_CFG=$(grep -E '^PublicKey\\s*=' "$CONF" | awk -F= '{{print $2}}' | tr -d ' ')

ip link del wg0 2>/dev/null || true
iptables -F OUTPUT 2>/dev/null || true

if [ "$PUB_CFG" != "PUBKEY_BRANCH_9F3A21C0" ]; then
    echo "ERROR: PublicKey del peer no coincide con /etc/wireguard/branch.pub" >&2
    exit 1
fi

if [ "$PORT_CFG" != "{real_port}" ]; then
    # Simula handshake fallido creando interfaz sin peer valido
    ip link add wg0 type dummy
    ip link set wg0 mtu "${{MTU_CFG:-1420}}" up
    ip addr add 10.{subnet_oct}.0.1/32 dev wg0
    echo "WARN: Handshake UDP hacia puerto ${{PORT_CFG}} sin respuesta (el peer escucha en {real_port})"
    exit 0
fi

ip link add wg0 type vxlan id 100 remote "${{IP_BRANCH_VPN_GW}}" local "${{IP_HQ_VPN_GW}}" dstport 4789
ip link set wg0 mtu "${{MTU_CFG:-1420}}" up
ip addr add 10.{subnet_oct}.0.1/32 dev wg0
ip route replace "$ALLOWED" dev wg0

# Si el MTU supera 1420, los paquetes grandes con DF caen en el tunel
if [ "${{MTU_CFG:-1420}}" -gt 1420 ]; then
    iptables -A OUTPUT -o wg0 -p tcp -m length --length 1400:65535 -j DROP
fi
echo "OK: wg0 aplicado (Endpoint OK, ruta $ALLOWED, MTU ${{MTU_CFG}})"
EOF
chmod +x /usr/local/bin/wg-apply
/usr/local/bin/wg-apply || true
"""

    return {
        "vars": {"real_port": real_port, "subnet_oct": subnet_oct, "token": token},
        "nodes": [
            {
                "role": "hq-vpn-gw",
                "distro": "debian",
                "shell": "/bin/bash",
                "default_user": "root",
                "caps": ["NET_ADMIN"],
                "setup_sh": hq_setup,
            },
            {
                "role": "branch-vpn-gw",
                "distro": "debian",
                "shell": "/bin/bash",
                "default_user": "root",
                "caps": ["NET_ADMIN"],
                "setup_sh": branch_setup,
            },
        ],
        "checks": [
            {
                "id": "wg-endpoint",
                "label": f"El Endpoint de wg0.conf llega al peer y hay ruta hacia la intranet 10.{subnet_oct}.0.2",
                "node": "hq-vpn-gw",
                "cmd": f"grep -q ':{real_port}' /etc/wireguard/wg0.conf && ip route show | grep -qE '10\\.{subnet_oct}\\.0\\.(0/24|2)'",
            },
            {
                "id": "wg-mtu",
                "label": "La MTU de wg0 cabe dentro del túnel",
                "node": "hq-vpn-gw",
                "cmd": "mtu=$(cat /sys/class/net/wg0/mtu 2>/dev/null || echo 9999); [ \"$mtu\" -le 1420 ]",
            },
            {
                "id": "wg-payload",
                "label": f"Descarga de payload grande (>2 KB) desde http://10.{subnet_oct}.0.2:8440 completa sin bloqueo MTU",
                "node": "hq-vpn-gw",
                "cmd": f"curl -sf --max-time 3 http://10.{subnet_oct}.0.2:8440/ | grep -q '{token}'",
            },
        ],
        "hints": [
            "Revisa `/etc/wireguard/wg0.conf` en `hq-vpn-gw` y ejecuta `wg-apply` para ver los avisos de handshake, `AllowedIPs` y `MTU`.",
            f"Comprueba la IP interna del nodo remoto en `branch-vpn-gw` (`ip -4 addr show wg0` -> `10.{subnet_oct}.0.2/24`). En `wg0.conf`, `AllowedIPs` apuntaba a una subred `.99.2/32` inexistente.",
            f"Ajusta `Endpoint = <IP_BRANCH>:{real_port}`, `AllowedIPs = 10.{subnet_oct}.0.0/24` y `MTU = 1420` en `/etc/wireguard/wg0.conf`, y aplica con `wg-apply`.",
        ],
        "topology": {
            "entry": {"label": "tú (curl)", "to": "hq-vpn-gw", "via": f"HTTP 10.{subnet_oct}.0.2:8440"},
            "nodes": {
                "hq-vpn-gw": {"runs": "wg0 (sede) · se aplica con wg-apply", "look": ["/etc/wireguard/wg0.conf", "ip route", "/etc/chaos_nodes.env"]},
                "branch-vpn-gw": {"runs": f"wg0 (sucursal) · intranet :8440", "look": ["ip link show wg0", "ss -tlnp", "/var/log/branch-api.log"]},
            },
            "links": [
                {"from": "hq-vpn-gw", "to": "branch-vpn-gw", "via": "túnel wg0 (UDP) → HTTP :8440"},
            ],
            "checks": {"wg-endpoint": "link:0", "wg-mtu": "node:hq-vpn-gw", "wg-payload": "entry"},
        },
        "solution_summary": (
            f"1. `Endpoint` en `/etc/wireguard/wg0.conf` apuntaba al puerto `{wrong_port}` en vez de `{real_port}`.\n"
            f"2. `AllowedIPs` enrutaba `10.{subnet_oct}.99.2/32` en lugar de `10.{subnet_oct}.0.0/24`.\n"
            "3. `MTU = 1580` descartaba respuestas TCP grandes (>1400B); bajar `MTU = 1420` y ejecutar `wg-apply` restaura el túnel."
        ),
    }


def _build_tls_expired_san(rng: random.Random) -> dict[str, Any]:
    tls_port = rng.choice([8443, 9443])
    token = _tok(rng, "TLS_MTLS")

    gw_setup = f"""
mkdir -p /etc/ssl/corp-ca /opt/tls
# Crear CA corporativa valida
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout /etc/ssl/corp-ca/ca.key \
  -out /etc/ssl/corp-ca/ca.crt \
  -days 3650 -subj "/CN=Corp Internal Root CA" >/dev/null 2>&1

# Crear certificado de servidor ROTO: CN/SAN equivocado (legacy-vault.corp.internal)
openssl req -newkey rsa:2048 -nodes \
  -keyout /opt/tls/server.key \
  -out /opt/tls/server.csr \
  -subj "/CN=legacy-vault.corp.internal" >/dev/null 2>&1

cat << 'EOF' > /opt/tls/bad_ext.cnf
subjectAltName = DNS:legacy-vault.corp.internal
EOF

openssl x509 -req -in /opt/tls/server.csr \
  -CA /etc/ssl/corp-ca/ca.crt -CAkey /etc/ssl/corp-ca/ca.key -CAcreateserial \
  -out /opt/tls/server.crt -days 365 -extfile /opt/tls/bad_ext.cnf >/dev/null 2>&1

chmod 0644 /etc/ssl/corp-ca/ca.crt

cat << 'EOF' > /opt/tls/https_srv.py
import http.server, json, ssl, socketserver

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/ca.crt":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(open("/etc/ssl/corp-ca/ca.crt", "rb").read())
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({{"tls": "verified", "token": "{token}"}}).encode())
    def log_message(self, *a): pass

ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain("/opt/tls/server.crt", "/opt/tls/server.key")
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("0.0.0.0", {tls_port}), H) as httpd:
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    httpd.serve_forever()
EOF

cat << 'EOF' > /usr/local/bin/restart-tls-gw
#!/bin/bash
pkill -f '/opt/tls/https_srv.py' 2>/dev/null || true
sleep 0.3
nohup python3 /opt/tls/https_srv.py >/var/log/tls-gw.log 2>&1 &
sleep 0.4
echo "Pasarela HTTPS reiniciada en 0.0.0.0:{tls_port}"
EOF
chmod +x /usr/local/bin/restart-tls-gw
/usr/local/bin/restart-tls-gw
"""

    client_setup = f"""
source /etc/chaos_nodes.env
echo "${{IP_TLS_GATEWAY}} vault.corp.internal" >> /etc/hosts
mkdir -p /etc/ssl/corp
for _ in 1 2 3 4 5; do
    curl -sk "https://vault.corp.internal:{tls_port}/ca.crt" -o /etc/ssl/corp/ca.crt && break
    sleep 0.3
done
"""

    return {
        "vars": {"tls_port": tls_port, "token": token},
        "nodes": [
            {
                "role": "tls-gateway",
                "distro": "debian",
                "shell": "/bin/bash",
                "default_user": "root",
                "setup_sh": gw_setup,
            },
            {
                "role": "api-client",
                "distro": "debian",
                "shell": "/bin/bash",
                "default_user": "root",
                "setup_sh": client_setup,
            },
        ],
        "checks": [
            {
                "id": "cert-san",
                "label": "El certificado de la pasarela es válido para el nombre vault.corp.internal",
                "node": "tls-gateway",
                "cmd": "openssl x509 -in /opt/tls/server.crt -noout -text | grep -q 'DNS:vault.corp.internal'",
            },
            {
                "id": "cert-chain",
                "label": "El certificado del servidor está firmado válidamente por /etc/ssl/corp-ca/ca.crt",
                "node": "tls-gateway",
                "cmd": "openssl verify -CAfile /etc/ssl/corp-ca/ca.crt /opt/tls/server.crt | grep -q 'OK'",
            },
            {
                "id": "client-strict-https",
                "label": f"Cliente valida TLS estricto (sin -k) contra https://vault.corp.internal:{tls_port}/status",
                "node": "api-client",
                "cmd": f"curl -sf --cacert /etc/ssl/corp/ca.crt https://vault.corp.internal:{tls_port}/status | grep -q '{token}'",
            },
        ],
        "hints": [
            f"En `api-client`, ejecuta `curl -v --cacert /etc/ssl/corp/ca.crt https://vault.corp.internal:{tls_port}/status` para ver el motivo exacto del rechazo X.509.",
            "En `tls-gateway`, inspecciona `openssl x509 -in /opt/tls/server.crt -noout -subject -ext subjectAltName`. Verás que fue emitido para `legacy-vault.corp.internal`.",
            "Genera un nuevo CSR/certificado en `/opt/tls/` con `subjectAltName = DNS:vault.corp.internal` firmándolo con `/etc/ssl/corp-ca/ca.crt` y `/etc/ssl/corp-ca/ca.key`, y ejecuta `restart-tls-gw`.",
        ],
        "topology": {
            "entry": {"label": "tú (shell)", "to": "api-client", "via": "curl https://vault.corp.internal"},
            "nodes": {
                "api-client": {"runs": "cliente HTTPS estricto (curl, sin -k)", "look": ["/etc/hosts", "/etc/ssl/corp/ca.crt"]},
                "tls-gateway": {"runs": f"python · pasarela HTTPS :{tls_port}", "look": ["ss -tlnp", "/usr/local/bin/restart-tls-gw", "/etc/ssl/corp-ca/"]},
            },
            "links": [
                {"from": "api-client", "to": "tls-gateway", "via": f"HTTPS :{tls_port} /status (TLS verificado con la CA corporativa)"},
            ],
            "checks": {"cert-san": "node:tls-gateway", "cert-chain": "node:tls-gateway", "client-strict-https": "link:0"},
        },
        "solution_summary": (
            "El certificado `/opt/tls/server.crt` tenía `DNS:legacy-vault.corp.internal` en `subjectAltName`, provocando fallo de verificación de hostname en clientes estrictos.\n"
            "Solución: reemitir `/opt/tls/server.crt` con `-extfile <(printf 'subjectAltName=DNS:vault.corp.internal')` firmado por `/etc/ssl/corp-ca/ca.{crt,key}` y ejecutar `restart-tls-gw`."
        ),
    }


def _build_dns_soa_serial(rng: random.Random) -> dict[str, Any]:
    base_serial = 2026112501
    http_port = rng.choice([8085, 8095])
    token = _tok(rng, "DNS_SOA")

    ns_setup = f"""
source /etc/chaos_nodes.env
mkdir -p /etc/bind/zones /var/lib/bind

echo "{base_serial}" > /var/lib/bind/loaded_serial

# Zona rota: serial sin incrementar, A apunta a IP muerta 10.254.99.99 y CNAME sin punto final
cat << EOF > /etc/bind/zones/db.corp.lan
\\$TTL 300
@   IN  SOA ns1.corp.lan. hostmaster.corp.lan. (
        {base_serial} ; Serial
        3600       ; Refresh
        900        ; Retry
        604800     ; Expire
        60 )       ; Negative Cache TTL
;
@       IN  NS      ns1.corp.lan.
ns1     IN  A       ${{IP_NS1_MASTER}}
api     IN  A       10.254.99.99
portal  IN  CNAME   api.corp.lan
EOF

cat << 'EOF' > /opt/dns_auth.py
import os, re, socket, struct, threading

ZONE_PATH = "/etc/bind/zones/db.corp.lan"
ACTIVE_FILE = "/var/lib/bind/active_records.txt"

def load_records():
    recs = {{"A": {{}}, "CNAME": {{}}}}
    if not os.path.exists(ACTIVE_FILE):
        return recs
    for line in open(ACTIVE_FILE):
        t, k, v = line.strip().split("|")
        recs[t][k] = v
    return recs

def parse_qname(data, offset=12):
    labels = []
    while True:
        l = data[offset]
        offset += 1
        if l == 0:
            break
        labels.append(data[offset:offset+l].decode("ascii", "ignore"))
        offset += l
    qtype, qclass = struct.unpack("!HH", data[offset:offset+4])
    return ".".join(labels).lower() + ".", qtype, offset + 4

def encode_name(fqdn):
    out = b""
    for p in fqdn.rstrip(".").split("."):
        if p:
            b = p.encode()
            out += bytes([len(b)]) + b
    return out + b"\\x00"

def resolve_ip(qname, recs):
    cur = qname
    for _ in range(4):
        if cur in recs["A"]:
            return recs["A"][cur]
        if cur in recs["CNAME"]:
            cur = recs["CNAME"][cur]
        else:
            break
    return None

def build_reply(data):
    tid = data[:2]
    qname, qtype, end_q = parse_qname(data)
    recs = load_records()
    ip = resolve_ip(qname, recs) if qtype in (1, 255) else None
    if not ip:
        return tid + struct.pack("!HHHHH", 0x8583, 1, 0, 0, 0) + data[12:end_q]
    ans = encode_name(qname) + struct.pack("!HHIH", 1, 1, 60, 4) + socket.inet_aton(ip)
    return tid + struct.pack("!HHHHH", 0x8580, 1, 1, 0, 0) + data[12:end_q] + ans

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 53))
while True:
    pkt, addr = sock.recvfrom(512)
    try:
        sock.sendto(build_reply(pkt), addr)
    except Exception:
        pass
EOF

cat << 'EOF' > /usr/local/bin/named-reload
#!/bin/bash
set -e
Z="/etc/bind/zones/db.corp.lan"
PREV=$(cat /var/lib/bind/loaded_serial 2>/dev/null || echo 0)
SER=$(grep -E '[0-9]{{8,10}}' "$Z" | head -n1 | grep -oE '[0-9]{{8,10}}')
if [ -z "$SER" ]; then
    echo "ERROR: No se encontro Serial SOA valido en $Z" >&2
    exit 1
fi
if [ "$SER" -le "$PREV" ] && [ -f /var/lib/bind/active_records.txt ]; then
    echo "WARN: Serial SOA ($SER) NO incrementado respecto a $PREV; cambios ignorados." >&2
    exit 1
fi
TMP="/var/lib/bind/active_records.txt.tmp"
: > "$TMP"
ORIGIN="corp.lan."
while read -r host class rtype target rest; do
    [[ -z "$host" || "$host" =~ ^\\; || "$host" =~ ^\\$ || "$host" == "(" || "$host" == ")" ]] && continue
    if [ "$class" != "IN" ]; then continue; fi
    [[ "$host" == "@" ]] && fqdn="$ORIGIN" || fqdn="${{host}}.${{ORIGIN}}"
    if [ "$rtype" = "A" ]; then
        echo "A|${{fqdn}}|${{target}}" >> "$TMP"
    elif [ "$rtype" = "CNAME" ]; then
        [[ "$target" == *. ]] && tgt="$target" || tgt="${{target}}.${{ORIGIN}}"
        echo "CNAME|${{fqdn}}|${{tgt}}" >> "$TMP"
    fi
done < "$Z"
mv "$TMP" /var/lib/bind/active_records.txt
echo "$SER" > /var/lib/bind/loaded_serial
echo "OK: Zona corp.lan recargada con Serial $SER"
EOF
chmod +x /usr/local/bin/named-reload
/usr/local/bin/named-reload

nohup python3 /opt/dns_auth.py >/var/log/dns.log 2>&1 &

mkdir -p /opt/web
cat << 'EOF' > /opt/web/srv.py
import http.server, socketserver
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"READY:{token}\\n")
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("0.0.0.0", {http_port}), H) as s: s.serve_forever()
EOF
nohup python3 /opt/web/srv.py >/var/log/web.log 2>&1 &
sleep 0.3
"""

    app_setup = """
source /etc/chaos_nodes.env
echo "nameserver ${IP_NS1_MASTER}" > /etc/resolv.conf
"""

    return {
        "vars": {"base_serial": base_serial, "http_port": http_port, "token": token},
        "nodes": [
            {
                "role": "ns1-master",
                "distro": "debian",
                "shell": "/bin/bash",
                "default_user": "root",
                "setup_sh": ns_setup,
            },
            {
                "role": "app-client",
                "distro": "debian",
                "shell": "/bin/bash",
                "default_user": "root",
                "setup_sh": app_setup,
            },
        ],
        "checks": [
            {
                "id": "soa-bumped",
                "label": f"Serial SOA incrementado por encima de {base_serial} y zona recargada",
                "node": "ns1-master",
                "cmd": f"s=$(cat /var/lib/bind/loaded_serial 2>/dev/null || echo 0); [ \"$s\" -gt {base_serial} ]",
            },
            {
                "id": "dig-portal",
                "label": "dig @ns1-master portal.corp.lan resuelve la IP real de ns1-master",
                "node": "app-client",
                "cmd": "source /etc/chaos_nodes.env && [ \"$(dig +short @${IP_NS1_MASTER} portal.corp.lan)\" = \"${IP_NS1_MASTER}\" ]",
            },
            {
                "id": "http-portal",
                "label": f"app-client conecta con http://portal.corp.lan:{http_port}/ready usando DNS",
                "node": "app-client",
                "cmd": f"curl -sf --max-time 3 http://portal.corp.lan:{http_port}/ready | grep -q '{token}'",
            },
        ],
        "hints": [
            "Desde `app-client`, prueba `dig portal.corp.lan` y `dig api.corp.lan`. Fíjate a qué FQDN se expande el CNAME y qué IP devuelve `api`.",
            "En `ns1-master`, abre `/etc/bind/zones/db.corp.lan` y consulta `/etc/chaos_nodes.env` para ver `IP_NS1_MASTER`. Recuerda qué ocurre en BIND cuando olvidas el punto final (`.`) en `api.corp.lan.`.",
            f"Corrige `api IN A <IP_NS1_MASTER>`, pon el punto final `portal IN CNAME api.corp.lan.`, incrementa el Serial SOA (> `{base_serial}`) y ejecuta `named-reload`.",
        ],
        "topology": {
            "entry": {"label": "tú (shell)", "to": "app-client", "via": "curl portal.corp.lan /ready"},
            "nodes": {
                "app-client": {"runs": "cliente · DNS + HTTP", "look": ["/etc/resolv.conf", "getent hosts portal.corp.lan"]},
                "ns1-master": {"runs": f"DNS autoritativo :53 · web :{http_port}", "look": ["/etc/bind/zones/db.corp.lan", "/var/lib/bind/loaded_serial", "/var/log/dns.log", "/var/log/web.log"]},
            },
            "links": [
                {"from": "app-client", "to": "ns1-master", "via": f"DNS :53 + HTTP :{http_port} /ready"},
            ],
            "checks": {"soa-bumped": "node:ns1-master", "dig-portal": "link:0", "http-portal": "entry"},
        },
        "solution_summary": (
            "1. `api` apuntaba a `10.254.99.99` en lugar de la IP real de `ns1-master`.\n"
            "2. `portal IN CNAME api.corp.lan` carecía de punto final (`.`), expandiéndose a `api.corp.lan.corp.lan.`.\n"
            f"3. Era obligatorio incrementar el Serial SOA por encima de `{base_serial}` antes de ejecutar `named-reload`."
        ),
    }


def _build_cloud_az_nsg_udr(rng: random.Random) -> dict[str, Any]:
    db_port = rng.choice([5432, 8529, 9200])
    vip_net = f"172.29.{rng.choice([10, 20, 30])}"
    token = _tok(rng, "AZ_VNET")

    nva_setup = f"""
# Ruta del hub hacia el spoke del backend: en Azure la da el peering de VNets (ruta del sistema, no es parte de la avería)
ip route add {vip_net}.0/24 via "$IP_VNET_DB"
""" + """
# Simula NVA Azure con IP Forwarding desactivado en regla FORWARD
iptables -P FORWARD DROP
cat << 'EOF' > /etc/nva_appliance.conf
# Azure NIC Setting Simulation: IP Forwarding
ENABLE_IP_FORWARDING=false
EOF
cat << 'EOF' > /usr/local/bin/nva-apply
#!/bin/bash
source /etc/nva_appliance.conf
if [ "$ENABLE_IP_FORWARDING" = "true" ]; then
    iptables -P FORWARD ACCEPT
    iptables -F FORWARD
    echo "NVA: IP Forwarding HABILITADO en plano de datos"
else
    iptables -P FORWARD DROP
    echo "NVA: IP Forwarding DESHABILITADO (paquetes en transito descartados)"
fi
EOF
chmod +x /usr/local/bin/nva-apply
/usr/local/bin/nva-apply
"""

    db_setup = f"""
source /etc/chaos_nodes.env
# Anuncia VIP de subred Backend en lo
ip addr add {vip_net}.10/32 dev lo

# Fallo 2 (NSG Inbound Rule Priority 100 DENY sobre puerto DB antes de Priority 200 ALLOW)
iptables -N NSG_INBOUND 2>/dev/null || true
iptables -F NSG_INBOUND
iptables -A INPUT -p tcp --dport {db_port} -j NSG_INBOUND
iptables -A NSG_INBOUND -p tcp --dport {db_port} -m comment --comment "prio-100-deny-legacy" -j REJECT
iptables -A NSG_INBOUND -p tcp --dport {db_port} -m comment --comment "prio-200-allow-vnet" -j ACCEPT

mkdir -p /opt/backend
cat << 'EOF' > /opt/backend/db.py
import http.server, socketserver
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"BACKEND_OK:{token}\\n")
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("{vip_net}.10", {db_port}), H) as s: s.serve_forever()
EOF
nohup python3 /opt/backend/db.py >/var/log/db.log 2>&1 &
sleep 0.3
"""

    web_setup = f"""
source /etc/chaos_nodes.env
# Fallo 3 (UDR mal apuntada a blackhole en vez de pasar por el NVA IP_NVA_FW)
ip route add blackhole {vip_net}.0/24
"""

    return {
        "vars": {"db_port": db_port, "vip_net": vip_net, "token": token},
        "nodes": [
            {
                "role": "vnet-web",
                "distro": "debian",
                "shell": "/bin/bash",
                "default_user": "root",
                "caps": ["NET_ADMIN"],
                "setup_sh": web_setup,
            },
            {
                "role": "nva-fw",
                "distro": "debian",
                "shell": "/bin/bash",
                "default_user": "root",
                "caps": ["NET_ADMIN"],
                "sysctls": {"net.ipv4.ip_forward": "1"},
                "setup_sh": nva_setup,
            },
            {
                "role": "vnet-db",
                "distro": "debian",
                "shell": "/bin/bash",
                "default_user": "root",
                "caps": ["NET_ADMIN"],
                "setup_sh": db_setup,
            },
        ],
        "checks": [
            {
                "id": "udr-web",
                "label": f"UDR en vnet-web enruta {vip_net}.0/24 hacia el next-hop Virtual Appliance (nva-fw)",
                "node": "vnet-web",
                "cmd": f"source /etc/chaos_nodes.env && ip route get {vip_net}.10 | grep -q \"via ${{IP_NVA_FW}}\"",
            },
            {
                "id": "nva-fwd",
                "label": "IP Forwarding habilitado y aplicado en el appliance nva-fw",
                "node": "nva-fw",
                "cmd": "iptables -S FORWARD | grep -q '^-P FORWARD ACCEPT'",
            },
            {
                "id": "nsg-e2e",
                "label": f"Tráfico desde vnet-web alcanza http://{vip_net}.10:{db_port} tras corregir NSG_INBOUND",
                "node": "vnet-web",
                "cmd": f"curl -sf --max-time 3 http://{vip_net}.10:{db_port}/ | grep -q '{token}'",
            },
        ],
        "hints": [
            f"En `vnet-web`, revisa `ip route show` buscando `{vip_net}.0/24` y consulta la IP de `nva-fw` en `/etc/chaos_nodes.env`.",
            "Tras reemplazar la ruta `blackhole` por `via <IP_NVA_FW>`, revisa en `nva-fw` el archivo `/etc/nva_appliance.conf` y el comando `nva-apply`.",
            f"Por último, en `vnet-db` inspecciona `iptables -L NSG_INBOUND -n --line-numbers`: la regla `prio-100-deny-legacy` bloquea el puerto `{db_port}` antes del `ACCEPT`.",
        ],
        "topology": {
            "entry": {"label": "tú (shell)", "to": "vnet-web", "via": f"curl {vip_net}.10:{db_port}"},
            "nodes": {
                "vnet-web": {"runs": "carga web (spoke) · cliente del backend", "look": [f"ping -c1 {vip_net}.10", "/etc/chaos_nodes.env", "ip -4 addr"]},
                "nva-fw": {"runs": "NVA (hub) · reenvía paquetes", "look": ["sysctl net.ipv4.ip_forward", "iptables -S FORWARD"]},
                "vnet-db": {"runs": f"python · backend {vip_net}.10:{db_port}", "look": ["ss -tlnp", "ip addr show lo", "/var/log/db.log"]},
            },
            "links": [
                {"from": "vnet-web", "to": "nva-fw", "via": "UDR · next hop Virtual Appliance"},
                {"from": "nva-fw", "to": "vnet-db", "via": f"TCP :{db_port}"},
            ],
            "checks": {"udr-web": "link:0", "nva-fwd": "node:nva-fw", "nsg-e2e": "entry"},
        },
        "solution_summary": (
            f"1. `vnet-web`: eliminar `ip route del blackhole {vip_net}.0/24` y añadir `ip route add {vip_net}.0/24 via $IP_NVA_FW`.\n"
            "2. `nva-fw`: poner `ENABLE_IP_FORWARDING=true` en `/etc/nva_appliance.conf` y ejecutar `nva-apply`.\n"
            "3. `vnet-db`: eliminar la regla de mayor prioridad `iptables -D NSG_INBOUND 1` (`prio-100-deny-legacy`)."
        ),
    }


SCENARIO_CATALOG: list[dict[str, Any]] = [
    {
        "id": "net-nginx-bad-gateway",
        "title": "502 Bad Gateway en Pasarela de Pagos",
        "category": "Servicios web y TLS",
        "difficulty": "Intermedio",
        "points": 180,
        "estimated_min": 7,
        "tags": ["Nginx", "Sockets"],
        "certs": ["LPIC-2"],
        "blind_alert": (
            "PAGERDUTY [SEV-1] · El balanceador `edge-proxy` devuelve errores 502 en `http://127.0.0.1:8080/health`. "
            "Tienes terminales abiertas en `edge-proxy` y `payments-api`. Restablece el tráfico sin perder el servicio."
        ),
        "briefing": (
            "El reverse proxy `edge-proxy` (puerto `8080`) debería enrutar `/health` y `/api/` hacia el nodo `payments-api`, "
            "pero todas las peticiones fallan con `502 Bad Gateway`. Diagnostica ambos contenedores y restablece el flujo extremo a extremo."
        ),
        "builder": _build_nginx_bad_gateway,
    },
    {
        "id": "net-firewall-drop",
        "title": "Bloqueo Silencioso de Telemetría",
        "category": "Redes y routing",
        "difficulty": "Intermedio",
        "points": 170,
        "estimated_min": 6,
        "tags": ["iptables"],
        "certs": ["LPIC-2", "CCNP"],
        "blind_alert": (
            "ALERTMANAGER [CRIT] · El recolector `client-probe` dejó de recibir métricas HTTP desde el nodo `metrics-srv`. "
            "El equipo de plataforma jura que el proceso exporter sigue arrancado. Averigua qué ocurre en la red."
        ),
        "briefing": (
            "El contenedor `client-probe` no logra consultar el endpoint `/metrics` de `metrics-srv`, aunque localmente en `metrics-srv` "
            "el proceso parece estar sano. Encuentra el bloqueo y permite que `client-probe` descargue las métricas."
        ),
        "builder": _build_firewall_drop,
    },
    {
        "id": "sec-acl-shared-vault",
        "title": "Permisos Fantasma en Cierre Contable",
        "category": "Sistema y permisos",
        "difficulty": "Básico",
        "points": 130,
        "estimated_min": 5,
        "tags": ["ACLs", "Permisos"],
        "certs": ["LPIC-1"],
        "blind_alert": (
            "TICKET OPS-409 · El usuario `alumno` (miembro de `auditores`) recibe `Permission denied` al lanzar "
            "`/srv/vault/close_month.sh`, a pesar de que `ls -l` aparenta tener permisos de grupo suficientes."
        ),
        "briefing": (
            "El usuario `alumno` pertenece al grupo `auditores` y debe poder ejecutar `/srv/vault/close_month.sh` sin usar `sudo` "
            "para generar `/srv/vault/out/report.ok`. Investiga por qué el kernel le deniega el acceso y corrígelo."
        ),
        "builder": _build_acl_vault,
    },
    {
        "id": "sys-rocky-crlf-env",
        "title": "Demonio de Facturación Roto tras Migración",
        "category": "Sistema y permisos",
        "difficulty": "Básico",
        "points": 140,
        "estimated_min": 6,
        "tags": ["Rocky Linux 9", "Bash", "Entorno"],
        "certs": ["LPIC-1"],
        "blind_alert": (
            "PAGERDUTY [SEV-2] · Tras un despliegue manual en `rocky-billing`, el demonio `/opt/billing/billingd.sh` "
            "no levanta el puerto local de facturación. Restaura el arranque limpio del servicio."
        ),
        "briefing": (
            "En este servidor Rocky Linux 9, `/opt/billing/billingd.sh` falla al intentar levantar el microservicio de facturación "
            "definido en `/etc/sysconfig/billing.env`. Corrige todos los defectos del despliegue hasta que el puerto responda."
        ),
        "builder": _build_rocky_crlf_env,
    },
    {
        "id": "sto-zombie-log-cron",
        "title": "Fuga Desbocada en /var/log con Persistencia",
        "category": "Sistema y permisos",
        "difficulty": "Intermedio",
        "points": 190,
        "estimated_min": 7,
        "tags": ["Procesos", "Cron"],
        "certs": ["LPIC-2"],
        "blind_alert": (
            "ALERTMANAGER [DISK-URGENT] · `/var/log/ingest/overflow.log` crece decenas de KB por segundo y si matas el proceso "
            "a ciegas reaparece al minuto siguiente. ¡PROHIBIDO reiniciar o matar el proceso crítico `core-dispatcher`!"
        ),
        "briefing": (
            "Un proceso fugitivo está llenando `/var/log/ingest/overflow.log` y cuenta con un mecanismo que lo revive periódicamente. "
            "Neutraliza la persistencia, detén el proceso culpable, trunca `overflow.log` sin borrarlo y mantén intacto el PID original de `core-dispatcher`."
        ),
        "builder": _build_zombie_log_cron,
    },
    {
        "id": "net-dns-redis-split",
        "title": "Secuestro de Resolución y Caché Desincronizada",
        "category": "DNS",
        "difficulty": "Intermedio",
        "points": 190,
        "estimated_min": 8,
        "tags": ["DNS", "Redis"],
        "certs": ["LPIC-2"],
        "blind_alert": (
            "PAGERDUTY [SEV-2] · `/opt/app/healthcheck.sh` falla en `app-node` al intentar leer el estado de sesión en `cache.internal`. "
            "Tienes acceso tanto a `app-node` como al nodo `redis-cache`."
        ),
        "briefing": (
            "La aplicación en `app-node` usa `/opt/app/cache.conf` para consultar `cache.internal` mediante `/opt/app/healthcheck.sh`, "
            "pero ni la resolución de nombres ni los parámetros de conexión coinciden con el servidor `redis-cache` activo."
        ),
        "builder": _build_dns_redis_split,
    },
    {
        "id": "sec-sudoers-lockout",
        "title": "Bloqueo Total de Sudoers y Cuenta Operativa",
        "category": "Sistema y permisos",
        "difficulty": "Intermedio",
        "points": 160,
        "estimated_min": 6,
        "tags": ["sudo", "Usuarios"],
        "certs": ["LPIC-2"],
        "blind_alert": (
            "CONSOLA SERIE DE RESCATE · Un cambio mal aplicado dejó inoperativo `sudo` en todo el servidor y bloqueó "
            "el acceso del operador `alumno`, rompiendo el pipeline `/usr/local/bin/deploy-check`."
        ),
        "briefing": (
            "Has entrado por consola de rescate `root` porque `/etc/sudoers.d/90-ops` corrompió `sudo` y la cuenta `alumno` quedó bloqueada. "
            "Repara los permisos y sintaxis de `sudoers` y habilita a `alumno` para ejecutar `sudo -n /usr/local/bin/deploy-check`."
        ),
        "builder": _build_sudoers_lockout,
    },
    {
        "id": "net-routing-blackhole",
        "title": "Agujero Negro de Enrutamiento hacia Subred Remota",
        "category": "Redes y routing",
        "difficulty": "Avanzado",
        "points": 240,
        "estimated_min": 9,
        "tags": ["iproute2", "Routing"],
        "certs": ["LPIC-2", "CCNP"],
        "blind_alert": (
            "NOC TICKET [NET-88] · Desde `gateway-rtr` es imposible conectar con el servicio interno en el puerto `8090` de la VIP "
            "anunciada en la interfaz `lo` de `branch-srv` (`RTNETLINK` / paquetes descartados). Restablece la ruta IPv4."
        ),
        "briefing": (
            "El nodo `branch-srv` sirve una API interna en el puerto `8090` sobre una dirección IP virtual configurada en `lo`. "
            "Sin embargo, `gateway-rtr` tiene una tabla de rutas saboteada que impide alcanzar esa subred. Corrige el enrutamiento en `gateway-rtr`."
        ),
        "builder": _build_routing_blackhole,
    },
    {
        "id": "web-nginx-vhost-collision",
        "title": "VirtualHost Fantasma y 403/503 Encadenados",
        "category": "Servicios web y TLS",
        "difficulty": "Intermedio",
        "points": 175,
        "estimated_min": 7,
        "tags": ["Nginx", "VirtualHosts", "Permisos"],
        "certs": ["LPIC-2"],
        "blind_alert": (
            "PAGERDUTY [WEB-04] · Las peticiones a `http://portal.corp.local/` devuelven una página fantasma de mantenimiento "
            "o errores HTTP 503/403 en lugar del portal productivo."
        ),
        "briefing": (
            "En `nginx-vhost`, al solicitar `http://127.0.0.1/` con cabecera `Host: portal.corp.local`, Nginx nunca entrega "
            "`/var/www/portal/index.html`. Resuelve la colisión de `server_name`, la directiva de bloqueo y los permisos del DocumentRoot."
        ),
        "builder": _build_nginx_vhost_collision,
    },
    {
        "id": "chaos-boss-cascade",
        "title": "Guardia 3:00 AM: Cascada Triple en Microservicios",
        "category": "Incidente mayor",
        "difficulty": "Experto",
        "points": 350,
        "estimated_min": 12,
        "tags": ["Nginx", "Firewall", "Redis"],
        "certs": [],
        "blind_alert": (
            "INCIDENTE MAYOR [SEV-0 · 03:14 AM] · Caída total de transacciones en `/api/tx` a través de `edge-lb:8080`. "
            "Topología de 3 nodos (`edge-lb` -> `core-api` -> `vault-db`). Hay múltiples fallos simultáneos en distintas capas."
        ),
        "briefing": (
            "Escenario jefe de 3 contenedores conectados (`edge-lb`, `core-api` y `vault-db`). El endpoint transaccional "
            "`http://127.0.0.1:8080/api/tx` en `edge-lb` debe escribir y leer en `vault-db` pasando por `core-api`, pero las tres capas presentan averías distintas."
        ),
        "builder": _build_boss_cascade,
    },
    {
        "id": "vpn-wireguard-overlay",
        "title": "Túnel WireGuard S2S Caído y Bloqueo por MTU",
        "category": "Redes y routing",
        "difficulty": "Avanzado",
        "points": 250,
        "estimated_min": 9,
        "tags": ["WireGuard", "MTU"],
        "certs": ["LPIC-2", "CCNP"],
        "blind_alert": (
            "NOC [VPN-S2S] · El túnel entre `hq-vpn-gw` y `branch-vpn-gw` no levanta tráfico hacia la intranet remota "
            "y las respuestas HTTP grandes se cortan en seco. Restablece `/etc/wireguard/wg0.conf`."
        ),
        "briefing": (
            "El nodo `hq-vpn-gw` gestiona su túnel hacia `branch-vpn-gw` mediante `/etc/wireguard/wg0.conf` y `wg-apply`, "
            "pero tiene fallos combinados de puerto Endpoint, subred AllowedIPs y tamaño de MTU."
        ),
        "builder": _build_wireguard_overlay,
    },
    {
        "id": "sec-tls-expired-san",
        "title": "Fallo X.509 de SAN en Pasarela Corporativa HTTPS",
        "category": "Servicios web y TLS",
        "difficulty": "Intermedio",
        "points": 210,
        "estimated_min": 8,
        "tags": ["OpenSSL", "TLS/PKI"],
        "certs": ["LPIC-2", "AZ-104"],
        "blind_alert": (
            "SECOPS [TLS-ERR] · Los clientes estrictos en `api-client` rechazan la conexión HTTPS contra `vault.corp.internal` "
            "pese a confiar en la CA raíz `/etc/ssl/corp/ca.crt`. Prohibido desactivar la verificación TLS en el cliente."
        ),
        "briefing": (
            "La pasarela `tls-gateway` sirve HTTPS con un certificado emitido por la CA local `/etc/ssl/corp-ca/`, "
            "pero `api-client` aborta el handshake TLS al verificar la identidad del certificado. Reemite el certificado correctamente."
        ),
        "builder": _build_tls_expired_san,
    },
    {
        "id": "net-dns-soa-serial",
        "title": "Zona DNS Autoritativa: Serial SOA y CNAME Roto",
        "category": "DNS",
        "difficulty": "Intermedio",
        "points": 200,
        "estimated_min": 8,
        "tags": ["DNS/BIND", "SOA"],
        "certs": ["LPIC-2"],
        "blind_alert": (
            "PAGERDUTY [DNS-53] · Los clientes en `app-client` no logran resolver `portal.corp.lan` contra `ns1-master` "
            "tras una edición manual fallida en `/etc/bind/zones/db.corp.lan`."
        ),
        "briefing": (
            "Repara los registros `A` y `CNAME` en `/etc/bind/zones/db.corp.lan` dentro de `ns1-master`, "
            "asegúrate de cumplir la regla del Serial SOA y recarga con `named-reload` hasta que `app-client` conecte por nombre."
        ),
        "builder": _build_dns_soa_serial,
    },
    {
        "id": "cloud-az-nsg-udr",
        "title": "Cloud Networking: UDR, NVA Forwarding y NSG",
        "category": "Redes y routing",
        "difficulty": "Experto",
        "points": 310,
        "estimated_min": 11,
        "tags": ["UDR/NVA", "NSG"],
        "certs": ["AZ-104"],
        "blind_alert": (
            "AZURE MONITOR [VNET-CRIT] · `vnet-web` no alcanza la VIP del backend en `vnet-db` a través del Virtual Appliance `nva-fw`. "
            "Revisa tablas de rutas UDR, IP Forwarding del NVA y reglas de prioridad en `NSG_INBOUND`."
        ),
        "briefing": (
            "Escenario clásico de arquitectura Hub-and-Spoke de AZ-104 en 3 nodos (`vnet-web` -> `nva-fw` -> `vnet-db`). "
            "Diagnostica y corrige la ruta definida por el usuario (UDR), el reenvío IP en el appliance y las reglas de seguridad NSG."
        ),
        "builder": _build_cloud_az_nsg_udr,
    },
    {
        "id": "sec-ssh-bruteforce",
        "title": "Fuerza Bruta SSH: Detectar y Bloquear con nftables",
        "category": "Seguridad (Blue Team)",
        "difficulty": "Intermedio",
        "points": 230,
        "estimated_min": 9,
        "tags": ["sshd", "auth.log", "nftables"],
        "certs": ["LPIC-2"],
        "blind_alert": (
            "SIEM [SSH-BRUTE] · `ssh-victim` acumula una ráfaga de `Failed password` y usuarios inexistentes en `/var/log/auth.log`. "
            "El equipo de operaciones sigue necesitando entrar por SSH desde `ops-client`. Contén el ataque sin cortar el acceso legítimo."
        ),
        "briefing": (
            "Un nodo externo (`bot-externo`) lanza fuerza bruta contra el `sshd` real de `ssh-victim`, mientras `ops-client` entra legítimamente. "
            "Identifica la IP atacante en los logs, bloquéala con nftables de forma persistente (`/etc/nftables.conf`) y verifica que el SSH legítimo sigue funcionando."
        ),
        "builder": build_ssh_bruteforce,
    },
    {
        "id": "sec-portscan-detect",
        "title": "Escaneo de Puertos: Detección y Mitigación con nftables",
        "category": "Seguridad (Blue Team)",
        "difficulty": "Intermedio",
        "points": 220,
        "estimated_min": 8,
        "tags": ["nftables", "Detección"],
        "certs": ["LPIC-2", "CCNA"],
        "blind_alert": (
            "IDS [RECON-SCAN] · `edge-srv` registra un pico de conexiones nuevas hacia cientos de puertos distintos. "
            "El servicio de inventario debe seguir accesible para `app-client`. Localiza el origen y mitígalo."
        ),
        "briefing": (
            "`recon-bot` barre puertos de `edge-srv` en bucle. Un sensor deja los SYN entrantes en `/var/log/portwatch.log`. "
            "Detecta al escáner, mitígalo con nftables (drop de su IP o `limit rate`) y deja el servicio legítimo accesible."
        ),
        "builder": build_portscan_detect,
    },
    {
        "id": "sec-dns-exfil",
        "title": "Exfiltración por DNS: Cazar el Proceso y Cortar la Salida",
        "category": "Seguridad (Blue Team)",
        "difficulty": "Avanzado",
        "points": 280,
        "estimated_min": 11,
        "tags": ["DNS", "cron", "nftables"],
        "certs": [],
        "blind_alert": (
            "EDR [DNS-TUNNEL] · `infected-host` emite consultas DNS anómalas de gran longitud hacia el exterior. "
            "Hay datos de clientes en `/srv/finance`. Corta la fuga sin romper la resolución interna."
        ),
        "briefing": (
            "Un proceso persistente en `infected-host` exfiltra datos codificados en subdominios DNS hacia un servidor externo. "
            "Identifica proceso/cron y dominio, páralo, elimina la persistencia y bloquea con nftables la salida DNS no autorizada manteniendo la resolución vía `corp-dns`."
        ),
        "builder": build_dns_exfil,
    },
]

# Packs definidos como datos (chaos_lab/packs/*.json)
SCENARIO_CATALOG += load_pack("lpic1_102")
SCENARIO_CATALOG += load_pack("lpic1_101")
SCENARIO_CATALOG += load_pack("essentials_010")
SCENARIO_CATALOG += load_pack("lpic2_ldap")
SCENARIO_CATALOG += load_pack("redes")

SCENARIOS_BY_ID: dict[str, dict[str, Any]] = {s["id"]: s for s in SCENARIO_CATALOG}


def instantiate_scenario(scenario_id: str, seed: int | None = None) -> dict[str, Any]:
    if scenario_id not in SCENARIOS_BY_ID:
        raise KeyError(f"Escenario desconocido: {scenario_id}")
    meta = SCENARIOS_BY_ID[scenario_id]
    actual_seed = seed if seed is not None else random.randint(100000, 999999)
    rng = random.Random(actual_seed)
    built = meta["builder"](rng)
    return {
        "id": meta["id"],
        "title": meta["title"],
        "category": meta["category"],
        "difficulty": meta["difficulty"],
        "points": meta["points"],
        "estimated_min": meta["estimated_min"],
        "tags": meta["tags"],
        "blind_alert": meta["blind_alert"],
        "briefing": meta["briefing"],
        "tipo": meta.get("tipo", "averia"),
        "seed": actual_seed,
        **built,
    }
