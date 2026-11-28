"""Traducciones al inglés de los escenarios definidos en código (scenarios.py y scenarios_secops.py).

Cada entrada es una función que recibe las `vars` del escenario ya construido (las mismas semillas que usa el
texto en español) y devuelve el bloque `i18n.en`:
    title, briefing, blind_alert, hints, solution_summary, nodes {rol: runs}, links [via...], entry {label, via},
    checks {id de la sonda: etiqueta} y, en SecOps, signals (plantillas con los mismos {0}, {1}... que el español).
`apply_en` completa lo que no se traduce (los `look` son comandos/rutas y se copian del español), pone `label_en`
junto a cada sonda y deja el resultado en inst["i18n"]["en"]. Los valores secretos solo aparecen donde aparecen
en español (pista 3 / solución).
"""

from __future__ import annotations

from typing import Any, Callable


def _nginx_bad_gateway(v: dict[str, Any]) -> dict[str, Any]:
    rp, wp = v["real_port"], v["wrong_port"]
    return {
        "title": "502 Bad Gateway on the Payments Gateway",
        "briefing": "The reverse proxy `edge-proxy` (port `8080`) should route `/health` and `/api/` to the `payments-api` node, but every request fails with `502 Bad Gateway`. Diagnose both containers and restore the end-to-end flow.",
        "blind_alert": "PAGERDUTY [SEV-1] · The load balancer `edge-proxy` returns 502 errors on `http://127.0.0.1:8080/health`. You have terminals open on `edge-proxy` and `payments-api`. Restore traffic without losing the service.",
        "hints": [
            "Check in `edge-proxy` what `wget -S -O- http://127.0.0.1:8080/health` returns and review `/etc/nginx/conf.d/payments.conf`.",
            "Switch to the `payments-api` tab and run `ss -tlnp`: look at both the real port number and the listen IP address (`127.0.0.1` vs `0.0.0.0`).",
            f"Edit `/opt/payments/payments.env` (`BIND_ADDR=0.0.0.0`), run `restart-payments`, fix the port `{rp}` in `/etc/nginx/conf.d/payments.conf` and apply `nginx -s reload`.",
        ],
        "solution_summary": (
            f"1. On `payments-api`, `/opt/payments/payments.env` forced `BIND_ADDR=127.0.0.1` on port `{rp}`, blocking external connections from `edge-proxy`. Change it to `BIND_ADDR=0.0.0.0` and run `restart-payments`.\n"
            f"2. On `edge-proxy`, `/etc/nginx/conf.d/payments.conf` pointed to the wrong port `{wp}`. Update `proxy_pass` to `http://payments-api:{rp}` and run `nginx -s reload`."
        ),
        "nodes": {"edge-proxy": "nginx · reverse proxy :8080", "payments-api": "python · payments API"},
        "links": ["proxy_pass → backend port"],
        "entry": {"label": "you (curl)", "via": "HTTP :8080 /health"},
        "checks": {
            "api-listen": "payments-api accepts connections coming from other nodes",
            "nginx-valid": "The Nginx configuration is valid and leads to payments-api",
            "e2e-http": "GET http://127.0.0.1:8080/health from edge-proxy returns HTTP 200 and the live token",
        },
    }


def _firewall_drop(v: dict[str, Any]) -> dict[str, Any]:
    p = v["port"]
    return {
        "title": "Silent Telemetry Block",
        "briefing": "The `client-probe` container cannot query the `/metrics` endpoint of `metrics-srv`, although the process looks healthy locally on `metrics-srv`. Find the block and let `client-probe` download the metrics.",
        "blind_alert": "ALERTMANAGER [CRIT] · The `client-probe` collector stopped receiving HTTP metrics from the `metrics-srv` node. The platform team swears the exporter process is still running. Find out what is going on in the network.",
        "hints": [
            f"From `metrics-srv` try `curl http://127.0.0.1:{p}/metrics`, then from `client-probe` try `curl -v http://metrics-srv:{p}/metrics`. Why does it get `Connection refused` / RST if it listens on `0.0.0.0`?",
            "On `metrics-srv`, inspect the local firewall with `iptables -L -n -v` or `nft list ruleset`.",
            f"Remove the rule that blocks port `{p}` on `metrics-srv` (`iptables -D INPUT -p tcp --dport {p} -j REJECT --reject-with tcp-reset` or `iptables -F INPUT`).",
        ],
        "solution_summary": (
            f"The `exporter.py` process was listening correctly on `0.0.0.0:{p}`, but a `REJECT` rule in the `iptables` `INPUT` chain dropped external packets while accepting `lo`. "
            "Deleting the rule with `iptables -D INPUT ...` restores scraping from `client-probe`."
        ),
        "nodes": {"client-probe": "metrics collector (curl)", "metrics-srv": f"python · metrics exporter :{p}"},
        "links": [f"HTTP :{p} /metrics"],
        "entry": {"label": "you (shell)", "via": "curl /metrics"},
        "checks": {
            "exporter-alive": f"Exporter daemon listening locally on metrics-srv:{p}",
            "fw-clean": f"Nothing on metrics-srv blocks the TCP traffic arriving at port {p}",
            "remote-scrape": f"client-probe downloads metrics from http://metrics-srv:{p}/metrics",
        },
    }


