/* Chaos Lab Frontend — Multi-Node PTY + Live Grader + 3AM Blind Mode */

const state = {
  scenarios: [],
  stats: { total_scenarios: 0, solved_count: 0, total_xp: 0, history: [] },
  active: null,
  filter: "all",
  search: "",
  category: "",
  cert: "",
  activeNodeRole: null,
  sessions: {}, // role -> { term, fitAddon, ws, slotEl }
  timerInterval: null,
  lastSessionId: null,
  pmFilename: "postmortem.md",
  previewId: null, // escenario abierto en la ficha de vista previa
};

const $ = (id) => document.getElementById(id);

function showToast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => el.classList.add("hidden"), 2800);
}

function setLoading(visible, title = "Desplegando contenedores…") {
  $("loading-title").textContent = title;
  $("loading-overlay").classList.toggle("hidden", !visible);
}

function fmtSeconds(sec) {
  const s = Math.max(0, Math.floor(sec || 0));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const data = await res.json();
  if (!res.ok || data.ok === false) {
    throw new Error(data.error || data.detail || `Error HTTP ${res.status}`);
  }
  return data;
}

/* -------------------- Salud e Inicialización -------------------- */

async function refreshHealth() {
  try {
    const h = await fetch("/api/health").then((r) => r.json());
    const rt = h.runtime || {};
    const panel = $("btn-panel");
    if (panel && h.panel_url) { panel.href = h.panel_url; panel.classList.remove("hidden"); }
    const motor = rt.engine === "docker" ? "Docker" : "Podman";
    $("podman-dot").className = "dot " + (rt.podman_ok ? "ok" : "err");
    $("podman-text").textContent = rt.podman_ok
      ? `${motor} OK · ${rt.cached_images_count} imgs`
      : `${motor} sin acceso`;

    const ol = h.ollama || {};
    $("ollama-dot").className = "dot " + (ol.online ? "ok" : "warn");
    $("ollama-text").textContent = ol.online
      ? `IA: ${ol.model || "Ollama"}`
      : "Mentor Heurístico";
  } catch (_) {
    const motor = rt.engine === "docker" ? "Docker" : "Podman";
    $("podman-dot").className = "dot err";
    $("podman-text").textContent = "Servidor desconectado";
  }
}

async function refreshCatalog() {
  const data = await fetch("/api/catalog").then((r) => r.json());
  state.scenarios = data.scenarios || [];
  state.stats = data.stats || state.stats;
  renderStats();
  renderScenarioList();
  syncActiveView(data.active || null);
}

function renderStats() {
  $("stat-xp").textContent = state.stats.total_xp || 0;
  $("stat-solved").textContent = `${state.stats.solved_count || 0}/${state.stats.total_scenarios || 0}`;

  const histEl = $("history-list");
  const items = state.stats.history || [];
  if (!items.length) {
    histEl.innerHTML = `<p class="muted-note">Aún no has cerrado ningún incidente.</p>`;
    return;
  }
  histEl.innerHTML = items
    .map(
      (h) => `
      <div class="hist-item">
        <div class="hist-row">
          <span>${h.blind_mode ? "🎲 " : ""}${escapeHtml(h.title)}</span>
          <span class="badge badge-solved">Rango ${escapeHtml(h.rank)} · +${h.xp} XP</span>
        </div>
        <div class="hist-sub">
          ⏱ ${fmtSeconds(h.elapsed_s)} · 💡 ${h.hints_used} pistas · ${escapeHtml(h.at)}
        </div>
      </div>`
    )
    .join("");
}

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/* -------------------- Catálogo Lateral -------------------- */

function fillFilterSelects() {
  // Rellena los desplegables con lo que hay en el catálogo (una vez)
  const fill = (id, values) => {
    const sel = $(id);
    if (!sel || sel.options.length > 1) return;
    [...new Set(values)].sort((a, b) => a.localeCompare(b, "es")).forEach((v) => {
      const o = document.createElement("option");
      o.value = v; o.textContent = v; sel.appendChild(o);
    });
  };
  fill("filter-category", state.scenarios.map((s) => s.category));
  fill("filter-cert", state.scenarios.flatMap((s) => s.certs || []));
}

