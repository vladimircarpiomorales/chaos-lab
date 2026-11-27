# ⚡ Chaos Lab — Arena Interactiva de Incidentes Linux, Redes y SRE

Simulador local de averías reales (*Break & Fix*) construido desde cero sobre **FastAPI + WebSockets PTY + xterm.js + Podman rootless**.

## Características principales

- **Topologías reales de 1 a 3 nodos en red aislada (`chaoslab-net`)**:
  - Terminales interactivas completas (`vim`, `nano`, `top`, `Tab`, `Ctrl+C`, redimensionado automático) en pestañas separadas por contenedor.
  - Multi-distro con imágenes propias (`chaos-debian`, `chaos-rocky`, `chaos-nginx`, `chaos-redis`) que traen de serie nano, vim, ss, dig, curl… `arrancar.sh` las construye la primera vez.
- **Chaos Mutator (Semilla dinámica)**:
  - Cada despliegue muta puertos, contraseñas, tokens de salud, nombres de procesos o subredes IPv4 para que tengas que diagnosticar en vez de memorizar comandos.
- **Modo Guardia 3:00 AM (`+25% XP`)**:
  - Lanza un incidente aleatorio ocultando el nombre del escenario y las descripciones de las sondas tras una alerta estilo PagerDuty/Alertmanager.
- **Verificación granular por sondas SLO + Rangos (`S+`, `S`, `A`, `B`, `C`)**:
  - Comprueba cada capa del incidente en vivo sin regalar la respuesta.
- **Mentor SRE Socrático + Exportación Post-Mortem (`.md`)**:
  - Se conecta automáticamente a tu **Ollama local** si está encendido (o usa heurística local si está apagado) leyendo los comandos que ya probaste en la terminal.
  - Genera un informe Post-Mortem en Markdown con cronología de comandos y análisis de causa raíz.

## Uso rápido

```bash
git clone https://github.com/vladimircarpiomorales/chaos-lab.git && cd chaos-lab
./arrancar.sh              # Arranca en http://127.0.0.1:7820/ y abre el navegador
./arrancar.sh --estado     # Comprueba salud del servidor y Podman
./arrancar.sh --parar      # Detiene el servidor y destruye cualquier contenedor chaoslab-*
```