def _acl_vault(v: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": "Ghost Permissions in the Month-End Close",
        "briefing": "The user `alumno` belongs to the `auditores` group and must be able to run `/srv/vault/close_month.sh` without `sudo` to generate `/srv/vault/out/report.ok`. Find out why the kernel denies access and fix it.",
        "blind_alert": "TICKET OPS-409 · The user `alumno` (a member of `auditores`) gets `Permission denied` when launching `/srv/vault/close_month.sh`, even though `ls -l` seems to show enough group permissions.",
        "hints": [
            "Look at the `+` sign at the end of the permissions in `ls -la /srv/vault /srv/vault/out`. Classic POSIX permissions don't tell the whole story.",
            "Inspect the access control lists with `getfacl /srv/vault/close_month.sh /srv/vault/out`: there are explicit entries for `user:alumno` and a mask (`mask::r--`) that trims group permissions.",
            "Clear the conflicting ACLs with `setfacl -b /srv/vault/close_month.sh /srv/vault/out` (and verify `chmod 770`) and test with `su - alumno -c /srv/vault/close_month.sh`.",
        ],
        "solution_summary": (
            "Although `alumno` belonged to the `auditores` group with mode `0770`, there were explicit ACL entries (`user:alumno:---` and `mask::r--`) on `/srv/vault/close_month.sh` and `user:alumno:r-x` on `/srv/vault/out`. "
            "Removing the anomalous ACLs with `setfacl -b` restores the effective permissions of the `auditores` group."
        ),
        "nodes": {"debian-vault": "bash · month-end close script"},
        "links": [],
        "entry": None,
        "checks": {
            "acl-script": "alumno can read and execute /srv/vault/close_month.sh",
            "acl-outdir": "The /srv/vault/out directory gives alumno effective write access without sudo",
            "run-as-alumno": "Running /srv/vault/close_month.sh as alumno generates /srv/vault/out/report.ok",
        },
    }


def _rocky_crlf_env(v: dict[str, Any]) -> dict[str, Any]:
    p = v["port"]
    return {
        "title": "Billing Daemon Broken After Migration",
        "briefing": "On this Rocky Linux 9 server, `/opt/billing/billingd.sh` fails when trying to bring up the billing microservice defined in `/etc/sysconfig/billing.env`. Fix every defect in the deployment until the port responds.",
        "blind_alert": "PAGERDUTY [SEV-2] · After a manual deployment on `rocky-billing`, the `/opt/billing/billingd.sh` daemon does not bring up the local billing port. Restore a clean service start.",
        "hints": [
            "Try running `/opt/billing/billingd.sh` or check its format with `file /opt/billing/billingd.sh`: it was uploaded from Windows with CRLF line endings (`\\r\\n`).",
            "After stripping the CRLF (`sed -i 's/\\r$//' /opt/billing/billingd.sh` and `chmod +x`), review `/etc/sysconfig/billing.env`: in Bash, assignments cannot have spaces around the `=`.",
            "Fix `BILLING_PORT=...` without spaces, grant write permission on `/var/run/billing` (`chmod 0755 /var/run/billing`) and launch `/opt/billing/billingd.sh`.",
        ],
        "solution_summary": (
            "Three chained faults after a manual deployment on Rocky Linux 9: "
            "(1) CRLF line endings and a missing `+x` on `/opt/billing/billingd.sh`, "
            "(2) invalid spaces in `BILLING_PORT = ...` inside `/etc/sysconfig/billing.env`, and "
            "(3) `/var/run/billing` with mode `0500` and no write permission."
        ),
        "nodes": {"rocky-billing": f"billingd.sh → python · billing :{p}"},
        "links": [],
        "entry": {"label": "you (curl)", "via": f"HTTP 127.0.0.1:{p}"},
        "checks": {
            "no-crlf": "/opt/billing/billingd.sh is executable and Bash parses it without format errors",
            "valid-env": "/etc/sysconfig/billing.env loads without errors and the daemon can write to its run directory",
            "service-up": f"Billing service up on 127.0.0.1:{p} returning the valid token",
        },
    }


def _zombie_log_cron(v: dict[str, Any]) -> dict[str, Any]:
    r = v["rogue_name"]
    return {
        "title": "Runaway Leak in /var/log with Persistence",
        "briefing": "A runaway process is filling `/var/log/ingest/overflow.log` and has a mechanism that periodically revives it. Neutralize the persistence, stop the culprit process, truncate `overflow.log` without deleting it and keep the original PID of `core-dispatcher` intact.",
        "blind_alert": "ALERTMANAGER [DISK-URGENT] · `/var/log/ingest/overflow.log` grows tens of KB per second and if you kill the process blindly it reappears the next minute. Do NOT restart or kill the critical process `core-dispatcher`!",
        "hints": [
            "Use `ps aux` and `ls -lh /var/log/ingest/` to identify which binary is inflating `overflow.log`, taking care NOT to kill `core-dispatcher`.",
            "Careful! Before or right after killing the runaway process, check `/etc/cron.d/`: a cron watchdog relaunches it every minute.",
            f"Remove or comment out `/etc/cron.d/ingest-watchdog`, kill only `{r}` (`pkill -f {r}`) and truncate the file in place with `truncate -s 0 /var/log/ingest/overflow.log` (or `: > /var/log/ingest/overflow.log`).",
        ],
        "solution_summary": (
            f"1. Disable the cron job `/etc/cron.d/ingest-watchdog` that resurrected `{r}` every minute.\n"
            f"2. Stop only `{r}`, preserving the original PID of `core-dispatcher`.\n"
            "3. Truncate `/var/log/ingest/overflow.log` to 0 bytes without deleting the inode."
        ),
        "nodes": {"debian-storage": "core-dispatcher (do not restart) · logs"},
        "links": [],
        "entry": None,
        "checks": {
            "cron-disarmed": "The persistence that revived the runaway process is disabled",
            "rogue-stopped-truncated": "Runaway process stopped and /var/log/ingest/overflow.log truncated (<1 KB) without deleting it",
            "core-untouched": "The critical worker core-dispatcher keeps its original PID intact (no restarts)",
        },
    }


