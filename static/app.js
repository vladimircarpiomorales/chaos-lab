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
      <div class="sc-card ${isCurrent ? "active-sc" : ""}">
        <div class="sc-top">
          <div class="sc-title">${escapeHtml(sc.title)}</div>
          ${solvedBadge}
        </div>
        <div class="sc-meta">
          <span class="badge diff-${escapeHtml(sc.difficulty)}">${escapeHtml(sc.difficulty)}</span>
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
            <button class="btn-ghost-sm" onclick="launchScenario('${sc.id}', true)" title="Jugar ocultando pistas de sondas (+25% XP)">🎲</button>
            <button class="btn btn-primary btn-sm" onclick="launchScenario('${sc.id}', false)">▶ Desplegar</button>
          </div>
        </div>
      </div>`;
    })
    .join("");
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
  $("active-desc").textContent = active.description;

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

function svgText(x, y, cls, text, anchor = "middle") {
  return `<text x="${x}" y="${y}" class="${cls}" text-anchor="${anchor}">${escapeHtml(text)}</text>`;
}

function renderTopology(active) {
  const strip = $("topo-strip");
  const topo = active && active.topology;
  if (!topo || !topo.nodes) {
    strip.classList.add("hidden");
    return;
  }
  strip.classList.remove("hidden");
  let collapsed = false;
  try { collapsed = localStorage.getItem("chaos-topo-collapsed") === "1"; } catch (_) {}
  strip.classList.toggle("collapsed", collapsed);
  $("btn-topo-toggle").textContent = collapsed ? "Mostrar esquema" : "Ocultar";

  const ipOf = Object.fromEntries((active.nodes || []).map((n) => [n.role, n.ip]));
  const roles = Object.keys(topo.nodes);
  const W = 190, H = 78, EW = 110, PAD = 6, TOP = 12;
  const gapFor = (txt) => Math.max(80, (txt || "").length * 6.7 + 24);

  // Columnas: [entrada] → nodos en el orden del esquema
  const cols = [];
  let x = PAD;
  const linkVia = {};
  (topo.links || []).forEach((l) => { linkVia[l.from + ">" + l.to] = l.via || ""; });
  if (topo.entry) {
    cols.push({ kind: "entry", x, w: EW });
    x += EW + gapFor(topo.entry.via);
  }
  roles.forEach((r, i) => {
    // La caja se ensancha si el texto de «qué corre» no cabe en el ancho base
    const w = Math.max(W, Math.ceil(((topo.nodes[r] || {}).runs || "").length * 6.4 + 28));
    cols.push({ kind: "node", role: r, x, w });
    const next = roles[i + 1];
    x += w + (next ? gapFor(linkVia[r + ">" + next]) : 0);
  });
  const width = x + PAD;
  const pos = Object.fromEntries(cols.filter((c) => c.kind === "node").map((c) => [c.role, c]));
  const hasBack = (topo.links || []).some((l) => pos[l.from] && pos[l.to] && pos[l.to].x <= pos[l.from].x);
  const height = TOP + H + (hasBack ? 52 : 26);

  const arrow = (x1, x2, y, via, st, key) => {
    const cls = st ? ` st-${st}` : "";
    const mid = (x1 + x2) / 2;
    let out = `<line x1="${x1}" y1="${y}" x2="${x2 - 8}" y2="${y}" class="topo-link${cls}" data-k="${key}"/>`;
    out += `<path d="M${x2 - 9},${y - 5} L${x2},${y} L${x2 - 9},${y + 5} Z" class="topo-arrow${cls}"/>`;
    if (via) out += svgText(mid, y - 9, "topo-via", via);
    if (st) out += svgText(mid, y + 18, `topo-badge st-${st}`, st === "ok" ? "✓" : "✗");
    return out;
  };

  let svg = "";
  const cy = TOP + H / 2;
  if (topo.entry) {
    const st = topoStatus(active, "entry");
    svg += `<g class="topo-entry"><rect x="${PAD}" y="${TOP + 12}" width="${EW}" height="${H - 24}" rx="8" class="topo-box"/>` +
      svgText(PAD + EW / 2, cy + 4, "topo-name", topo.entry.label || "tú") + `</g>`;
    const target = pos[topo.entry.to];
    if (target) svg += arrow(PAD + EW, target.x, cy, topo.entry.via, st, "entry");
  }
  (topo.links || []).forEach((l, i) => {
    const a = pos[l.from], b = pos[l.to];
    if (!a || !b) return;
    const st = topoStatus(active, `link:${i}`);
    if (b.x > a.x) {
      svg += arrow(a.x + a.w, b.x, cy, l.via, st, `link:${i}`);
    } else {
      // Enlace hacia atrás (p. ej. dos clientes hacia el mismo servidor): curva por debajo con punta, texto y estado
      const y0 = TOP + H, yb = TOP + H + 30;
      const cls = st ? ` st-${st}` : "";
      const x1 = a.x + 30, x2 = b.x + b.w - 30, mid = (x1 + x2) / 2;
      svg += `<path d="M${x1},${y0} C${x1},${yb} ${x2},${yb} ${x2},${y0 + 9}" class="topo-link${cls}" fill="none" data-k="link:${i}"/>`;
      svg += `<path d="M${x2 - 5},${y0 + 9} L${x2},${y0} L${x2 + 5},${y0 + 9} Z" class="topo-arrow${cls}"/>`;
      if (l.via) svg += svgText(mid, yb + 14, "topo-via", l.via);
      if (st) svg += svgText(mid, yb - 4, `topo-badge st-${st}`, st === "ok" ? "✓" : "✗");
    }
  });
  cols.filter((c) => c.kind === "node").forEach((c) => {
    const info = topo.nodes[c.role] || {};
    const st = topoStatus(active, `node:${c.role}`);
    const isActive = state.activeNodeRole === c.role;
    svg += `<g class="topo-node${st ? " st-" + st : ""}${isActive ? " is-active" : ""}" data-role="${escapeHtml(c.role)}">` +
      `<rect x="${c.x}" y="${TOP}" width="${c.w}" height="${H}" rx="10" class="topo-box"/>` +
      svgText(c.x + 14, TOP + 24, "topo-name", c.role, "start") +
      svgText(c.x + 14, TOP + 42, "topo-ip", ipOf[c.role] || "", "start") +
      (info.runs ? svgText(c.x + 14, TOP + 62, "topo-runs", info.runs, "start") : "") +
      (st ? svgText(c.x + c.w - 14, TOP + 24, `topo-badge st-${st}`, st === "ok" ? "✓" : "✗", "end") : "") +
      `</g>`;
  });

  $("topo-body").innerHTML =
    `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMinYMid meet" role="img" aria-label="Esquema de la topología">${svg}</svg>`;
  $("topo-body").querySelectorAll(".topo-node").forEach((g) => {
    g.addEventListener("click", () => selectNodeTab(g.dataset.role));
  });
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