function renderScenarioList() {
  fillFilterSelects();
  const listEl = $("scenario-list");
  const q = state.search.trim().toLowerCase();

  const filtered = state.scenarios.filter((sc) => {
    if (state.filter === "multi" && sc.node_count < 2) return false;
    if (state.filter === "Básico" && sc.difficulty !== "Básico") return false;
    if (state.filter === "Intermedio" && sc.difficulty !== "Intermedio") return false;
    if (state.filter === "Avanzado" && !["Avanzado", "Experto"].includes(sc.difficulty)) return false;
    if (state.filter === "pending" && sc.solved) return false;
    if (state.filter === "averia" && (sc.tipo || "averia") !== "averia") return false;
    if (state.filter === "tarea" && sc.tipo !== "tarea") return false;
    if (state.category && sc.category !== state.category) return false;
    if (state.cert && !(sc.certs || []).includes(state.cert)) return false;

    if (q) {
      const hay = [sc.title, sc.category, sc.difficulty, ...(sc.tags || []), ...(sc.certs || []), ...(sc.nodes || [])]
        .join(" ")
        .toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  if (!filtered.length) {
    listEl.innerHTML = `<p class="muted-note empty-note">Ningún escenario coincide con ese filtro.</p>`;
    return;
  }

  const currentRealId = state.active && !state.active.blind_masked ? state.active.real_scenario_id : null;

  listEl.innerHTML = filtered
    .map((sc) => {
      const isCurrent = currentRealId === sc.id;
      const solvedBadge = sc.solved
        ? `<span class="badge badge-solved">✓ ${sc.best_rank || "OK"} · ${fmtSeconds(sc.best_time_s)}</span>`
        : "";
      return `
      <div class="sc-card ${isCurrent ? "active-sc" : ""}" data-id="${escapeHtml(sc.id)}"
           role="button" tabindex="0" title="Clic para ver de qué va sin desplegarlo">
        <div class="sc-top">
          <div class="sc-title">${escapeHtml(sc.title)}</div>
          ${solvedBadge}
        </div>
        <div class="sc-meta">
          <span class="badge diff-${escapeHtml(sc.difficulty)}">${escapeHtml(sc.difficulty)}</span>
          <span class="badge tipo-${sc.tipo === "tarea" ? "tarea" : "averia"}">${sc.tipo === "tarea" ? "📋 Tarea" : "🔧 Avería"}</span>
          <span>⚡ ${sc.points} XP</span>
          <span>·</span>
          <span>🖧 ${sc.node_count} ${sc.node_count > 1 ? "nodos" : "nodo"}</span>
          <span>·</span>
          <span>~${sc.estimated_min}m</span>
        </div>
        <div class="sc-tags">
          ${(sc.certs || []).length ? `<span class="sc-certs">${sc.certs.map((c) => `<span class="cert">${escapeHtml(c)}</span>`).join("")}</span>` : ""}
          ${sc.solved
            ? (sc.tags || []).map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join("")
            : `<span class="tags-locked" title="Los temas del escenario delatan la causa: se muestran al resolverlo">🔒 temas al resolver</span>`}
        </div>
        <div class="sc-actions">
          <span class="sc-cat" title="${escapeHtml(sc.category)}">${escapeHtml(sc.category)}</span>
          <div class="sc-buttons">
            <button class="btn-ghost-sm" onclick="event.stopPropagation(); launchScenario('${sc.id}', true)" title="Jugar ocultando pistas de sondas (+25% XP)">🎲</button>
            <button class="btn btn-primary btn-sm" onclick="event.stopPropagation(); launchScenario('${sc.id}', false)">▶ Desplegar</button>
          </div>
        </div>
      </div>`;
    })
    .join("");
}

/* Vista previa de un escenario dentro de su tarjeta (sin desplegar nada) */
function scenarioPreview(sc) {
  const code = (t) => escapeHtml(t || "").replace(/`([^`\n]+)`/g, "<code>$1</code>");
  const hasDraw = (sc.machines || []).length > 1 || Object.keys(sc.networks || {}).length > 0;
  const machines = hasDraw ? "" : (sc.machines || [])
    .map((m) => `<li><span class="pv-role">${escapeHtml(m.role)}</span>${m.runs ? ` <span class="pv-runs">${escapeHtml(m.runs)}</span>` : ""}</li>`)
    .join("");
  const links = hasDraw ? "" : (sc.links || [])
    .map((l) => `<li>${escapeHtml(l.from)} → ${escapeHtml(l.to)}${l.via ? ` <span class="pv-runs">· ${escapeHtml(l.via)}</span>` : ""}</li>`)
    .join("");
  const obj = (sc.objetivos_lpi || []).length
    ? `<div class="pv-obj">Objetivos LPI: ${sc.objetivos_lpi.map((o) => `<span class="tag">${escapeHtml(o)}</span>`).join(" ")}</div>`
    : "";
  return `
        <div class="sc-preview">
          <div class="pv-label">${sc.tipo === "tarea" ? "📋 El encargo" : "🔧 La incidencia"}</div>
          <div class="pv-brief">${code(sc.briefing)}</div>
          ${hasDraw ? `<div class="pv-label">🗺 Topología</div><div class="pv-topo" id="pv-topo"></div>` : ""}
          ${machines ? `<div class="pv-label">🖧 Máquinas</div><ul class="pv-list">${machines}</ul>` : ""}
          ${links ? `<div class="pv-label">🔗 Conexiones</div><ul class="pv-list">${links}</ul>` : ""}
          ${obj}
        </div>`;
}

function openPreview(id) {
  const sc = state.scenarios.find((x) => x.id === id);
  if (!sc) return;
  state.previewId = id;
  $("pv-title").textContent = sc.title;
  $("pv-meta").innerHTML = `
    <span class="badge diff-${escapeHtml(sc.difficulty)}">${escapeHtml(sc.difficulty)}</span>
    <span class="badge tipo-${sc.tipo === "tarea" ? "tarea" : "averia"}">${sc.tipo === "tarea" ? "📋 Tarea" : "🔧 Avería"}</span>
    <span>⚡ ${sc.points} XP</span><span>·</span><span>~${sc.estimated_min}m</span><span>·</span>
    <span>${escapeHtml(sc.category)}</span>
    ${(sc.certs || []).map((c) => `<span class="cert">${escapeHtml(c)}</span>`).join("")}
    ${sc.solved ? `<span class="badge badge-solved">✓ ${sc.best_rank || "OK"} · ${fmtSeconds(sc.best_time_s)}</span>` : ""}`;
  const oldBox = $("pv-topo");
  if (oldBox && oldBox._topo) oldBox._topo.destroy();
  $("pv-body").innerHTML = scenarioPreview(sc);
  $("pv-modal").classList.remove("hidden");
  const pvBox = $("pv-topo");
  if (pvBox) {
    const nodes = Object.fromEntries((sc.machines || []).map((m) => [m.role, { runs: m.runs }]));
    drawTopology(pvBox, { entry: sc.entry || null, nodes, links: sc.links || [], networks: sc.networks || {} }, { minHeight: 110, compact: true });
  }
  $("btn-pv-launch").focus();
}

function closePreview() {
  const pvBox = $("pv-topo");
  if (pvBox && pvBox._topo) pvBox._topo.destroy();
  $("pv-modal").classList.add("hidden");
  const id = state.previewId;
  state.previewId = null;
  if (id) document.querySelector(`.sc-card[data-id="${CSS.escape(id)}"]`)?.focus();
}

/* -------------------- Lanzar / Detener / Sincronizar -------------------- */

async function launchScenario(scenarioId = null, blindMode = false) {
  const diff = $("blind-diff-select").value;
  setLoading(
    true,
    blindMode && !scenarioId
      ? "Sorteando incidente de guardia 3:00 AM…"
      : "Levantando contenedores e inyectando avería…"
  );
  try {
    const res = await api("/api/lab/launch", {
      method: "POST",
      body: JSON.stringify({
        scenario_id: scenarioId,
        blind_mode: blindMode,
        difficulty: diff,
      }),
    });
    $("mentor-output").textContent =
      "Laboratorio en marcha. Investiga desde la consola y pulsa «Consultar» si necesitas orientación socrática.";
    syncActiveView(res.active);
    await refreshCatalog();
    showToast(blindMode ? "🚨 Guardia a ciegas iniciada" : "⚡ Escenario desplegado");
  } catch (err) {
    showToast(`❌ ${err.message}`);
  } finally {
    setLoading(false);
  }
}

window.launchScenario = launchScenario;

function destroyAllTerminals() {
  Object.values(state.sessions).forEach((s) => {
    try { s.ws && s.ws.close(); } catch (_) {}
    try { s.term && s.term.dispose(); } catch (_) {}
  });
  state.sessions = {};
  state.activeNodeRole = null;
  $("terminals-wrapper").innerHTML = "";
  $("node-tabs").innerHTML = "";
}

function syncActiveView(active) {
  state.active = active;
  clearInterval(state.timerInterval);

  if (!active) {
    destroyAllTerminals();
    state.lastSessionId = null;
    $("empty-arena").classList.remove("hidden");
    $("active-arena").classList.add("hidden");
    renderTopology(null);
    return;
  }

  $("empty-arena").classList.add("hidden");
  $("active-arena").classList.remove("hidden");

  $("incident-banner").classList.toggle("blind-active", Boolean(active.blind_masked));
  $("active-diff-badge").className = `badge diff-${active.difficulty}`;
  $("active-diff-badge").textContent = `${active.difficulty} · ${active.points} XP`;
  $("active-cat-badge").textContent = active.category;
  $("active-seed-badge").textContent = `Seed #${active.seed}`;
  $("active-title").textContent = active.title;
  // `algo` → <code>algo</code>; los saltos de línea se respetan (listas numeradas del encargo)
  $("active-desc").innerHTML = escapeHtml(active.description || "").replace(/`([^`\n]+)`/g, "<code>$1</code>");
  $("active-desc").style.whiteSpace = "pre-line";
  const esTarea = active.tipo === "tarea";
  $("howto-averia").classList.toggle("hidden", esTarea);
  $("howto-tarea").classList.toggle("hidden", !esTarea);

  // Línea de tiempo de señales correlacionadas (alerta de guardia en escenarios sec-*)
  const tl = active.timeline || [];
  const tlBox = $("alert-timeline");
  tlBox.classList.toggle("hidden", !tl.length);
  if (tl.length) {
    const ico = { crit: "🔴", warn: "🟠", info: "🔵" };
    tlBox.innerHTML =
      `<div class="alert-timeline-title">📡 Señales correlacionadas (SIEM)</div>` +
      tl
        .map(
          (e) => `<div class="tl-row tl-${escapeHtml(e.sev)}"><span class="tl-t">${escapeHtml(e.t)}</span>` +
            `<span class="tl-ico">${ico[e.sev] || "•"}</span><span class="tl-node">[${escapeHtml(e.node)}]</span>` +
            `<span class="tl-text">${escapeHtml(e.text)}</span></div>`
        )
        .join("");
  }

  renderTopology(active);
  renderHowtoLook(active);

  $("btn-reveal-blind").classList.toggle("hidden", !active.blind_masked);

  // Reloj en vivo
  const startedClientEpoch = Date.now() / 1000 - (active.elapsed_s || 0);
  const updateClock = () => {
    if (active.solved) {
      $("timer-val").textContent = fmtSeconds(active.elapsed_s);
      return;
    }
    const sec = Math.floor(Date.now() / 1000 - startedClientEpoch);
    $("timer-val").textContent = fmtSeconds(sec);
  };
  updateClock();
  if (!active.solved) {
    state.timerInterval = setInterval(updateClock, 1000);
  }

  // Sondas de verificación
  const passed = (active.checks || []).filter((c) => c.passed).length;
  $("check-counter").textContent = `${passed}/${(active.checks || []).length}`;
  $("checks-list").innerHTML = (active.checks || [])
    .map(
      (c) => `
      <div class="check-item ${c.passed ? "passed" : ""}">
        <span class="check-icon">
          ${c.passed ? "✓" : "○"}
        </span>
        <div>
          <span class="check-node">[${escapeHtml(c.node)}]</span>
          <span>${escapeHtml(c.label)}</span>
        </div>
      </div>`
    )
    .join("");

  // Pistas
  const hints = active.hints || [];
  $("btn-unlock-hint").disabled = active.hints_used >= active.total_hints;
  $("btn-unlock-hint").textContent =
    active.hints_used >= active.total_hints
      ? `Pistas (${active.hints_used}/${active.total_hints})`
      : `💡 Pista ${active.hints_used + 1}/${active.total_hints} (-15% XP)`;

  if (!hints.length) {
    $("hints-list").innerHTML = `<p class="muted-note">Sin pistas consumidas (${active.total_hints} disponibles).</p>`;
  } else {
    $("hints-list").innerHTML = hints
      .map((h, idx) => `<div class="hint-box"><strong>Pista ${idx + 1}:</strong> ${escapeHtml(h)}</div>`)
      .join("");
  }

  // Tarjeta de victoria
  if (active.solved) {
    $("victory-card").classList.remove("hidden");
    $("victory-rank").textContent = active.rank || "S";
    $("victory-meta").textContent = `+${active.earned_xp || active.points} XP · Resuelto en ${fmtSeconds(active.elapsed_s)}`;
    $("victory-solution").textContent = active.solution_summary || "";
  } else {
    $("victory-card").classList.add("hidden");
  }

  // Inicializar terminales si es una nueva sesión
  if (state.lastSessionId !== active.session_id) {
    destroyAllTerminals();
    state.lastSessionId = active.session_id;
    setupNodeTerminals(active.nodes || []);
  } else {
    renderNodeTabs(active.nodes || []);
  }
}

/* -------------------- Tema claro / oscuro -------------------- */

function termTheme() {
  const light = document.documentElement.dataset.theme === "light";
  return light
    ? { background: "#ffffff", foreground: "#1f1f23", cursor: "#0369a1", cursorAccent: "#ffffff",
        selectionBackground: "rgba(3, 105, 161, 0.22)",
        black: "#1f1f23", red: "#b91c1c", green: "#15803d", yellow: "#a16207", blue: "#1d4ed8",
        magenta: "#7e22ce", cyan: "#0e7490", white: "#6b6b75",
        brightBlack: "#52525b", brightRed: "#dc2626", brightGreen: "#16a34a", brightYellow: "#b45309",
        brightBlue: "#2563eb", brightMagenta: "#9333ea", brightCyan: "#0891b2", brightWhite: "#3f3f46" }
    : { background: "#0a0a0b", foreground: "#ededef", cursor: "#38bdf8", cursorAccent: "#0a0a0b",
        selectionBackground: "rgba(56, 189, 248, 0.28)" };
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("chaos-theme", theme); } catch (_) {}
  const btn = $("btn-theme");
  if (btn) btn.textContent = theme === "light" ? "☾" : "☀";
  Object.values(state.sessions).forEach((s) => {
    try { s.term.options.theme = termTheme(); } catch (_) {}
  });
  restyleTopologies();
}

document.addEventListener("DOMContentLoaded", () => {
  setTheme(document.documentElement.dataset.theme === "light" ? "light" : "dark");
  const btn = $("btn-theme");
  if (btn) btn.addEventListener("click", () =>
    setTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light"));
});

/* -------------------- Esquema de topología -------------------- */

function topoStatus(active, target) {
  // null = sin comprobar todavía (no se ha pulsado Verificar en esta sesión)
  const topo = active.topology || {};
  const map = topo.checks || {};
  const ids = Object.keys(map).filter((id) => map[id] === target);
  if (!ids.length) return null;
  const byId = Object.fromEntries((active.checks || []).map((c) => [c.id, c]));
  const allOk = ids.every((id) => byId[id] && byId[id].passed);
  if (allOk) return "ok";
  return state.verifiedSession === active.session_id ? "bad" : null;
}

/* ---- Dibujo con Cytoscape.js (vendor/cytoscape.min.js) ----
   drawTopology(container, topo, {ipOf, statusOf, activeRole, onNodeClick})
   topo = {entry, nodes:{rol:{runs}}, links:[{from,to,via}], networks:{corto:[roles]}}
   statusOf(target) -> "ok" | "bad" | null con target "entry" | "node:<rol>" | "link:<n>".
   Devuelve {cy, update({statusOf, activeRole}), restyle(), destroy()}. La posición de cada nodo se calcula
   aquí (layout `preset`, de izquierda a derecha), así el dibujo sale igual siempre. */

const TOPO_LIVE = new Set();   // instancias vivas, para volver a pintarlas al cambiar de tema

function topoColors() {
  const cs = getComputedStyle(document.documentElement);
  const v = (n, d) => (cs.getPropertyValue(n) || "").trim() || d;
  return {
    bg: v("--bg-1", "#111"), box: v("--bg-2", "#1a1a1d"), border: v("--border-hi", "#444"),
    text: v("--text", "#eee"), dim: v("--text-dim", "#888"), text2: v("--text-2", "#bbb"),
    green: v("--green", "#22c55e"), red: v("--red", "#ef4444"),
    accent: v("--accent", "#38bdf8"), accentSoft: v("--accent-soft", "rgba(56,189,248,.15)"),
    mono: v("--font-mono", "monospace"), sans: v("--font-sans", "sans-serif"),
  };
}

function topoStyle(c, compact) {
  const fs = compact ? 12 : 11;
  return [
    { selector: "node.n", style: {
      shape: "round-rectangle", width: "data(w)", height: "data(h)",
      "background-color": c.box, "border-width": 1.5, "border-color": c.border,
      label: "data(label)", "text-wrap": "wrap", "text-valign": "center", "text-halign": "center",
      color: c.text, "font-family": c.mono, "font-size": fs, "line-height": 1.35, "text-max-width": 300 } },
    { selector: "node.router", style: { "border-style": "double", "border-width": 4 } },
    { selector: "node.n.ok", style: { "border-color": c.green } },
    { selector: "node.n.bad", style: { "border-color": c.red } },
    { selector: "node.n.active", style: { "border-color": c.accent, "border-width": 3, "background-color": c.accent, "background-opacity": 0.14 } },
    { selector: "node.n.router.active", style: { "border-width": 5 } },
    { selector: "node.entry", style: {
      shape: "round-rectangle", width: "data(w)", height: "data(h)", label: "data(label)",
      "text-valign": "center", "text-halign": "center",
      "background-opacity": 0, "border-width": 1.5, "border-style": "dashed", "border-color": c.dim,
      color: c.text2, "font-family": c.sans, "font-size": 12 } },
    { selector: "node.net", style: {
      shape: "round-rectangle", "background-color": c.dim, "background-opacity": 0.07,
      "border-width": 1.2, "border-style": "dashed", "border-color": c.dim, padding: 16,
      label: "data(label)", "text-valign": "top", "text-halign": "center", "text-margin-y": -2,
      color: c.dim, "font-family": c.mono, "font-size": 11 } },
    { selector: "edge.l", style: {
      width: 2, "line-color": c.dim, "line-style": "dashed", "target-arrow-shape": "triangle", "target-arrow-color": c.dim,
      "arrow-scale": 1.1, "curve-style": "bezier", "control-point-step-size": 40,
      label: "data(label)", "font-size": compact ? 11 : 10.5, "font-family": c.mono, color: c.text2, "edge-text-rotation": "none",
      ...(compact ? { "text-wrap": "wrap", "text-max-width": 96 } : {}),
      "text-background-color": c.bg, "text-background-opacity": 1, "text-background-padding": 2, "text-background-shape": "roundrectangle" } },
    { selector: "edge.l.ok", style: { "line-color": c.green, "target-arrow-color": c.green, "line-style": "solid" } },
    { selector: "edge.l.bad", style: { "line-color": c.red, "target-arrow-color": c.red, "line-style": "solid" } },
    { selector: "edge.member", style: {
      width: 1, "line-color": c.border, "line-style": "dotted", "target-arrow-shape": "none", "curve-style": "straight", opacity: 0.55 } },
    { selector: "node.ghost", style: { opacity: 0, width: 2, height: 2, events: "no", label: "" } },
  ];
}

// Posiciones (centro) de nodos y entrada, de izquierda a derecha. Devuelve {pos, nets, netsOf}
function topoLayout(topo, dims) {
  const roles = Object.keys(topo.nodes || {});
  const links = topo.links || [];
  const nets = {};
  Object.entries(topo.networks || {}).forEach(([n, rs]) => {
    const own = rs.filter((r) => roles.includes(r));
    if (own.length) nets[n] = own;
  });
  const netNames = Object.keys(nets);
  const netsOf = (r) => netNames.filter((n) => nets[n].includes(r));

  // Profundidad por flujo (entrada → enlaces); lo no alcanzado cuelga de lo que sí
  const depth = {};
  const first = topo.entry && roles.includes(topo.entry.to) ? topo.entry.to
    : (roles.find((r) => !links.some((l) => l.to === r)) || roles[0]);
  let queue = [first];
  depth[first] = 0;
  const walk = () => {
    while (queue.length) {
      const r = queue.shift();
      links.filter((l) => l.from === r && depth[l.to] === undefined && roles.includes(l.to))
        .forEach((l) => { depth[l.to] = depth[r] + 1; queue.push(l.to); });
    }
  };
  walk();
  let guard = roles.length + 2;
  while (roles.some((r) => depth[r] === undefined) && guard-- > 0) {
    const hit = roles.find((r) => depth[r] === undefined && links.some((l) => l.from === r && depth[l.to] !== undefined));
    if (hit) {
      depth[hit] = Math.min(...links.filter((l) => l.from === hit && depth[l.to] !== undefined).map((l) => depth[l.to]));  // misma columna que su destino, apilado
      continue;
    }
    const orphan = roles.find((r) => depth[r] === undefined);
    depth[orphan] = Math.max(0, ...Object.values(depth)) + 1;
    queue = [orphan];
    walk();
  }
  const byDepth = (a, b) => (depth[a] - depth[b]) || (roles.indexOf(a) - roles.indexOf(b));

  // Columnas de izquierda a derecha: [{roles, extra}]
  const cols = [];
  const chunk = (arr, n) => { const o = []; for (let i = 0; i < arr.length; i += n) o.push(arr.slice(i, i + n)); return o; };
  if (netNames.length) {
    // Cada red = su(s) columna(s) de máquinas; los routers (2+ redes) van en una columna entre cajas
    const isRouter = (r) => netsOf(r).length > 1;
    const placed = new Set();
    netNames.forEach((n, i) => {
      const own = nets[n].filter((r) => !isRouter(r) && !placed.has(r)).sort(byDepth);
      own.forEach((r) => placed.add(r));
      chunk(own, 3).forEach((c, k) => cols.push({ roles: c, extra: k === 0 && i > 0 ? 34 : 0 }));
      // Red solo con routers: columna con un hijo invisible para que su caja se dibuje igualmente
      if (!own.length && dims.node["__net:" + n]) cols.push({ roles: ["__net:" + n], extra: i > 0 ? 34 : 0 });
      const rs = roles.filter((r) => isRouter(r) && !placed.has(r) && netsOf(r)[0] === n);
      if (rs.length) { rs.forEach((r) => placed.add(r)); cols.push({ roles: rs.sort(byDepth), extra: 34 }); }
    });
    const rest = roles.filter((r) => !placed.has(r)).sort(byDepth);
    if (rest.length) cols.push({ roles: rest, extra: 0 });
  } else {
    const min = Math.min(...roles.map((r) => depth[r]));
    const groups = {};
    roles.forEach((r) => { (groups[depth[r] - min] = groups[depth[r] - min] || []).push(r); });
    Object.keys(groups).map(Number).sort((a, b) => a - b).forEach((d) => cols.push({ roles: groups[d].sort(byDepth), extra: 0 }));
  }

  const maxVia = Math.max(0, ...links.map((l) => (l.via || "").length), ((topo.entry && topo.entry.via) || "").length);
  const gap = dims.compact ? 100 : Math.min(260, Math.max(110, maxVia * 6.3 + 44));
  const pos = {};
  const all = [];
  if (topo.entry) all.push({ entry: true, roles: [], w: dims.entryW, extra: 0 });
  cols.forEach((c) => all.push({ ...c, w: Math.max(...c.roles.map((r) => dims.node[r].w)) }));
  let x = 0, prevW = 0;
  all.forEach((c, i) => {
    x += i === 0 ? c.w / 2 : prevW / 2 + gap + (c.extra || 0) + c.w / 2;
    prevW = c.w;
    if (c.entry) { pos.__entry = { x, y: 0 }; return; }
    const total = c.roles.reduce((s, r) => s + dims.node[r].h, 0) + (c.roles.length - 1) * 42;
    let y = -total / 2;
    c.roles.forEach((r) => { pos[r] = { x, y: y + dims.node[r].h / 2 }; y += dims.node[r].h + 42; });
  });
  const tall = netNames.length > 0 || cols.some((c) => c.roles.length >= 3);
  return { pos, nets, netsOf, tall };
}

function drawTopology(container, topo, opts = {}) {
  if (container._topo) container._topo.destroy();
  container.innerHTML = "";
  if (typeof cytoscape === "undefined" || !topo || !topo.nodes || !Object.keys(topo.nodes).length) return null;
  const o = { ipOf: {}, statusOf: () => null, activeRole: null, onNodeClick: null, minHeight: 0, compact: false, ...opts };
  const roles = Object.keys(topo.nodes);
  // «tú» solo si apunta a un nodo que existe
  if (topo.entry && !roles.includes(topo.entry.to)) topo = { ...topo, entry: null };
  const links = topo.links || [];
  const clip = (t, n) => (t.length > n ? t.slice(0, n - 1) + "…" : t);
  const badge = (st) => (st === "ok" ? " ✓" : st === "bad" ? " ✗" : "");

  const dims = { entryW: o.compact ? 72 : 96, node: {}, compact: o.compact };
  roles.forEach((r) => {
    const runs = clip((topo.nodes[r] || {}).runs || "", o.compact ? 22 : 42);
    const ipLines = o.ipOf[r] ? String(o.ipOf[r]).split("\n") : [];
    const lines = 1 + ipLines.length + (runs ? 1 : 0);
    const longest = Math.max(runs.length, r.length + 4, ...ipLines.map((t) => t.length));
    dims.node[r] = o.compact
      ? { w: Math.max(120, Math.min(190, Math.ceil(longest * 7.6 + 24))), h: 14 + lines * 16, runs }
      : { w: Math.max(150, Math.min(290, Math.ceil(longest * 6.4 + 30))), h: 16 + lines * 15, runs };
  });
  // Redes sin ninguna máquina propia (solo routers): hijo invisible para que la caja exista
  const ghostNets = Object.entries(topo.networks || {}).filter(([, rs]) => {
    const mine = rs.filter((q) => roles.includes(q));
    return mine.length && mine.every((q) => Object.values(topo.networks).filter((x) => x.includes(q)).length > 1);
  }).map(([n]) => n);
  ghostNets.forEach((n) => { dims.node["__net:" + n] = { w: 110, h: 30, runs: "" }; });
  const lay = topoLayout(topo, dims);

  const els = [];
  Object.keys(lay.nets).forEach((n) => {
    if (ghostNets.includes(n)) {
      els.push({ group: "nodes", data: { id: "net:" + n, label: n }, classes: "net" });
      els.push({ group: "nodes", data: { id: "ghost:" + n, parent: "net:" + n, w: 110, h: 30 }, classes: "ghost", position: lay.pos["__net:" + n] });
    } else if (lay.nets[n].some((r) => lay.netsOf(r).length === 1)) els.push({ group: "nodes", data: { id: "net:" + n, label: n }, classes: "net" });
  });
  roles.forEach((r) => {
    const nets = lay.netsOf(r);
    const router = nets.length > 1;
    els.push({
      group: "nodes", classes: "n" + (router ? " router" : ""), position: lay.pos[r],
      data: { id: "n:" + r, role: r, label: "", w: dims.node[r].w, h: dims.node[r].h, ...(nets.length === 1 ? { parent: "net:" + nets[0] } : {}) },
    });
    // El router queda fuera de las cajas: aristas finas de pertenencia hacia cada red a la que está unido
    // Solo si el router no tiene ya enlaces con máquinas de esa red (si los tiene, la pertenencia ya se ve)
    const linked = (n) => links.some((l) => (l.from === r && lay.nets[n].includes(l.to) && l.to !== r) || (l.to === r && lay.nets[n].includes(l.from) && l.from !== r));
    if (router) nets.forEach((n) => {
      if (!linked(n) && (ghostNets.includes(n) || lay.nets[n].some((q) => lay.netsOf(q).length === 1))) els.push({ group: "edges", classes: "member", data: { id: `m:${r}:${n}`, source: "n:" + r, target: "net:" + n } });
    });
  });
  if (topo.entry) {
    els.push({ group: "nodes", classes: "entry", position: lay.pos.__entry, data: { id: "entry", w: dims.entryW, h: 40, label: topo.entry.label || "tú" } });
    if (roles.includes(topo.entry.to)) els.push({ group: "edges", classes: "l", data: { id: "e:entry", label: "", source: "entry", target: "n:" + topo.entry.to, via: topo.entry.via || "", tk: "entry" } });
  }
  links.forEach((l, i) => {
    if (roles.includes(l.from) && roles.includes(l.to)) els.push({ group: "edges", classes: "l", data: { id: "e:" + i, label: "", source: "n:" + l.from, target: "n:" + l.to, via: l.via || "", tk: "link:" + i } });
  });

  // Alto según el dibujo: entre 150 y 260 px
  const ys = Object.values(lay.pos).map((p) => p.y);
  const rawH = (ys.length ? Math.max(...ys) - Math.min(...ys) : 0) + 70 + (Object.keys(lay.nets).length ? 60 : 24);
  container.style.height = Math.round(Math.min(lay.tall ? 320 : 260, Math.max(o.minHeight || 150, rawH))) + "px";

  const cy = cytoscape({
    container, elements: els, layout: { name: "preset" }, style: topoStyle(topoColors(), !!o.compact),
    autoungrabify: true, boxSelectionEnabled: false, userZoomingEnabled: false,
    minZoom: 0.2, maxZoom: 2.5,
  });

  const apply = (st) => {
    cy.batch(() => {
      cy.nodes(".n").forEach((n) => {
        const r = n.data("role"), status = st.statusOf(`node:${r}`);
        const ip = o.ipOf[r];
        n.data("label", `${n.hasClass("router") ? "⇄ " : ""}${r}${badge(status)}` + (ip ? `\n${ip}` : "") + (dims.node[r].runs ? `\n${dims.node[r].runs}` : ""));
        n.removeClass("ok bad");
        if (status) n.addClass(status);
        n.toggleClass("active", st.activeRole === r);
      });
      cy.edges(".l").forEach((e) => {
        const status = st.statusOf(e.data("tk"));
        e.data("label", (e.data("via") + badge(status)).trim());
        e.removeClass("ok bad");
        if (status) e.addClass(status);
      });
    });
  };
  apply(o);

  if (o.onNodeClick) cy.on("tap", "node.n", (ev) => o.onNodeClick(ev.target.data("role")));
  cy.on("mouseover", "node.n", () => { if (o.onNodeClick) container.style.cursor = "pointer"; });
  cy.on("mouseout", "node.n", () => { container.style.cursor = ""; });

  // Zoom solo con Ctrl + rueda (la rueda sola sigue haciendo scroll de la página); doble clic = ajustar
  const onWheel = (e) => {
    if (!e.ctrlKey) return;
    e.preventDefault();
    const r = container.getBoundingClientRect();
    cy.zoom({ level: Math.min(2.5, Math.max(0.2, cy.zoom() * (e.deltaY < 0 ? 1.12 : 0.89))), renderedPosition: { x: e.clientX - r.left, y: e.clientY - r.top } });
  };
  const onDbl = () => { cy.fit(undefined, 12); if (cy.zoom() > 1.1) { cy.zoom(1.1); cy.center(); } };
  container.addEventListener("wheel", onWheel, { passive: false });
  container.addEventListener("dblclick", onDbl);

  // Ajusta al contenedor sin ampliar de más (cajas enormes en dibujos pequeños)
  const refit = () => { try { cy.resize(); cy.fit(undefined, 12); if (cy.zoom() > 1.1) { cy.zoom(1.1); cy.center(); } } catch (_) {} };
  let ro = null;
  if (typeof ResizeObserver !== "undefined") { ro = new ResizeObserver(refit); ro.observe(container); }
  refit();

  const handle = {
    cy,
    update(next) { Object.assign(o, next); apply(o); },
    restyle() { cy.style(topoStyle(topoColors(), !!o.compact)); },
    destroy() {
      TOPO_LIVE.delete(handle);
      if (ro) ro.disconnect();
      container.removeEventListener("wheel", onWheel);
      container.removeEventListener("dblclick", onDbl);
      try { cy.destroy(); } catch (_) {}
      if (container._topo === handle) container._topo = null;
    },
  };
  container._topo = handle;
  TOPO_LIVE.add(handle);
  return handle;
}

function restyleTopologies() {
  TOPO_LIVE.forEach((h) => { try { h.restyle(); } catch (_) {} });
}

function renderTopology(active) {
  const strip = $("topo-strip");
  const body = $("topo-body");
  const topo = active && active.topology;
  const unNodoTarea = active && active.tipo === "tarea" && topo && Object.keys(topo.nodes || {}).length < 2;
  if (!topo || !topo.nodes || !Object.keys(topo.nodes).length || unNodoTarea) {
    strip.classList.add("hidden");
    if (body._topo) body._topo.destroy();
    body._sig = null;
    return;
  }
  strip.classList.remove("hidden");
  let collapsed = false;
  try { collapsed = localStorage.getItem("chaos-topo-collapsed") === "1"; } catch (_) {}
  strip.classList.toggle("collapsed", collapsed);
  $("btn-topo-toggle").textContent = collapsed ? "Mostrar esquema" : "Ocultar";
  if (collapsed) { if (body._topo) body._topo.destroy(); body._sig = null; return; }

  // Router con varias IPs: una línea «red ip» por red
  const ipOf = Object.fromEntries((active.nodes || []).map((n) => {
    const ips = Object.entries(n.ips || {});
    return [n.role, ips.length > 1 ? ips.map(([net, ip]) => `${net} ${ip}`).join("\n") : n.ip];
  }));
  const st = { statusOf: (t) => topoStatus(active, t), activeRole: state.activeNodeRole };
  // Misma estructura que la última vez: solo se repintan estados (se conserva el zoom/arrastre del usuario)
  const sig = JSON.stringify([active.session_id, topo.entry, topo.nodes, topo.links, topo.networks, ipOf]);
  if (body._topo && body._sig === sig) { body._topo.update(st); return; }
  body._sig = sig;
  drawTopology(body, topo, { ipOf, ...st, onNodeClick: (role) => selectNodeTab(role) });
}

function renderHowtoLook(active) {
  const topo = active && active.topology;
  const box = $("howto-look");
  const toolsOf = Object.fromEntries(((active && active.nodes) || []).map((n) => [n.role, n.tools || []]));
  const tools = (role) => (toolsOf[role] && toolsOf[role].length)
    ? `<div class="look-tools">🧰 Herramientas: ${toolsOf[role].map((t) => `<code>${escapeHtml(t)}</code>`).join("")}</div>`
    : "";
  if (!topo || !topo.nodes) {
    // Sin esquema: al menos las herramientas de cada nodo
    box.innerHTML = Object.keys(toolsOf).map((role) =>
      `<div class="look-node"><b>${escapeHtml(role)}</b>${tools(role)}</div>`).join("");
    return;
  }
  box.innerHTML = Object.entries(topo.nodes)
    .map(([role, n]) =>
      `<div class="look-node">` +
      ((n.look && n.look.length)
        ? `Dónde mirar en <b>${escapeHtml(role)}</b>:<br>` + n.look.map((x) => `<code>${escapeHtml(x)}</code>`).join("")
        : `<b>${escapeHtml(role)}</b>`) +
      tools(role) + `</div>`)
    .join("");
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = $("btn-topo-toggle");
  if (btn) btn.addEventListener("click", () => {
    const strip = $("topo-strip");
    const now = !strip.classList.contains("collapsed");
    try { localStorage.setItem("chaos-topo-collapsed", now ? "1" : "0"); } catch (_) {}
    if (state.active) renderTopology(state.active);
    // el terminal cambia de alto: reajustar
    const s = state.sessions[state.activeNodeRole];
    if (s) requestAnimationFrame(() => { try { s.fitAddon.fit(); } catch (_) {} });
  });
});

/* -------------------- Terminales PTY Multi-Nodo -------------------- */

function setupNodeTerminals(nodes) {
  const wrapper = $("terminals-wrapper");
  nodes.forEach((n, idx) => {
    const slot = document.createElement("div");
    slot.className = "term-slot" + (idx === 0 ? "" : " hidden-slot");
    wrapper.appendChild(slot);

    const term = new window.Terminal({
      cursorBlink: true,
      fontSize: 13.5,
      fontFamily: '"JetBrains Mono", "Fira Code", monospace',
      scrollback: 3000,
      theme: termTheme(),
    });
    const fitAddon = new window.FitAddon.FitAddon();
    term.loadAddon(fitAddon);
    term.open(slot);

    state.sessions[n.role] = { term, fitAddon, ws: null, slotEl: slot, node: n };
    connectNodeWs(n.role);
  });

  if (nodes.length > 0) {
    selectNodeTab(nodes[0].role);
  }
}

function connectNodeWs(role) {
  const sess = state.sessions[role];
  if (!sess) return;
  if (sess.ws) {
    try { sess.ws.close(); } catch (_) {}
  }

  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${location.host}/ws/terminal/${encodeURIComponent(role)}`);
  sess.ws = ws;

  ws.onopen = () => {
    try {
      sess.fitAddon.fit();
      ws.send(JSON.stringify({ type: "resize", cols: sess.term.cols, rows: sess.term.rows }));
    } catch (_) {}
  };

  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === "output") {
        sess.term.write(msg.data);
      }
    } catch (_) {}
  };

  if (!sess._boundInput) {
    sess._boundInput = true;
    sess.term.onData((data) => {
      if (sess.ws && sess.ws.readyState === WebSocket.OPEN) {
        sess.ws.send(JSON.stringify({ type: "input", data }));
      }
    });
  }
}