def _dns_redis_split(v: dict[str, Any]) -> dict[str, Any]:
    rpass = v["rpass"]
    return {
        "title": "Resolution Hijack and Out-of-Sync Cache",
        "briefing": "The application on `app-node` uses `/opt/app/cache.conf` to query `cache.internal` through `/opt/app/healthcheck.sh`, but neither the name resolution nor the connection parameters match the active `redis-cache` server.",
        "blind_alert": "PAGERDUTY [SEV-2] · `/opt/app/healthcheck.sh` fails on `app-node` when trying to read the session state on `cache.internal`. You have access to both `app-node` and the `redis-cache` node.",
        "hints": [
            "Run `/opt/app/healthcheck.sh` on `app-node`. You will first see `Connection refused`: check which IP `cache.internal` resolves to (`getent hosts cache.internal`, `/etc/hosts`) and compare it with the IP of `redis-cache` (`ip a` on the `redis-cache` tab or `dig redis-cache`).",
            "On the `redis-cache` tab, review how Redis was started (`ps aux` and `/tmp/redis-chaos.conf`) to see the real port and the `requirepass` directive.",
            "Point `cache.internal` in `/etc/hosts` to the IP of `redis-cache` (edit it with `nano` or `vim`: in a container `/etc/hosts` is bind-mounted and `sed -i` fails with \"Device or resource busy\"), update `REDIS_PORT=6379` and `REDIS_PASSWORD` in `/opt/app/cache.conf`, and verify with `/opt/app/healthcheck.sh`.",
        ],
        "solution_summary": (
            "1. `/etc/hosts` on `app-node` hijacked `cache.internal` to `127.0.0.1` instead of the IP of the `redis-cache` node.\n"
            f"2. `/opt/app/cache.conf` had port `6380` (instead of `6379`) and an expired password instead of `{rpass}`."
        ),
        "nodes": {"app-node": "bash · healthcheck.sh (rcli client)", "redis-cache": "redis-server · session cache"},
        "links": ["TCP cache.internal → Redis"],
        "entry": {"label": "you (shell)", "via": "/opt/app/healthcheck.sh"},
        "checks": {
            "dns-resolution": "From app-node, cache.internal resolves first to the IP of redis-cache",
            "conf-updated": "The connection parameters in /opt/app/cache.conf match the active Redis",
            "healthcheck-ok": "/opt/app/healthcheck.sh retrieves the witness key from Redis",
        },
    }


def _sudoers_lockout(v: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": "Total Sudoers Lockout and Operator Account",
        "briefing": "You have entered through the `root` rescue console because `/etc/sudoers.d/90-ops` broke `sudo` and the `alumno` account got locked. Repair the permissions and syntax of `sudoers` and enable `alumno` to run `sudo -n /usr/local/bin/deploy-check`.",
        "blind_alert": "RESCUE SERIAL CONSOLE · A badly applied change left `sudo` unusable on the whole server and locked out the operator `alumno`, breaking the `/usr/local/bin/deploy-check` pipeline.",
        "hints": [
            "You are in the emergency console as `root`. Run `visudo -c` to diagnose why `sudo` rejects `/etc/sudoers.d/90-ops`.",
            "In `sudoers`, `NOPASSWD:` requires its colon and files in `/etc/sudoers.d/` require `0440` permissions. Also check `getent passwd alumno` and `passwd -S alumno`.",
            "Fix `/etc/sudoers.d/90-ops` to `alumno ALL=(ALL) NOPASSWD: /usr/local/bin/deploy-check`, apply `chmod 0440 /etc/sudoers.d/90-ops`, restore the shell with `usermod -s /bin/bash alumno` and unlock with `passwd -u alumno`.",
        ],
        "solution_summary": (
            "1. Fix the `NOPASSWD:` syntax error in `/etc/sudoers.d/90-ops` and set the permissions to `0440`.\n"
            "2. Restore the `/bin/bash` shell (`usermod -s /bin/bash alumno`) and unlock the account (`passwd -u alumno`)."
        ),
        "nodes": {"debian-sec": "sudo · deploy-check (root rescue)"},
        "links": [],
        "entry": None,
        "checks": {
            "sudoers-valid": "The sudo configuration is valid and /etc/sudoers.d/90-ops has safe permissions",
            "user-unlocked": "The alumno account is unlocked and can open an interactive session",
            "sudo-exec": "alumno runs 'sudo -n /usr/local/bin/deploy-check' without a password, successfully",
        },
    }


