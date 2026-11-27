# Cómo contribuir a Chaos Lab

¡Gracias! Lo más valioso que puedes aportar es **un escenario nuevo** (una avería realista). Esta guía explica cómo se escribe, las reglas que lo mantienen jugable y cómo probarlo antes de abrir el pull request.

## Anatomía de un escenario

Cada escenario son dos piezas en `chaos_lab/scenarios.py` (o `scenarios_secops.py` para Blue Team):

1. Una función `_build_<nombre>(rng)` que devuelve un `dict` con:

   | Clave | Qué es |
   |---|---|
   | `vars` | Valores aleatorios de esta partida (puertos, contraseñas, nombres…). Sácalos de `rng` para que cada despliegue sea distinto. |
   | `nodes` | 1–3 nodos: `role`, `distro` (`debian`, `rocky`, `nginx`, `redis`), `shell`, `default_user`, `setup_sh` (monta el servicio **e inyecta la avería**) y, si hace falta, `caps` (`NET_ADMIN`, `NET_RAW`) o `sysctls`. |
   | `checks` | Sondas: `id`, `label` (lo que ve el jugador), `node` y `cmd` (código de salida 0 = verde). |
   | `hints` | Exactamente 3 pistas, de menos a más: orientar → señalar el sitio → casi la solución. |
   | `topology` | El esquema: `entry`, `nodes` (`runs` y `look` por rol), `links` y en qué sitio del dibujo va cada sonda. |
   | `solution_summary` | La explicación que se muestra al resolver. |

2. Una entrada en `SCENARIO_CATALOG`: `id`, `title`, `category`, `difficulty`, `points`, `estimated_min`, `tags`, `certs`, `blind_alert` (alerta del Modo Guardia), `briefing` y `builder`.

Copia uno existente parecido al tuyo y adáptalo: es la forma más rápida.

## Reglas «sin spoilers» (las comprueban las pruebas)

El jugador ve, **antes de resolver**, el briefing, las etiquetas de las sondas y el esquema. Nada de eso puede regalar la solución:

- **Etiquetas de sondas = objetivo observable**, nunca el fallo ni el valor correcto.
  ✅ «payments-api acepta conexiones que llegan desde otros nodos» · ❌ «payments-api escucha en 0.0.0.0:9025».
- **`look` («dónde mirar») = dónde miraría un sysadmin**, nunca un comando o fichero que aparece entre `backticks` en las pistas (salvo que ya lo diga el briefing o la alerta).
- **`runs` y `via` describen cómo *debería* funcionar**, no qué está roto.
- **Los datos secretos** (el puerto real cuando el reto es encontrarlo, el nombre del proceso culpable, contraseñas, dominios del atacante, tokens) solo pueden salir en la pista 3 y en la solución. Nómbralos `real_port`, `wrong_port`, `rogue_name`, `rpass`, `c2_domain`, `hidden_dir`, `decoys`, `token`… o añade el nombre a `SECRET_VARS` en `tests/test_sin_spoilers.py`.
- Las **`tags`** (tecnologías) delatan la causa: la interfaz las oculta hasta resolver. Las **`certs`** (LPIC-1, LPIC-2, CCNA, CCNP, AZ-104) sí se ven.

## Sondas que no mienten

- Prueba **lo que importa al usuario**, no un detalle de implementación: si hay varias formas correctas de arreglarlo, la sonda debe aceptarlas todas (p. ej. cualquier shell de `/etc/shells`, no solo `/bin/bash`).
- Cuidado con `pgrep -f`/`pkill -f`: la propia línea de la sonda contiene el patrón y se encuentra a sí misma. Usa el truco del corchete: `pgrep -f '/ruta/[n]ombre'`.
- Cuidado con los falsos verdes: si el arreglo bueno y el truco malo dan la misma salida, la sonda no sirve (p. ej. `getent hosts` devuelve **todas** las líneas de `/etc/hosts`; compara la primera).
- En contenedores `/etc/hosts` está montado: `sed -i` falla. Si tu escenario pide editarlo, dilo en las pistas (nano/vim).

## Dificultad

| Nivel | Criterio |
|---|---|
| Básico | 1 nodo, 1–2 fallos que se ven con un comando estándar. |
| Intermedio | 1–3 nodos, hasta 3 fallos; hay que leer logs o configuración para encontrar la causa. |
| Avanzado | Varias capas (red + servicio) o un dato oculto que hay que deducir (ruta, IP atacante, MTU). |
| Experto | 3 nodos y 3+ fallos encadenados en capas distintas: arreglar uno descubre el siguiente. |

`category` es una de: Redes y routing · DNS · Servicios web y TLS · Sistema y permisos · Seguridad (Blue Team) · Incidente mayor.

## Probar antes del pull request

```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q tests     # coherencia, esquema y reglas sin spoilers (sin contenedores)
```

Y **en real**: escribe la solución en `tests/e2e/soluciones/<id>.sh` (usa `"$RT" exec "$C_<ROL>" …`; tienes `C_<ROL>` e `IP_<ROL>` de cada nodo) y ejecuta con Chaos Lab arrancado:

```bash
tests/e2e/probar.sh <id> tests/e2e/soluciones/<id>.sh
```

Debe salir **todo ✗ antes** (salvo sondas de «no romper lo que funciona») y **todo ✓ después**. Las pruebas no suman XP ni historial. Si puedes, pruébalo con Podman y con Docker (`CHAOS_RUNTIME=docker`).

## Estilo

- Textos en español, frases cortas; comandos, ficheros y términos TI sin traducir (namespace, host, proxy_pass…).
- Datos (puertos, rutas) entre `backticks` o en campos aparte, no mezclados en el texto: facilita la futura traducción al inglés.