function selectNodeTab(role) {
  state.activeNodeRole = role;
  Object.entries(state.sessions).forEach(([r, s]) => {
    const active = r === role;
    s.slotEl.classList.toggle("hidden-slot", !active);
    if (active) {
      requestAnimationFrame(() => {
        try {
          s.fitAddon.fit();
          if (s.ws && s.ws.readyState === WebSocket.OPEN) {
            s.ws.send(JSON.stringify({ type: "resize", cols: s.term.cols, rows: s.term.rows }));
          }
          s.term.focus();
        } catch (_) {}
      });
    }
  });
  if (state.active) {
    renderNodeTabs(state.active.nodes || []);
    renderTopology(state.active);
  }
}

function renderNodeTabs(nodes) {
  $("node-tabs").innerHTML = nodes
    .map(
      (n) => `
      <button class="node-tab ${state.activeNodeRole === n.role ? "active" : ""}" data-role="${escapeHtml(n.role)}">
        <span class="dot ok"></span>
        <span>${escapeHtml(n.role)}</span>
        <span class="node-ip">${escapeHtml(n.ip)}</span>
      </button>`
    )
    .join("");

  $("node-tabs").querySelectorAll(".node-tab").forEach((btn) => {
    btn.addEventListener("click", () => selectNodeTab(btn.dataset.role));
  });
}