def _routing_blackhole(v: dict[str, Any]) -> dict[str, Any]:
    s, vip = v["subnet"], v["vip"]
    return {
        "title": "Routing Black Hole to a Remote Subnet",
        "briefing": "The `branch-srv` node serves an internal API on port `8090` over a virtual IP address configured on `lo`. However, `gateway-rtr` has a sabotaged routing table that prevents reaching that subnet. Fix the routing on `gateway-rtr`.",
        "blind_alert": "NOC TICKET [NET-88] · From `gateway-rtr` it is impossible to connect to the internal service on port `8090` of the VIP announced on the `lo` interface of `branch-srv` (`RTNETLINK` / dropped packets). Restore the IPv4 route.",
        "hints": [
            f"The service listens on the virtual IP `{vip}:8090` (configured on `lo` inside `branch-srv`). Try `ip route show` and `ip route get {vip}` from `gateway-rtr`.",
            f"You will see a `blackhole {s}` route blocking packets on `gateway-rtr`. Also find the network IP of `branch-srv` (`ping -c1 branch-srv` or `ip -4 addr` on `branch-srv`).",
            f"Run on `gateway-rtr`: `ip route del blackhole {s}` followed by `ip route add {s} via <IP_DE_BRANCH_SRV>` and check with `curl http://{vip}:8090/`.",
        ],
        "solution_summary": (
            f"On `gateway-rtr` there was a `blackhole {s}` route that dropped traffic to the VIP `{vip}` hosted on `branch-srv`. "
            f"Removing the blackhole route and adding `ip route add {s} via <IP_BRANCH_SRV>` restores L3 routing."
        ),
        "nodes": {"gateway-rtr": "Linux router · HTTP client", "branch-srv": f"python · API {vip}:8090 (on lo)"},
        "links": [f"IPv4 → subnet {s}"],
        "entry": {"label": "you (curl)", "via": f"HTTP {vip}:8090"},
        "checks": {
            "no-blackhole": f"gateway-rtr no longer drops traffic to {s}",
            "route-via-branch": f"gateway-rtr routes {s} through branch-srv",
            "reach-vip": f"gateway-rtr reaches the service at http://{vip}:8090/",
        },
    }


def _nginx_vhost_collision(v: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": "Ghost VirtualHost and Chained 403/503",
        "briefing": "On `nginx-vhost`, when requesting `http://127.0.0.1/` with the header `Host: portal.corp.local`, Nginx never serves `/var/www/portal/index.html`. Resolve the `server_name` collision, the blocking directive and the DocumentRoot permissions.",
        "blind_alert": "PAGERDUTY [WEB-04] · Requests to `http://portal.corp.local/` return a ghost maintenance page or HTTP 503/403 errors instead of the production portal.",
        "hints": [
            "Run `nginx -t`: you will see a warning about `conflicting server name \"portal.corp.local\"`. Review all the files in `/etc/nginx/conf.d/`.",
            "Besides the conflict in `00-trap.conf`, review `10-portal.conf` (it has a hardcoded `return 503;`) and the permissions of `/var/www/portal` (`ls -ld /var/www/portal /var/www/portal/index.html`).",
            "Remove `portal.corp.local` from `00-trap.conf`, change `return 503;` to `try_files $uri $uri/ =404;` in `10-portal.conf`, apply `chmod 755 /var/www/portal && chmod 644 /var/www/portal/index.html` and reload with `nginx -s reload`.",
        ],
        "solution_summary": (
            "1. `00-trap.conf` declared `server_name portal.corp.local _;`, stealing requests before `10-portal.conf`.\n"
            "2. `10-portal.conf` forced `return 503;` in `location /`.\n"
            "3. `/var/www/portal` had mode `0700` (`root:root`), producing `403 Forbidden` for the `nginx` worker user."
        ),
        "nodes": {"nginx-vhost": "nginx · vhost portal.corp.local :80"},
        "links": [],
        "entry": {"label": "you (curl)", "via": "HTTP :80 Host: portal.corp.local"},
        "checks": {
            "nginx-syntax": "Nginx configuration with no server_name collisions and OK syntax",
            "docroot-perms": "Permissions of /var/www/portal accessible to the Nginx worker process",
            "vhost-serves": "Host: portal.corp.local answers HTTP 200 with the real portal content",
        },
    }


def _boss_cascade(v: dict[str, Any]) -> dict[str, Any]:
    ap = v["api_port"]
    return {
        "title": "3:00 AM On-Call: Triple Cascade in Microservices",
        "briefing": "Boss scenario with 3 connected containers (`edge-lb`, `core-api` and `vault-db`). The transactional endpoint `http://127.0.0.1:8080/api/tx` on `edge-lb` must write to and read from `vault-db` through `core-api`, but all three layers have different faults.",
        "blind_alert": "MAJOR INCIDENT [SEV-0 · 03:14 AM] · Total transaction outage on `/api/tx` through `edge-lb:8080`. 3-node topology (`edge-lb` -> `core-api` -> `vault-db`). There are multiple simultaneous faults in different layers.",
        "hints": [
            "Follow the request layer by layer: `edge-lb (:8080)` -> `core-api` -> `vault-db (:6379)`. On `edge-lb`, look at where `proxy_pass` points in `/etc/nginx/conf.d/edge.conf`.",
            f"On `core-api`, try `curl -i http://127.0.0.1:{ap}/api/tx`. First you will see `DB_CONN_ERR` (check `iptables -S OUTPUT`). Once you open the firewall, you will see `READONLY You can't write against a read only replica`.",
            f"Promote `vault-db` to primary with `redis-cli REPLICAOF NO ONE` (and update `/tmp/redis-boss.conf` if you want), clear `iptables -F OUTPUT` on `core-api`, and point `edge-lb` to `http://core-api:{ap}/api/` with `nginx -s reload`.",
        ],
        "solution_summary": (
            "Triple cascading incident:\n"
            f"1. `edge-lb`: `/etc/nginx/conf.d/edge.conf` pointed to `127.0.0.1:{ap}` instead of `http://core-api:{ap}`.\n"
            "2. `core-api`: an `iptables OUTPUT` rule blocked destination port `6379`.\n"
            "3. `vault-db`: Redis was locked as a read-only replica (`replicaof 10.254.254.254 6379`); promote it with `redis-cli REPLICAOF NO ONE`."
        ),
        "nodes": {"edge-lb": "nginx · load balancer :8080", "core-api": "python · transactional API", "vault-db": "redis :6379"},
        "links": ["proxy_pass /api/", "TCP :6379 (reads and writes)"],
        "entry": {"label": "you (curl)", "via": "HTTP :8080 /api/tx"},
        "checks": {
            "db-writable": "vault-db accepts writes",
            "api-egress": "core-api reaches vault-db (TCP :6379)",
            "edge-upstream": "edge-lb gets /api/ through to core-api",
            "full-tx": "End-to-end transaction GET http://127.0.0.1:8080/api/tx on edge-lb returns HTTP 200",
        },
    }


