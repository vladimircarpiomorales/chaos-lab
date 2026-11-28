/* Chaos Lab · i18n (ES | EN) — sin dependencias ni paso de compilación.
   El español es el idioma por defecto y la fuente; t(clave, {vars}) usa {nombre} y cae en en → es → clave.
   Idioma: localStorage["chaos-lang"], si no navigator.language ("es*" → es, resto → en). */

(function () {
  const es = {
    /* ---- Cabecera ---- */
    "app.title": "Chaos Lab · Arena SRE y Troubleshooting Linux/Red",
    "app.subtitle": "Simulador Interactivo de Incidentes Linux · Redes · Multi-Nodo",
    "pill.engineTip": "Estado del motor de contenedores (Podman o Docker)",
    "pill.checking": "Comprobando motor…",
    "pill.mentorTip": "Mentor IA Socrático local",
    "pill.mentorLocal": "Mentor Local",
    "health.ok": "{motor} OK · {n} imgs",
    "health.noAccess": "{motor} sin acceso",
    "health.offline": "Servidor desconectado",
    "health.ai": "IA: {model}",
    "health.heuristic": "Mentor Heurístico",
    "stat.solved": "resueltos",
    "btn.panel": "← Panel",
    "btn.panelTip": "Volver a tu panel (CHAOS_PANEL_URL en .env)",
    "blind.filterTip": "Filtro de dificultad para Guardia a Ciegas",
    "blind.any": "Cualquier nivel",
    "blind.onlyBasic": "Solo Básico",
    "blind.onlyMid": "Solo Intermedio",
    "blind.onlyAdv": "Solo Avanzado",
    "blind.onlyExpert": "Solo Experto",
    "theme.tip": "Cambiar tema claro / oscuro",
    "theme.aria": "Cambiar tema",
    "lang.aria": "Idioma de la interfaz",
    "btn.blindLaunch": "🎲 Guardia 3:00 AM (+25% XP)",

    /* ---- Catálogo ---- */
    "cat.title": "Catálogo",
    "hist.btn": "📜 Historial",
    "hist.btnTip": "Ver historial reciente",
    "search.ph": "Buscar por Nginx, ACL, DNS, Rocky, Routing…",
    "filter.catAria": "Filtrar por categoría",
    "filter.certAria": "Filtrar por certificación",
    "filter.catAll": "Categoría: todas",
    "filter.certAll": "Certificación: todas",
    "filter.all": "Todos",
    "filter.multi": "Multi-Nodo",
    "filter.adv": "Avanzado+",
    "filter.averia": "🔧 Averías",
    "filter.tarea": "📋 Tareas",
    "filter.pending": "Pendientes",
    "diff.Básico": "Básico",
    "diff.Intermedio": "Intermedio",
    "diff.Avanzado": "Avanzado",
    "diff.Experto": "Experto",
    "hist.drawerTitle": "Últimas guardias resueltas",
    "hist.export": "⬇ Exportar progreso",
    "hist.exportTip": "Descargar tu progreso en un fichero JSON",
    "hist.import": "⬆ Importar",
    "hist.importTip": "Cargar un progreso exportado (sustituye el actual; se guarda copia)",
    "hist.local": "Tu progreso solo vive en este equipo:",
    "hist.empty": "Aún no has cerrado ningún incidente.",
    "hist.rank": "Rango {rank} · +{xp} XP",
    "hist.hints": "{n} pistas",
    "list.empty": "Ningún escenario coincide con ese filtro.",
    "sc.openTip": "Clic para ver de qué va sin desplegarlo",
    "sc.locked": "🔒 temas al resolver",
    "sc.lockedTip": "Los temas del escenario delatan la causa: se muestran al resolverlo",
    "sc.blindTip": "Jugar ocultando pistas de sondas (+25% XP)",
    "sc.node": "nodo",
    "sc.nodes": "nodos",
    "type.tarea": "📋 Tarea",
    "type.averia": "🔧 Avería",
    "btn.deploy": "▶ Desplegar",
    "btn.close": "✕ Cerrar",
    "btn.blind": "🎲 A ciegas",

    /* ---- Vista previa ---- */
    "pv.task": "📋 El encargo",
    "pv.issue": "🔧 La incidencia",
    "pv.topo": "🗺 Topología",
    "pv.machines": "🖧 Máquinas",
    "pv.links": "🔗 Conexiones",
    "pv.obj": "Objetivos LPI:",
    "pv.blindTip": "Jugar ocultando pistas de sondas (+25% XP)",

    /* ---- Pantalla vacía ---- */
    "empty.badge": "ENTORNO EFÍMERO AISLADO SOBRE PODMAN",
    "empty.title": "¿Listo para entrar de guardia?",
    "empty.lead": "Cada laboratorio levanta <strong>1 a 3 contenedores reales interconectados</strong> con averías inyectadas dinámicamente (puertos, contraseñas, reglas de firewall, rutas y tokens cambian en cada partida).",
    "feat.multi.t": "Topologías Multi-Nodo",
    "feat.multi.d": "Pestañas PTY reales por servidor (`edge-proxy`, `api`, `redis`, routers IPv4).",
    "feat.chaos.t": "Chaos Mutator",
    "feat.chaos.d": "Semillas aleatorias para diagnosticar de verdad en lugar de memorizar comandos.",
    "feat.blind.t": "Modo Guardia 3:00 AM",
    "feat.blind.d": "Incidente a ciegas tipo PagerDuty sin pistas en el título ni en las sondas.",
    "feat.pm.t": "Post-Mortem y Mentor SRE",
    "feat.pm.d": "Orientación socrática sin spoilers y exportación del informe `.md` en 1 clic.",
    "btn.emptyBlind": "🎲 Lanzar Incidente Aleatorio a Ciegas",
    "btn.emptyFirst": "▶ Empezar por Pasarela 502 (Multi-Nodo)",

    /* ---- Laboratorio activo ---- */
    "blind.title": "🚨 INCIDENTE EN GUARDIA (Causa Raíz Oculta)",
    "blind.cat": "Modo Guardia 3:00 AM",
    "blind.probe": "Sonda de salud #{n} (oculta en Modo Guardia)",
    "timer.label": "TIEMPO",
    "reveal.tip": "Mostrar qué escenario es (pierde bonus ciego)",
    "reveal.btn": "👁 Revelar Escenario",
    "remutate.tip": "Redesplegar escenario con nueva semilla aleatoria",
    "remutate.btn": "↻ Re-mutar",
    "pm.tip": "Generar informe Post-Mortem en Markdown",
    "pm.btn": "📄 Post-Mortem",
    "stop.tip": "Detener y limpiar contenedores",
    "stop.btn": "⏹ Destruir Lab",
    "tl.title": "📡 Señales correlacionadas (SIEM)",

    /* ---- Esquema ---- */
    "topo.title": "🗺 Cómo debería fluir el tráfico",
    "topo.unk": "sin comprobar",
    "topo.ok": "OK",
    "topo.bad": "falla",
    "topo.tip": "· clic en un nodo = abrir su terminal",
    "topo.hide": "Ocultar",
    "topo.show": "Mostrar esquema",
    "topo.you": "tú",

    /* ---- Terminal ---- */
    "tool.cliTip": "Copiar comando podman exec para abrir en tu terminal local",
    "tool.cli": "CLI externa",
    "tool.reconnectTip": "Reconectar sesión PTY del nodo actual",
    "tool.reconnect": "Reconectar",
    "tool.clearTip": "Limpiar pantalla",
    "tool.clear": "Limpiar",

    /* ---- Panel derecho ---- */
    "victory.title": "¡Incidente Resuelto!",
    "victory.meta": "+{xp} XP · Resuelto en {time}",
    "victory.cause": "Causa raíz documentada:",
    "victory.pm": "📄 Exportar Post-Mortem SRE (.md)",
    "probes.title": "Sondas de Salud (SLO)",
    "btn.verify": "✓ Ejecutar Verificación en Vivo",
    "verify.running": "⏳ Comprobando sondas…",
    "howto.title": "🧭 Cómo empezar",
    "howto.a1": "<strong>Reproduce el síntoma.</strong> Lanza tú la misma petición que falla (la flecha «tú» del esquema).",
    "howto.a2": "<strong>Sigue el camino.</strong> Ve nodo a nodo en el orden de las flechas.",
    "howto.a3": "<strong>En cada salto pregúntate:</strong> ¿el servicio está vivo? ¿escucha en la IP y puerto correctos? ¿la config apunta al sitio bueno? ¿algún firewall lo corta?",
    "howto.a4": "<strong>Arregla de uno en uno y pulsa Verificar.</strong> El esquema se pone verde donde ya funciona.",
    "howto.t1": "<strong>Lee el encargo entero.</strong> Fíjate en los nombres exactos que pide: usuarios, rutas, ficheros.",
    "howto.t2": "<strong>Antes de tocar, mira cómo está.</strong> Consulta la configuración actual y el manual del comando (<code>man</code>, <code>--help</code>).",
    "howto.t3": "<strong>Hazlo paso a paso.</strong> Si necesitas root, usa <code>sudo</code>.",
    "howto.t4": "<strong>Pulsa Verificar cuando quieras.</strong> Cada sonda en verde es un punto del encargo ya cumplido.",
    "look.where": "Dónde mirar en {role}:",
    "look.tools": "🧰 Herramientas:",
    "hints.title": "Pistas Escalonadas",
    "hint.ask": "💡 Pedir pista (-15% XP)",
    "hint.next": "💡 Pista {n}/{total} (-15% XP)",
    "hint.done": "Pistas ({used}/{total})",
    "hint.none0": "Sin pistas consumidas. ¡Resuélvelo limpio para rango S!",
    "hint.none": "Sin pistas consumidas ({total} disponibles).",
    "hint.item": "Pista {n}:",
    "mentor.title": "Mentor SRE Socrático",
    "mentor.ready": "Listo",
    "mentor.fallback": "Mentor",
    "mentor.ph": "Opcional: ¿qué observas o dónde dudas?",
    "mentor.ask": "Consultar",
    "mentor.intro": "Analiza los comandos que has probado en la terminal y te sugiere por dónde seguir investigando sin destriparte el comando final.",
    "mentor.started": "Laboratorio en marcha. Investiga desde la consola y pulsa «Consultar» si necesitas orientación socrática.",
    "mentor.analyzing": "Analizando tus comandos…",
    "mentor.error": "Error: {msg}",

    /* ---- Carga y avisos ---- */
    "load.default": "Desplegando contenedores e inyectando caos…",
    "load.sub": "Configurando red aislada y mutando variables del escenario",
    "load.deploy": "Levantando contenedores e inyectando avería…",
    "load.blind": "Sorteando incidente de guardia 3:00 AM…",
    "load.stop": "Limpiando contenedores y red efímera…",
    "toast.blind": "🚨 Guardia a ciegas iniciada",
    "toast.deployed": "⚡ Escenario desplegado",
    "toast.solved": "🏆 ¡Incidente resuelto! Rango {rank}",
    "toast.probes": "Sondas superadas: {passed}/{total}",
    "toast.revealed": "👁 Identidad del escenario revelada",
    "toast.stopped": "⏹ Laboratorio detenido y limpio",
    "toast.cli": "📋 Comando 'podman exec' copiado al portapapeles",
    "toast.reconnected": "🔌 Reconectado a {role}",
    "toast.pmCopied": "📋 Post-Mortem copiado",
    "toast.pmSaved": "📝 Post-mortem guardado: {path}",
    "toast.err": "❌ {msg}",
    "import.confirm": "¿Sustituir tu progreso actual por el de «{name}»?\n(El actual se guarda como copia en data/.)",
    "import.ok": "Progreso importado: {solved} escenarios resueltos, {xp} XP.",
    "import.fail": "No se pudo importar: {msg}",

    /* ---- Post-mortem ---- */
    "pmodal.title": "📄 Informe Post-Mortem SRE",
    "pmodal.copy": "📋 Copiar Markdown",
    "pmodal.vaultTip": "Guarda el post-mortem como Markdown en CHAOS_EXPORT_DIR (por defecto, exports/)",
    "pmodal.vault": "📝 Guardar post-mortem (.md)",
    "pmodal.download": "⬇ Descargar .md",
  };

  const en = {
    "app.title": "Chaos Lab · SRE Arena & Linux/Network Troubleshooting",
    "app.subtitle": "Interactive Incident Simulator · Linux · Networking · Multi-Node",
    "pill.engineTip": "Container engine status (Podman or Docker)",
    "pill.checking": "Checking engine…",
    "pill.mentorTip": "Local Socratic AI mentor",
    "pill.mentorLocal": "Local Mentor",
    "health.ok": "{motor} OK · {n} images",
    "health.noAccess": "{motor}: no access",
    "health.offline": "Server offline",
    "health.ai": "AI: {model}",
    "health.heuristic": "Heuristic Mentor",
    "stat.solved": "solved",
    "btn.panel": "← Dashboard",
    "btn.panelTip": "Back to your dashboard (CHAOS_PANEL_URL in .env)",
    "blind.filterTip": "Difficulty filter for Blind On-Call",
    "blind.any": "Any level",
    "blind.onlyBasic": "Basic only",
    "blind.onlyMid": "Intermediate only",
    "blind.onlyAdv": "Advanced only",
    "blind.onlyExpert": "Expert only",
    "theme.tip": "Toggle light / dark theme",
    "theme.aria": "Toggle theme",
    "lang.aria": "Interface language",
    "btn.blindLaunch": "🎲 3:00 AM On-Call (+25% XP)",

    "cat.title": "Catalog",
    "hist.btn": "📜 History",
    "hist.btnTip": "Show recent history",
    "search.ph": "Search Nginx, ACL, DNS, Rocky, Routing…",
    "filter.catAria": "Filter by category",
    "filter.certAria": "Filter by certification",
    "filter.catAll": "Category: all",
    "filter.certAll": "Certification: all",
    "filter.all": "All",
    "filter.multi": "Multi-Node",
    "filter.adv": "Advanced+",
    "filter.averia": "🔧 Faults",
    "filter.tarea": "📋 Tasks",
    "filter.pending": "Unsolved",
    "diff.Básico": "Basic",
    "diff.Intermedio": "Intermediate",
    "diff.Avanzado": "Advanced",
    "diff.Experto": "Expert",
    "hist.drawerTitle": "Recently solved incidents",
    "hist.export": "⬇ Export progress",
    "hist.exportTip": "Download your progress as a JSON file",
    "hist.import": "⬆ Import",
    "hist.importTip": "Load an exported progress file (replaces the current one; a backup is kept)",
    "hist.local": "Your progress is stored only on this machine:",
    "hist.empty": "You haven't closed any incident yet.",
    "hist.rank": "Rank {rank} · +{xp} XP",
    "hist.hints": "{n} hints",
    "list.empty": "No scenario matches that filter.",
    "sc.openTip": "Click to preview without deploying",
    "sc.locked": "🔒 topics on solve",
    "sc.lockedTip": "Scenario topics give away the root cause: they are shown once you solve it",
    "sc.blindTip": "Play with probe labels hidden (+25% XP)",
    "sc.node": "node",
    "sc.nodes": "nodes",
    "type.tarea": "📋 Task",
    "type.averia": "🔧 Fault",
    "btn.deploy": "▶ Deploy",
    "btn.close": "✕ Close",
    "btn.blind": "🎲 Blind",

    "pv.task": "📋 The assignment",
    "pv.issue": "🔧 The incident",
    "pv.topo": "🗺 Topology",
    "pv.machines": "🖧 Machines",
    "pv.links": "🔗 Links",
    "pv.obj": "LPI objectives:",
    "pv.blindTip": "Play with probe labels hidden (+25% XP)",

    "empty.badge": "EPHEMERAL ISOLATED ENVIRONMENT ON PODMAN",
    "empty.title": "Ready to go on call?",
    "empty.lead": "Each lab spins up <strong>1 to 3 real, interconnected containers</strong> with dynamically injected faults (ports, passwords, firewall rules, routes and tokens change on every run).",
    "feat.multi.t": "Multi-Node Topologies",
    "feat.multi.d": "Real PTY tabs per server (`edge-proxy`, `api`, `redis`, IPv4 routers).",
    "feat.chaos.t": "Chaos Mutator",
    "feat.chaos.d": "Random seeds so you actually diagnose instead of memorising commands.",
    "feat.blind.t": "3:00 AM On-Call Mode",
    "feat.blind.d": "PagerDuty-style blind incident with no hints in the title or the probes.",
    "feat.pm.t": "Post-Mortem & SRE Mentor",
    "feat.pm.d": "Socratic guidance without spoilers and a one-click `.md` report export.",
    "btn.emptyBlind": "🎲 Launch a Random Blind Incident",
    "btn.emptyFirst": "▶ Start with Gateway 502 (Multi-Node)",

    "blind.title": "🚨 ON-CALL INCIDENT (Root Cause Hidden)",
    "blind.cat": "3:00 AM On-Call Mode",
    "blind.probe": "Health probe #{n} (hidden in On-Call Mode)",
    "timer.label": "TIME",
    "reveal.tip": "Show which scenario this is (loses the blind bonus)",
    "reveal.btn": "👁 Reveal Scenario",
    "remutate.tip": "Redeploy the scenario with a new random seed",
    "remutate.btn": "↻ Re-mutate",
    "pm.tip": "Generate a Post-Mortem report in Markdown",
    "pm.btn": "📄 Post-Mortem",
    "stop.tip": "Stop and clean up containers",
    "stop.btn": "⏹ Destroy Lab",
    "tl.title": "📡 Correlated signals (SIEM)",

    "topo.title": "🗺 How traffic should flow",
    "topo.unk": "not checked",
    "topo.ok": "OK",
    "topo.bad": "failing",
    "topo.tip": "· click a node = open its terminal",
    "topo.hide": "Hide",
    "topo.show": "Show diagram",
    "topo.you": "you",

    "tool.cliTip": "Copy the podman exec command to open it in your local terminal",
    "tool.cli": "External CLI",
    "tool.reconnectTip": "Reconnect the PTY session of the current node",
    "tool.reconnect": "Reconnect",
    "tool.clearTip": "Clear screen",
    "tool.clear": "Clear",

    "victory.title": "Incident Resolved!",
    "victory.meta": "+{xp} XP · Solved in {time}",
    "victory.cause": "Documented root cause:",
    "victory.pm": "📄 Export SRE Post-Mortem (.md)",
    "probes.title": "Health Probes (SLO)",
    "btn.verify": "✓ Run Live Verification",
    "verify.running": "⏳ Running probes…",
    "howto.title": "🧭 How to start",
    "howto.a1": "<strong>Reproduce the symptom.</strong> Send the same request that fails yourself (the “you” arrow in the diagram).",
    "howto.a2": "<strong>Follow the path.</strong> Go node by node, in the order of the arrows.",
    "howto.a3": "<strong>At each hop, ask yourself:</strong> is the service up? Is it listening on the right IP and port? Does the config point to the right place? Is a firewall dropping it?",
    "howto.a4": "<strong>Fix one thing at a time and hit Verify.</strong> The diagram turns green where things already work.",
    "howto.t1": "<strong>Read the whole assignment.</strong> Note the exact names it asks for: users, paths, files.",
    "howto.t2": "<strong>Look before you touch.</strong> Check the current configuration and the command's manual (<code>man</code>, <code>--help</code>).",
    "howto.t3": "<strong>Go step by step.</strong> If you need root, use <code>sudo</code>.",
    "howto.t4": "<strong>Hit Verify whenever you like.</strong> Every green probe is a requirement already met.",
    "look.where": "Where to look on {role}:",
    "look.tools": "🧰 Tools:",
    "hints.title": "Staged Hints",
    "hint.ask": "💡 Get a hint (-15% XP)",
    "hint.next": "💡 Hint {n}/{total} (-15% XP)",
    "hint.done": "Hints ({used}/{total})",
    "hint.none0": "No hints used. Solve it clean for an S rank!",
    "hint.none": "No hints used ({total} available).",
    "hint.item": "Hint {n}:",
    "mentor.title": "Socratic SRE Mentor",
    "mentor.ready": "Ready",
    "mentor.fallback": "Mentor",
    "mentor.ph": "Optional: what are you seeing, or where are you stuck?",
    "mentor.ask": "Ask",
    "mentor.intro": "Reviews the commands you've tried in the terminal and suggests where to dig next, without giving away the final command.",
    "mentor.started": "Lab is up. Investigate from the console and press “Ask” if you want Socratic guidance.",
    "mentor.analyzing": "Analysing your commands…",
    "mentor.error": "Error: {msg}",

    "load.default": "Deploying containers and injecting chaos…",
    "load.sub": "Setting up the isolated network and mutating the scenario variables",
    "load.deploy": "Starting containers and injecting the fault…",
    "load.blind": "Drawing a 3:00 AM on-call incident…",
    "load.stop": "Cleaning up containers and the ephemeral network…",
    "toast.blind": "🚨 Blind on-call started",
    "toast.deployed": "⚡ Scenario deployed",
    "toast.solved": "🏆 Incident resolved! Rank {rank}",
    "toast.probes": "Probes passing: {passed}/{total}",
    "toast.revealed": "👁 Scenario identity revealed",
    "toast.stopped": "⏹ Lab stopped and cleaned up",
    "toast.cli": "📋 'podman exec' command copied to clipboard",
    "toast.reconnected": "🔌 Reconnected to {role}",
    "toast.pmCopied": "📋 Post-Mortem copied",
    "toast.pmSaved": "📝 Post-mortem saved: {path}",
    "toast.err": "❌ {msg}",
    "import.confirm": "Replace your current progress with “{name}”?\n(The current one is kept as a backup in data/.)",
    "import.ok": "Progress imported: {solved} scenarios solved, {xp} XP.",
    "import.fail": "Import failed: {msg}",

    "pmodal.title": "📄 SRE Post-Mortem Report",
    "pmodal.copy": "📋 Copy Markdown",
    "pmodal.vaultTip": "Saves the post-mortem as Markdown in CHAOS_EXPORT_DIR (default: exports/)",
    "pmodal.vault": "📝 Save post-mortem (.md)",
    "pmodal.download": "⬇ Download .md",
  };

  const DICT = { es, en };
  const LS_KEY = "chaos-lang";

  function detect() {
    try {
      const saved = localStorage.getItem(LS_KEY);
      if (saved === "es" || saved === "en") return saved;
    } catch (_) {}
    const nav = String((typeof navigator !== "undefined" && navigator.language) || "es").toLowerCase();
    return nav.startsWith("es") ? "es" : "en";
  }

  let lang = detect();

  function currentLang() { return lang; }

  function has(key) { return Object.prototype.hasOwnProperty.call(DICT[lang], key) || Object.prototype.hasOwnProperty.call(es, key); }

  function t(key, vars) {
    let s = DICT[lang][key];
    if (s === undefined) s = es[key];
    if (s === undefined) s = key;
    if (vars) s = s.replace(/\{(\w+)\}/g, (m, k) => (vars[k] !== undefined && vars[k] !== null ? String(vars[k]) : m));
    return s;
  }

  // Texto traducido si la clave existe; si no, el valor tal cual (p. ej. dificultades que llegan del servidor)
  function tOr(key, fallback) { return has(key) ? t(key) : fallback; }

  function applyI18n(root) {
    const scope = root || document;
    scope.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    scope.querySelectorAll("[data-i18n-html]").forEach((el) => { el.innerHTML = t(el.dataset.i18nHtml); });
    [["placeholder", "i18nPlaceholder"], ["title", "i18nTitle"], ["aria-label", "i18nAriaLabel"]].forEach(([attr, ds]) => {
      const sel = "[data-i18n-" + attr + "]";
      scope.querySelectorAll(sel).forEach((el) => el.setAttribute(attr, t(el.dataset[ds])));
    });
    document.documentElement.lang = lang;
    document.title = t("app.title");
    document.querySelectorAll("#lang-toggle [data-lang]").forEach((b) => {
      const on = b.dataset.lang === lang;
      b.classList.toggle("active", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  function setLang(l) {
    if (l !== "es" && l !== "en") return;
    lang = l;
    try { localStorage.setItem(LS_KEY, l); } catch (_) {}
    applyI18n();
  }

  window.I18N = { t, tOr, has, currentLang, setLang, applyI18n, dict: DICT };
  window.t = t;
  window.tOr = tOr;
  window.currentLang = currentLang;

  document.documentElement.lang = lang;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => applyI18n());
  else applyI18n();
})();