window.addEventListener("resize", () => {
  if (!state.activeNodeRole) return;
  const s = state.sessions[state.activeNodeRole];
  if (s) {
    try {
      s.fitAddon.fit();
      if (s.ws && s.ws.readyState === WebSocket.OPEN) {
        s.ws.send(JSON.stringify({ type: "resize", cols: s.term.cols, rows: s.term.rows }));
      }
    } catch (_) {}
  }
});

/* -------------------- Acciones de Usuario -------------------- */

async function runVerify() {
  const btn = $("btn-verify");
  btn.disabled = true;
  btn.textContent = "⏳ Comprobando sondas…";
  try {
    const res = await api("/api/lab/verify", { method: "POST" });
    if (res.active) state.verifiedSession = res.active.session_id;
    syncActiveView(res.active);
    if (res.all_passed) {
      showToast(`🏆 ¡Incidente resuelto! Rango ${res.active.rank}`);
      await refreshCatalog();
    } else {
      showToast(`Sondas superadas: ${res.passed_count}/${res.total_checks}`);
    }
  } catch (err) {
    showToast(`❌ ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = "✓ Ejecutar Verificación en Vivo";
  }
}

async function openPostMortem() {
  try {
    const res = await api("/api/lab/postmortem");
    state.pmFilename = res.filename || "postmortem.md";
    $("pm-textarea").value = res.markdown || "";
    $("pm-modal").classList.remove("hidden");
  } catch (err) {
    showToast(`❌ ${err.message}`);
  }
}

function bindEvents() {
  // Ficha de vista previa: se cierra con ✕, Esc o clic fuera; desde ella se puede desplegar
  $("btn-close-pv").addEventListener("click", closePreview);
  $("pv-modal").addEventListener("click", (e) => { if (e.target.id === "pv-modal") closePreview(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && state.previewId) closePreview(); });
  $("btn-pv-launch").addEventListener("click", () => { const id = state.previewId; closePreview(); launchScenario(id, false); });
  $("btn-pv-blind").addEventListener("click", () => { const id = state.previewId; closePreview(); launchScenario(id, true); });
  // Clic (o Enter/Espacio) en una tarjeta del catálogo: abre su ficha sin desplegar nada
  const scList = $("scenario-list");
  scList.addEventListener("click", (e) => {
    if (e.target.closest("button, a")) return;
    const card = e.target.closest(".sc-card");
    if (card) openPreview(card.dataset.id);
  });
  scList.addEventListener("keydown", (e) => {
    if ((e.key === "Enter" || e.key === " ") && e.target.classList.contains("sc-card")) {
      e.preventDefault();
      openPreview(e.target.dataset.id);
    }
  });
  $("btn-blind-launch").addEventListener("click", () => launchScenario(null, true));
  $("btn-empty-blind").addEventListener("click", () => launchScenario(null, true));
  $("btn-empty-first").addEventListener("click", () => launchScenario("net-nginx-bad-gateway", false));

  $("search-input").addEventListener("input", (e) => {
    state.search = e.target.value;
    renderScenarioList();
  });

  $("filter-category")?.addEventListener("change", (e) => { state.category = e.target.value; renderScenarioList(); });
  $("filter-cert")?.addEventListener("change", (e) => { state.cert = e.target.value; renderScenarioList(); });

  $("filter-chips").querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      $("filter-chips").querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      state.filter = chip.dataset.filter;
      renderScenarioList();
    });
  });

  $("btn-toggle-history").addEventListener("click", () => $("history-drawer").classList.remove("hidden"));
  $("btn-close-history").addEventListener("click", () => $("history-drawer").classList.add("hidden"));

  $("btn-verify").addEventListener("click", runVerify);

  $("btn-unlock-hint").addEventListener("click", async () => {
    try {
      const res = await api("/api/lab/hint", { method: "POST" });
      syncActiveView(res.active);
    } catch (err) {
      showToast(`❌ ${err.message}`);
    }
  });

  $("btn-reveal-blind").addEventListener("click", async () => {
    try {
      const res = await api("/api/lab/reveal", { method: "POST" });
      syncActiveView(res.active);
      renderScenarioList();
      showToast("👁 Identidad del escenario revelada");
    } catch (err) {
      showToast(`❌ ${err.message}`);
    }
  });

  $("btn-remutate").addEventListener("click", () => {
    if (!state.active) return;
    const realId = state.active.real_scenario_id;
    launchScenario(realId, state.active.blind_mode);
  });

  $("btn-stop-lab").addEventListener("click", async () => {
    setLoading(true, "Limpiando contenedores y red efímera…");
    try {
      await api("/api/lab/stop", { method: "POST" });
      syncActiveView(null);
      renderScenarioList();
      showToast("⏹ Laboratorio detenido y limpio");
    } catch (err) {
      showToast(`❌ ${err.message}`);
    } finally {
      setLoading(false);
    }
  });

  $("btn-ask-mentor").addEventListener("click", async () => {
    const btn = $("btn-ask-mentor");
    btn.disabled = true;
    $("mentor-output").textContent = "Analizando tus comandos…";
    try {
      const q = $("mentor-input").value;
      const res = await api("/api/lab/mentor", {
        method: "POST",
        body: JSON.stringify({ question: q }),
      });
      $("mentor-source-tag").textContent = res.source || "Mentor";
      $("mentor-output").textContent = res.advice || "";
      $("mentor-input").value = "";
    } catch (err) {
      $("mentor-output").textContent = `Error: ${err.message}`;
    } finally {
      btn.disabled = false;
    }
  });

  $("btn-copy-cli").addEventListener("click", async () => {
    if (!state.active || !state.activeNodeRole) return;
    const n = (state.active.nodes || []).find((x) => x.role === state.activeNodeRole);
    if (n && n.cli_attach) {
      await navigator.clipboard.writeText(n.cli_attach);
      showToast("📋 Comando 'podman exec' copiado al portapapeles");
    }
  });

  $("btn-reconnect-tty").addEventListener("click", () => {
    if (state.activeNodeRole) {
      connectNodeWs(state.activeNodeRole);
      showToast(`🔌 Reconectado a ${state.activeNodeRole}`);
    }
  });

  $("btn-clear-tty").addEventListener("click", () => {
    const s = state.sessions[state.activeNodeRole];
    if (s && s.term) s.term.clear();
  });

  $("btn-postmortem").addEventListener("click", openPostMortem);
  $("btn-victory-pm").addEventListener("click", openPostMortem);
  $("btn-close-pm").addEventListener("click", () => $("pm-modal").classList.add("hidden"));

  $("btn-copy-pm").addEventListener("click", async () => {
    await navigator.clipboard.writeText($("pm-textarea").value);
    showToast("📋 Post-Mortem copiado");
  });

  $("btn-vault-pm")?.addEventListener("click", async () => {
    try {
      const res = await api("/api/lab/export-vault", { method: "POST" });
      showToast(`📝 Post-mortem guardado: ${res.path}`);
    } catch (err) {
      showToast(`❌ ${err.message}`);
    }
  });

  $("btn-download-pm").addEventListener("click", () => {
    const blob = new Blob([$("pm-textarea").value], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = state.pmFilename;
    a.click();
    URL.revokeObjectURL(url);
  });
}

(async function init() {
  bindEvents();
  await refreshHealth();
  await refreshCatalog();
  setInterval(refreshHealth, 20000);
})();