def _wireguard_overlay(v: dict[str, Any]) -> dict[str, Any]:
    rp, wp, so = v["real_port"], v["wrong_port"], v["subnet_oct"]
    return {
        "title": "S2S WireGuard Tunnel Down and MTU Blackhole",
        "briefing": "The `hq-vpn-gw` node manages its tunnel to `branch-vpn-gw` through `/etc/wireguard/wg0.conf` and `wg-apply`, but it has combined faults in the Endpoint port, the AllowedIPs subnet and the MTU size.",
        "blind_alert": "NOC [VPN-S2S] · The tunnel between `hq-vpn-gw` and `branch-vpn-gw` does not carry traffic to the remote intranet and large HTTP responses get cut off abruptly. Restore `/etc/wireguard/wg0.conf`.",
        "hints": [
            "Review `/etc/wireguard/wg0.conf` on `hq-vpn-gw` and run `wg-apply` to see the warnings about handshake, `AllowedIPs` and `MTU`.",
            f"Check the internal IP of the remote node on `branch-vpn-gw` (`ip -4 addr show wg0` -> `10.{so}.0.2/24`). In `wg0.conf`, `AllowedIPs` pointed to a nonexistent `.99.2/32` subnet.",
            f"Set `Endpoint = <IP_BRANCH>:{rp}`, `AllowedIPs = 10.{so}.0.0/24` and `MTU = 1420` in `/etc/wireguard/wg0.conf`, and apply with `wg-apply`.",
        ],
        "solution_summary": (
            f"1. `Endpoint` in `/etc/wireguard/wg0.conf` pointed to port `{wp}` instead of `{rp}`.\n"
            f"2. `AllowedIPs` routed `10.{so}.99.2/32` instead of `10.{so}.0.0/24`.\n"
            "3. `MTU = 1580` dropped large TCP responses (>1400B); lowering to `MTU = 1420` and running `wg-apply` restores the tunnel."
        ),
        "nodes": {"hq-vpn-gw": "wg0 (HQ) · applied with wg-apply", "branch-vpn-gw": "wg0 (branch) · intranet :8440"},
        "links": ["wg0 tunnel (UDP) → HTTP :8440"],
        "entry": {"label": "you (curl)", "via": f"HTTP 10.{so}.0.2:8440"},
        "checks": {
            "wg-endpoint": f"The Endpoint in wg0.conf reaches the peer and there is a route to the intranet 10.{so}.0.2",
            "wg-mtu": "The wg0 MTU fits inside the tunnel",
            "wg-payload": f"Download of a large payload (>2 KB) from http://10.{so}.0.2:8440 completes without MTU blocking",
        },
    }


def _tls_expired_san(v: dict[str, Any]) -> dict[str, Any]:
    tp = v["tls_port"]
    return {
        "title": "X.509 SAN Failure on the Corporate HTTPS Gateway",
        "briefing": "The `tls-gateway` serves HTTPS with a certificate issued by the local CA `/etc/ssl/corp-ca/`, but `api-client` aborts the TLS handshake when verifying the certificate identity. Reissue the certificate correctly.",
        "blind_alert": "SECOPS [TLS-ERR] · Strict clients on `api-client` reject the HTTPS connection to `vault.corp.internal` even though they trust the root CA `/etc/ssl/corp/ca.crt`. Disabling TLS verification on the client is forbidden.",
        "hints": [
            f"On `api-client`, run `curl -v --cacert /etc/ssl/corp/ca.crt https://vault.corp.internal:{tp}/status` to see the exact reason for the X.509 rejection.",
            "On `tls-gateway`, inspect `openssl x509 -in /opt/tls/server.crt -noout -subject -ext subjectAltName`. You will see it was issued for `legacy-vault.corp.internal`.",
            "Generate a new CSR/certificate in `/opt/tls/` with `subjectAltName = DNS:vault.corp.internal`, signing it with `/etc/ssl/corp-ca/ca.crt` and `/etc/ssl/corp-ca/ca.key`, and run `restart-tls-gw`.",
        ],
        "solution_summary": (
            "The certificate `/opt/tls/server.crt` had `DNS:legacy-vault.corp.internal` in `subjectAltName`, causing a hostname verification failure on strict clients.\n"
            "Fix: reissue `/opt/tls/server.crt` with `-extfile <(printf 'subjectAltName=DNS:vault.corp.internal')` signed by `/etc/ssl/corp-ca/ca.{crt,key}` and run `restart-tls-gw`."
        ),
        "nodes": {"api-client": "strict HTTPS client (curl, no -k)", "tls-gateway": f"python · HTTPS gateway :{tp}"},
        "links": [f"HTTPS :{tp} /status (TLS verified with the corporate CA)"],
        "entry": {"label": "you (shell)", "via": "curl https://vault.corp.internal"},
        "checks": {
            "cert-san": "The gateway certificate is valid for the name vault.corp.internal",
            "cert-chain": "The server certificate is validly signed by /etc/ssl/corp-ca/ca.crt",
            "client-strict-https": f"Client validates strict TLS (no -k) against https://vault.corp.internal:{tp}/status",
        },
    }


