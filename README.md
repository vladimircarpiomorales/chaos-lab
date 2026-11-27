# ⚡ Chaos Lab — Arena de incidentes Linux, redes y SRE

Laboratorio local de averías reales (*Break & Fix*): despliega 1–3 contenedores con un fallo inyectado, te da una terminal en cada uno desde el navegador y comprueba en vivo, capa por capa, si lo has arreglado.

Pensado para practicar troubleshooting de verdad (LPIC-1/2, CCNA, AZ-104, guardias SRE) sin romper tu sistema: todo ocurre en contenedores aislados que se destruyen al terminar.

## Qué tiene

- **17 escenarios** de 1 a 3 nodos: proxies y 502, cortafuegos, DNS, routing, VPN y MTU, TLS, permisos y ACL, sudo, cron, y Blue Team (fuerza bruta SSH, escaneo de puertos, exfiltración por DNS).
- **Terminal real en cada nodo** (xterm.js por WebSocket): `vim`, `nano`, `Tab`, `Ctrl+C`… Cada nodo trae de serie nano, vim, less, curl, ss, dig y ps, y la interfaz te dice qué herramientas tiene.
- **Esquema de la topología** con el recorrido de la petición; tras «Verificar» se pone verde donde ya funciona y rojo donde no. Clic en un nodo abre su terminal.
- **Semilla aleatoria**: cada despliegue cambia puertos, contraseñas, nombres de procesos o subredes, para que diagnostiques en vez de memorizar.
- **Sondas sin spoilers**: dicen *qué* tiene que funcionar, nunca qué está roto. Las pistas son graduales (3 por escenario).
- **Modo Guardia 3:00 AM**: incidente al azar con solo una alerta tipo PagerDuty; sin título, sin esquema detallado y sin etiquetas de sondas.
- **Mentor socrático** (opcional, con [Ollama](https://ollama.com) local) que lee los comandos que ya probaste, y **post-mortem en Markdown** con la cronología.

## Requisitos

- Linux con **Podman 4+** (rootless) **o Docker** 24+. Probado en Debian 13 con Podman 5.4 y en Ubuntu 24.04 con Docker 29.
  Si tienes los dos, usa Podman; para forzar uno: `CHAOS_RUNTIME=docker` en `.env`.
- **Python 3.11+** con el módulo `venv` (`apt install python3-venv` en Debian/Ubuntu).
- ~1 GB libre para las imágenes y **conexión a internet la primera vez** (se construyen las imágenes y se instalan las dependencias).

## Instalación y uso

```bash
git clone https://github.com/vladimircarpiomorales/chaos-lab.git && cd chaos-lab
./arrancar.sh              # la 1ª vez prepara .venv e imágenes; luego abre http://127.0.0.1:7820/
./arrancar.sh --estado     # salud del servidor y del motor de contenedores
./arrancar.sh --reiniciar  # reinicia el servidor (¡destruye el laboratorio en curso!)
./arrancar.sh --parar      # para el servidor y borra los contenedores chaoslab-*
```

Elige un escenario, pulsa **▶ Desplegar**, investiga en las terminales y pulsa **Verificar** cuando creas que está arreglado.

## Escenarios

| Escenario | Nivel | Nodos |
|---|---|---|
| Permisos Fantasma en Cierre Contable | Básico | 1 |
| Demonio de Facturación Roto tras Migración | Básico | 1 |
| 502 Bad Gateway en Pasarela de Pagos | Intermedio | 2 |
| Bloqueo Silencioso de Telemetría | Intermedio | 2 |
| Fuga Desbocada en /var/log con Persistencia | Intermedio | 1 |
| Secuestro de Resolución y Caché Desincronizada | Intermedio | 2 |
| Bloqueo Total de Sudoers y Cuenta Operativa | Intermedio | 1 |
| VirtualHost Fantasma y 403/503 Encadenados | Intermedio | 1 |
| Fallo X.509 de SAN en Pasarela Corporativa HTTPS | Intermedio | 2 |
| Zona DNS Autoritativa: Serial SOA y CNAME Roto | Intermedio | 2 |
| Fuerza Bruta SSH: Detectar y Bloquear con nftables | Intermedio | 3 |
| Escaneo de Puertos: Detección y Mitigación con nftables | Intermedio | 3 |
| Agujero Negro de Enrutamiento hacia Subred Remota | Avanzado | 2 |
| Túnel WireGuard S2S Caído y Bloqueo por MTU | Avanzado | 2 |
| Exfiltración por DNS: Cazar el Proceso y Cortar la Salida | Avanzado | 3 |
| Guardia 3:00 AM: Cascada Triple en Microservicios | Experto | 3 |
| Cloud Networking: UDR, NVA Forwarding y NSG | Experto | 3 |

## Configuración

Opcional, en un fichero `.env` en la raíz del repo (no se sube a git):

| Variable | Por defecto | Para qué |
|---|---|---|
| `CHAOS_PORT` | `7820` | Puerto de la interfaz web |
| `CHAOS_HOST` | `127.0.0.1` | Dirección de escucha (déjala en local, ver *Seguridad*) |
| `CHAOS_RUNTIME` | autodetección | `podman` o `docker` |
| `CHAOS_EXPORT_DIR` | `./exports` | Dónde se guardan los post-mortem (p. ej. una carpeta de tu bóveda de Obsidian) |

Las imágenes `chaos-debian`, `chaos-rocky`, `chaos-nginx` y `chaos-redis` se construyen con `images/construir.sh` (lo hace `arrancar.sh` solo si faltan). Si no existen, se usan las imágenes oficiales, que funcionan pero sin las herramientas de serie.

## Seguridad

- El servidor escucha **solo en `127.0.0.1`**. No lo expongas a la red: da una shell root dentro de los contenedores a quien abra la página.
- Los contenedores corren como **root dentro del contenedor** (rootless desde fuera con Podman; con Docker, según tu instalación) y algunos escenarios piden `NET_ADMIN`/`NET_RAW` para tocar rutas y cortafuegos **dentro** de su propia red.
- Todo ocurre en la red aislada `chaoslab-net`; `--parar` borra contenedores y red.
- El usuario de prácticas `alumno` tiene la contraseña `alumno`: solo existe dentro de los contenedores.

## Desarrollo

```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q tests                       # coherencia, esquemas y reglas sin spoilers (sin contenedores)
tests/e2e/probar.sh <escenario> tests/e2e/soluciones/<escenario>.sh   # prueba real: despliega, resuelve y verifica
```

¿Quieres añadir un escenario? Lee [CONTRIBUTING.md](CONTRIBUTING.md). Cada escenario es una función `_build_*` en `chaos_lab/scenarios.py` (o `scenarios_secops.py`) que devuelve nodos, setup con la avería, sondas, pistas, esquema y solución.

## Licencia

[MIT](LICENSE). Incluye [xterm.js](https://xtermjs.org/) (MIT, ver `static/vendor/LICENSE-xterm`).