def _dns_soa_serial(v: dict[str, Any]) -> dict[str, Any]:
    bs, hp = v["base_serial"], v["http_port"]
    return {
        "title": "Authoritative DNS Zone: SOA Serial and Broken CNAME",
        "briefing": "Repair the `A` and `CNAME` records in `/etc/bind/zones/db.corp.lan` on `ns1-master`, make sure you follow the SOA Serial rule and reload with `named-reload` until `app-client` connects by name.",
        "blind_alert": "PAGERDUTY [DNS-53] · Clients on `app-client` cannot resolve `portal.corp.lan` against `ns1-master` after a failed manual edit of `/etc/bind/zones/db.corp.lan`.",
        "hints": [
            "From `app-client`, try `dig portal.corp.lan` and `dig api.corp.lan`. Look at which FQDN the CNAME expands to and which IP `api` returns.",
            "On `ns1-master`, open `/etc/bind/zones/db.corp.lan` and check `/etc/chaos_nodes.env` for `IP_NS1_MASTER`. Remember what happens in BIND when you forget the trailing dot (`.`) in `api.corp.lan.`.",
            f"Fix `api IN A <IP_NS1_MASTER>`, add the trailing dot in `portal IN CNAME api.corp.lan.`, increment the SOA Serial (> `{bs}`) and run `named-reload`.",
        ],
        "solution_summary": (
            "1. `api` pointed to `10.254.99.99` instead of the real IP of `ns1-master`.\n"
            "2. `portal IN CNAME api.corp.lan` lacked the trailing dot (`.`), expanding to `api.corp.lan.corp.lan.`.\n"
            f"3. It was mandatory to increment the SOA Serial above `{bs}` before running `named-reload`."
        ),
        "nodes": {"app-client": "client · DNS + HTTP", "ns1-master": f"authoritative DNS :53 · web :{hp}"},
        "links": [f"DNS :53 + HTTP :{hp} /ready"],
        "entry": {"label": "you (shell)", "via": "curl portal.corp.lan /ready"},
        "checks": {
            "soa-bumped": f"SOA serial incremented above {bs} and zone reloaded",
            "dig-portal": "dig @ns1-master portal.corp.lan resolves to the real IP of ns1-master",
            "http-portal": f"app-client connects to http://portal.corp.lan:{hp}/ready using DNS",
        },
    }


def _cloud_az_nsg_udr(v: dict[str, Any]) -> dict[str, Any]:
    dp, vn = v["db_port"], v["vip_net"]
    return {
        "title": "Cloud Networking: UDR, NVA Forwarding and NSG",
        "briefing": "Classic AZ-104 Hub-and-Spoke architecture scenario with 3 nodes (`vnet-web` -> `nva-fw` -> `vnet-db`). Diagnose and fix the user-defined route (UDR), the IP forwarding on the appliance and the NSG security rules.",
        "blind_alert": "AZURE MONITOR [VNET-CRIT] · `vnet-web` cannot reach the backend VIP on `vnet-db` through the Virtual Appliance `nva-fw`. Review the UDR route tables, the NVA IP Forwarding and the priority rules in `NSG_INBOUND`.",
        "hints": [
            f"On `vnet-web`, review `ip route show` looking for `{vn}.0/24` and check the IP of `nva-fw` in `/etc/chaos_nodes.env`.",
            "After replacing the `blackhole` route with `via <IP_NVA_FW>`, review the `/etc/nva_appliance.conf` file on `nva-fw` and the `nva-apply` command.",
            f"Finally, on `vnet-db` inspect `iptables -L NSG_INBOUND -n --line-numbers`: the `prio-100-deny-legacy` rule blocks port `{dp}` before the `ACCEPT`.",
        ],
        "solution_summary": (
            f"1. `vnet-web`: remove `ip route del blackhole {vn}.0/24` and add `ip route add {vn}.0/24 via $IP_NVA_FW`.\n"
            "2. `nva-fw`: set `ENABLE_IP_FORWARDING=true` in `/etc/nva_appliance.conf` and run `nva-apply`.\n"
            "3. `vnet-db`: delete the highest-priority rule with `iptables -D NSG_INBOUND 1` (`prio-100-deny-legacy`)."
        ),
        "nodes": {"vnet-web": "web workload (spoke) · backend client", "nva-fw": "NVA (hub) · forwards packets", "vnet-db": f"python · backend {vn}.10:{dp}"},
        "links": ["UDR · next hop Virtual Appliance", f"TCP :{dp}"],
        "entry": {"label": "you (shell)", "via": f"curl {vn}.10:{dp}"},
        "checks": {
            "udr-web": f"UDR on vnet-web routes {vn}.0/24 to the Virtual Appliance next hop (nva-fw)",
            "nva-fwd": "IP Forwarding enabled and applied on the nva-fw appliance",
            "nsg-e2e": f"Traffic from vnet-web reaches http://{vn}.10:{dp} after fixing NSG_INBOUND",
        },
    }


def _ssh_bruteforce(v: dict[str, Any]) -> dict[str, Any]:
    p, legit = v["ssh_port"], v["legit_user"]
    return {
        "title": "SSH Brute Force: Detect and Block with nftables",
        "briefing": "An external node (`bot-externo`) launches a brute-force attack against the real `sshd` on `ssh-victim`, while `ops-client` logs in legitimately. Identify the attacker IP in the logs, block it with nftables persistently (`/etc/nftables.conf`) and verify that legitimate SSH still works.",
        "blind_alert": "SIEM [SSH-BRUTE] · `ssh-victim` accumulates a burst of `Failed password` entries and nonexistent users in `/var/log/auth.log`. The operations team still needs to SSH in from `ops-client`. Contain the attack without cutting legitimate access.",
        "hints": [
            "On `ssh-victim` look at `/var/log/auth.log`: `grep 'Failed password' /var/log/auth.log | sed -E 's/.* from ([0-9.]+) port.*/\\1/' | sort | uniq -c | sort -rn`. One IP concentrates almost all the failures; another (the one from `ops-client`) only shows up in successful logins.",
            "Check which IP is the legitimate one before blocking: `grep Accepted /var/log/auth.log`. Blocking the whole subnet would also cut off `ops-client`.",
            f"Add a rule to the `input` chain of `inet filter`: `nft add rule inet filter input ip saddr <IP_ATACANTE> tcp dport {p} drop`. The in-memory ruleset is lost on reboot: write the same rule inside the `input` chain of `/etc/nftables.conf` and validate it with `nft -c -f /etc/nftables.conf`.",
        ],
        "solution_summary": (
            f"`bot-externo` launched a password brute-force attack against `ssh-victim:{p}` (hundreds of `Failed password` entries and nonexistent users in `/var/log/auth.log`), "
            f"while `ops-client` logged in legitimately as `{legit}`.\n"
            "Fix: identify the IP with `grep 'Failed password' /var/log/auth.log | ... | sort | uniq -c | sort -rn`, block it with "
            "`nft add rule inet filter input ip saddr <IP> drop` (without touching the subnet) and make it persistent by adding `ip saddr <IP> drop` to the `input` chain of `/etc/nftables.conf`."
        ),
        "nodes": {"ops-client": "operations SSH client (ops-ssh)", "ssh-victim": f"sshd :{p}", "bot-externo": "automated SSH client"},
        "links": [f"SSH :{p}", f"SSH :{p}"],
        "entry": None,
        "checks": {
            "sshd-alive": f"sshd is still listening on ssh-victim:{p} (the service has not been stopped)",
            "legit-login": f"ops-client still logs in over SSH as `{legit}` (the legitimate client is not cut off)",
            "attacker-cut": f"bot-externo can no longer open TCP connections to port {p} of ssh-victim",
            "nft-rule-live": "The active nftables ruleset on ssh-victim contains a drop/reject on the attacker IP",
            "nft-persistent": "The rule is persistent: /etc/nftables.conf (or /etc/nftables.d) includes the attacker IP and passes `nft -c`",
        },
        "signals": [
            "{1} sshd authentication failures on ssh-victim from {2} (sustained burst)",
            "{1} distinct usernames tried against sshd (many nonexistent)",
            "spike of new connections to the SSH port: ~{1} attempts/min with no established session",
            "{1} successful login(s) by legitimate users in the same interval",
        ],
    }


def _portscan_detect(v: dict[str, Any]) -> dict[str, Any]:
    p = v["service_port"]
    return {
        "title": "Port Scan: Detection and Mitigation with nftables",
        "briefing": "`recon-bot` sweeps the ports of `edge-srv` in a loop. A sensor leaves the incoming SYNs in `/var/log/portwatch.log`. Detect the scanner, mitigate it with nftables (drop its IP or `limit rate`) and keep the legitimate service reachable.",
        "blind_alert": "IDS [RECON-SCAN] · `edge-srv` records a spike of new connections to hundreds of different ports. The inventory service must remain reachable for `app-client`. Locate the source and mitigate it.",
        "hints": [
            "On `edge-srv` the kernel log is not visible from the container: the `portwatch` sensor leaves incoming SYNs in `/var/log/portwatch.log`. Count sources: `grep -o 'SRC=[0-9.]*' /var/log/portwatch.log | sort | uniq -c | sort -rn`, and distinct ports per source with `grep SRC=<ip> ... | grep -o 'DPT=[0-9]*' | sort -u | wc -l`.",
            "Legitimate sources talk only to the service port; the scanner touches thousands of distinct ports. Compare with `ss -ltnp` to see what is really open.",
            "Mitigate only the scanner: `nft add rule inet filter input ip saddr <IP> drop`, or limit new connections per source (`nft add rule inet filter input ct state new tcp dport != <puerto> limit rate over 10/second drop`). `app-client` must still reach the service.",
        ],
        "solution_summary": (
            f"`recon-bot` swept thousands of ports on `edge-srv` (visible in `/var/log/portwatch.log`: one source with thousands of distinct `DPT` values), while `app-client` only used port `{p}`.\n"
            "Fix: find the scanner IP by counting sources and ports in the log and drop it in the nftables `input` chain "
            "(`nft add rule inet filter input ip saddr <IP> drop`) or apply `limit rate over N/second drop` to new connections, without breaking the legitimate client."
        ),
        "nodes": {"app-client": "inventory client (inventory-call)", "edge-srv": f"python · inventory service :{p}", "recon-bot": "automated TCP client"},
        "links": [f"HTTP :{p} /health", "TCP"],
        "entry": None,
        "checks": {
            "service-up": f"The inventory service is still healthy on edge-srv:{p}",
            "legit-client": f"app-client consumes http://edge-srv:{p}/health with no errors (legitimate service reachable)",
            "nft-mitigation": "An nftables input chain (hook input) on edge-srv contains a mitigation (drop / reject / limit rate)",
            "scan-mitigated": "A fast sweep of 120 closed ports from recon-bot no longer gets a flood of RSTs (dropped or rate-limited)",
        },
        "signals": [
            "spike of new connections: {1} SYNs to edge-srv from {2} in {3} s",
            "{1} distinct destination ports probed by a single source (sequential scan pattern)",
            "{1} ports answering on edge-srv (the rest return RST): the scan has already mapped open services",
            "legitimate traffic to the service keeps arriving from a source other than the spike's",
        ],
    }


def _dns_exfil(v: dict[str, Any]) -> dict[str, Any]:
    domain, hidden, script, cron_name, mode, zone = v["c2_domain"], v["hidden_dir"], v["script"], v["cron_name"], v["cron_mode"], v["zone"]
    cron = f"/etc/cron.d/{cron_name}" if mode == "etc" else "root's crontab"
    return {
        "title": "DNS Exfiltration: Hunt the Process and Cut the Outbound Path",
        "briefing": "A persistent process on `infected-host` exfiltrates data encoded in DNS subdomains to an external server. Identify the process/cron job and the domain, stop it, remove the persistence and block the unauthorized outbound DNS with nftables while keeping resolution through `corp-dns`.",
        "blind_alert": "EDR [DNS-TUNNEL] · `infected-host` emits anomalous, very long DNS queries to the outside. There is customer data in `/srv/finance`. Cut the leak without breaking internal resolution.",
        "hints": [
            "On `infected-host` the `dnsaudit` sensor logs every outgoing DNS query in `/var/log/dnsaudit.log`: sort by `LEN=` and look at `DST=` and `QNAME=`. A legitimate QNAME is a few characters long; the encoded ones are over 50.",
            "Find who is sending it: `ss -uanp` (which IP:53 is it talking to?), `ps aux --forest` and the task schedulers (`ls /etc/cron.d`, `crontab -l`). The process lives in a hidden directory under `/var/tmp`.",
            "Stop the process (`pkill -f`), remove the cron entry (and the script) and block with nftables any DNS egress that does not go to the authorized resolver: `nft add rule inet filter output udp dport 53 ip daddr != <IP_corp-dns> drop` (and the same for `tcp`).",
        ],
        "solution_summary": (
            f"A hidden script at `{hidden}/{script}`, relaunched by cron every minute (`{cron}`), "
            f"encoded `/srv/finance/clientes.csv` in base32 and sent it in long subdomains of `{domain}` straight to `ns-externo` over UDP/53, bypassing the corporate resolver.\n"
            "Fix: locate it in `/var/log/dnsaudit.log` (QNAME > 50 characters to an IP that is not `corp-dns`), kill the process, remove the cron persistence and "
            "block with `nft add rule inet filter output udp dport 53 ip daddr != <IP_corp-dns> drop` so that only authorized resolution remains."
        ),
        "nodes": {"corp-dns": f"corporate resolver :53 · {zone}", "infected-host": "application host · /srv/finance", "ns-externo": "DNS server :53 outside the company"},
        "links": ["DNS :53", "DNS :53"],
        "entry": None,
        "checks": {
            "exfil-process-dead": "On infected-host no process is sending data anymore (the responsible process is stopped)",
            "persistence-gone": "The persistence (cron) that relaunched the process is gone from infected-host",
            "dns-egress-blocked": "nftables on infected-host blocks outbound DNS to the unauthorized external server",
            "dns-legit-ok": f"Legitimate resolution still works: portal.{zone} via corp-dns",
            "exfil-stopped-at-ns": "ns-externo has gone more than 8 s without receiving any new query (the exfiltration has stopped)",
        },
        "signals": [
            "{1} DNS queries with a QNAME over 50 characters are leaving infected-host",
            "the long queries are addressed to {1}, a destination that is not the corporate resolver",
            "{1} unique subdomains under a single second-level domain (apparently encoded strings)",
            "regular cadence: one long query every ~{1} s (automated beaconing behavior)",
        ],
    }


EN: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "net-nginx-bad-gateway": _nginx_bad_gateway,
    "net-firewall-drop": _firewall_drop,
    "sec-acl-shared-vault": _acl_vault,
    "sys-rocky-crlf-env": _rocky_crlf_env,
    "sto-zombie-log-cron": _zombie_log_cron,
    "net-dns-redis-split": _dns_redis_split,
    "sec-sudoers-lockout": _sudoers_lockout,
    "net-routing-blackhole": _routing_blackhole,
    "web-nginx-vhost-collision": _nginx_vhost_collision,
    "chaos-boss-cascade": _boss_cascade,
    "vpn-wireguard-overlay": _wireguard_overlay,
    "sec-tls-expired-san": _tls_expired_san,
    "net-dns-soa-serial": _dns_soa_serial,
    "cloud-az-nsg-udr": _cloud_az_nsg_udr,
    "sec-ssh-bruteforce": _ssh_bruteforce,
    "sec-portscan-detect": _portscan_detect,
    "sec-dns-exfil": _dns_exfil,
}


def apply_en(inst: dict[str, Any]) -> None:
    """Añade inst["i18n"]["en"] (y `label_en` en cada sonda) si el escenario en código tiene traducción.
    No pisa un i18n que ya traiga el builder."""
    fn = EN.get(inst.get("id", ""))
    if not fn or (inst.get("i18n") or {}).get("en"):
        return
    en = fn(inst.get("vars") or {})
    topo = inst.get("topology") or {}
    checks = en.pop("checks", {})
    for c in inst.get("checks") or []:
        if c.get("id") in checks:
            c["label_en"] = checks[c["id"]]
    runs = en.pop("nodes", {})
    en["nodes"] = {
        role: {"runs": runs[role], "look": list((topo.get("nodes", {}).get(role) or {}).get("look", []))}
        for role in runs
    }
    ent = en.pop("entry", None)
    if ent and topo.get("entry"):
        en["entry"] = {"label": ent["label"], "via": ent["via"]}
    inst["i18n"] = {"en": en}
