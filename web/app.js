const LABELS = {
  A: "A", B: "B", X: "X", Y: "Y",
  LB: "LB (traseira)", RB: "RB (traseira)", LT: "LT (traseira)", RT: "RT (traseira)",
  M1: "M1 (paddle)", M2: "M2 (paddle)", M3: "M3 (paddle)", M4: "M4 (paddle)",
  START: "Start", BACK: "Back", LS: "LS click", RS: "RS click",
  DUP: "D-pad ↑", DDOWN: "D-pad ↓", DLEFT: "D-pad ←", DRIGHT: "D-pad →",
};

const STEP_LABELS = {
  mouse_move: "Mover mouse",
  mouse_click: "Clique",
  mouse_down: "Segurar clique",
  mouse_up: "Soltar clique",
  key_tap: "Tecla",
  key_down: "Segurar tecla",
  key_up: "Soltar tecla",
  wait: "Esperar",
  wheel: "Scroll",
};

const BIND_ORDER = ["A", "B", "X", "Y", "LB", "RB", "LT", "RT", "M1", "M2", "M3", "M4", "START", "BACK", "LS", "RS", "DUP", "DDOWN", "DLEFT", "DRIGHT"];

let config = null;
let state = null;
let bindTarget = null;
let capturing = false;
let saveTimer = 0;

const $ = (id) => document.getElementById(id);

async function api(path, body) {
  const opts = body === undefined
    ? {}
    : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function activeSequence() {
  const id = config.activeSequenceId;
  return (config.sequences || []).find((s) => s.id === id) || config.sequences[0];
}

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

function sequenceName(id) {
  const seq = (config.sequences || []).find((s) => s.id === id);
  return seq ? seq.name : "sequência";
}

function padButtonForSequence(seqId) {
  const binds = (config.mapper && config.mapper.binds) || {};
  return BIND_ORDER.filter((name) => {
    const bind = binds[name];
    return bind && bind.kind === "sequence" && bind.sequenceId === seqId;
  });
}

function bindText(bind) {
  if (!bind || bind.kind === "none") return "—";
  if (bind.kind === "mouse") {
    const names = { left: "clique esq.", right: "clique dir.", middle: "clique meio" };
    return names[bind.button] || "clique";
  }
  if (bind.kind === "sequence") return `seq: ${sequenceName(bind.sequenceId)}`;
  return bind.key || "tecla";
}

function scheduleSave() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => api("/api/config", config).catch(console.error), 250);
}

function renderHeader() {
  if (!state) return;
  $("mouse-xy").textContent = `${state.mouse.x}, ${state.mouse.y}`;
  $("screen-size").textContent = `${state.screen.w}×${state.screen.h}`;
  const pad = $("pad-stat");
  $("pad-label").textContent = state.connected ? (state.padName || "conectado") : "desconectado";
  pad.classList.toggle("ok", state.connected);
  pad.classList.toggle("off", !state.connected);
  $("mapper-toggle").checked = !!state.mapperEnabled;
  if (config) config.mapper.enabled = !!state.mapperEnabled;

  const axes = state.axes || {};
  const place = (id, x, y) => {
    const nub = $(id);
    if (!nub) return;
    nub.style.transform = `translate(calc(-50% + ${((x || 0) * 28).toFixed(1)}px), calc(-50% + ${((y || 0) * 28).toFixed(1)}px))`;
  };
  place("nub-l", axes.lx, axes.ly);
  place("nub-r", axes.rx, axes.ry);

  document.querySelectorAll("[data-btn]").forEach((el) => {
    const name = el.dataset.btn;
    const analog = name === "LT" || name === "RT";
    const on = analog ? (axes[name.toLowerCase()] || 0) > 0.35 : !!(state.buttons || {})[name];
    el.classList.toggle("on", on);
  });

  const extra = $("extra-signals");
  if (extra) {
    const dbg = state.debug || {};
    const hid = (dbg.hid || []).join(", ");
    const wm = (dbg.winmmExtra || []).join(", ");
    const taught = Object.keys(state.paddleMap || {}).join(", ");
    extra.textContent = [
      hid ? `HID ${hid}` : "",
      wm ? `botão extra ${wm}` : "",
      taught ? `gravados: ${taught}` : "",
    ].filter(Boolean).join(" · ") || "Nenhum paddle extra. Clique Identificar M1 e aperte o botão de trás.";
  }
  const seq = state.sequence || {};
  const status = $("seq-status");
  if (seq.playing) {
    status.textContent = `Executando “${seq.name}” — passo ${seq.index + 1}${seq.repeatLeft > 1 ? ` (${seq.repeatLeft} reps)` : ""}. F11 para parar.`;
  }
}

function renderMapper() {
  if (!config) return;
  const m = config.mapper;
  $("left-stick").value = m.leftStick;
  $("right-stick").value = m.rightStick;
  $("sensitivity").value = m.sensitivity;
  $("sensitivity-val").textContent = m.sensitivity;
  $("deadzone").value = Math.round(m.deadzone * 100);
  $("deadzone-val").textContent = Number(m.deadzone).toFixed(2);
  $("curve").value = m.curve;
  $("invert-y").checked = !!m.invertY;

  const keys = (state && state.keys) || [];
  const keySelect = $("bind-key");
  if (!keySelect.dataset.filled) {
    keySelect.innerHTML = keys.map((k) => `<option value="${k}">${k}</option>`).join("");
    keySelect.dataset.filled = "1";
  }

  $("bind-list").innerHTML = BIND_ORDER.map((name) => {
    const bind = m.binds[name] || { kind: "none" };
    return `<button type="button" class="bind" data-bind="${name}"><b>${LABELS[name] || name}</b><span>${bindText(bind)}</span></button>`;
  }).join("");
}

function renderSequences() {
  if (!config) return;
  const sel = $("seq-select");
  sel.innerHTML = config.sequences.map((s) => `<option value="${s.id}">${s.name}</option>`).join("");
  const seq = activeSequence();
  if (!seq) return;
  sel.value = seq.id;
  $("seq-name").value = seq.name;
  $("seq-start").value = seq.startDelayMs;
  $("seq-repeat").value = seq.repeat;
  const padSel = $("seq-pad-bind");
  const assigned = padButtonForSequence(seq.id)[0] || "";
  padSel.innerHTML = `<option value="">Nenhum</option>` + BIND_ORDER.map((name) =>
    `<option value="${name}" ${assigned === name ? "selected" : ""}>${LABELS[name] || name}</option>`
  ).join("");
  padSel.value = assigned;
  $("seq-library").innerHTML = config.sequences.map((s) => {
    const pads = padButtonForSequence(s.id).map((n) => LABELS[n] || n).join(", ");
    return `<button type="button" class="seq-chip ${s.id === seq.id ? "active" : ""}" data-seq="${s.id}">${s.name}${pads ? `<small>${pads}</small>` : ""}</button>`;
  }).join("");
  const playingIndex = state && state.sequence && state.sequence.playing ? state.sequence.index : -1;
  $("steps").innerHTML = seq.steps.map((step, i) => stepRow(step, i, i === playingIndex)).join("");
}

function stepRow(step, i, active) {
  const fields = fieldsFor(step);
  return `
    <article class="step ${active ? "active" : ""}" data-id="${step.id}">
      <div class="idx">${String(i + 1).padStart(2, "0")}</div>
      <select data-k="type">${Object.entries(STEP_LABELS).map(([k, v]) =>
        `<option value="${k}" ${step.type === k ? "selected" : ""}>${v}</option>`).join("")}</select>
      <div class="step-fields">${fields}</div>
      <div class="step-actions">
        <div class="ms-box">ms <input type="number" min="0" step="10" data-k="ms" value="${step.ms ?? 0}" /></div>
        <button type="button" data-act="up" title="Subir">↑</button>
        <button type="button" data-act="down" title="Descer">↓</button>
        <button type="button" data-act="test">Testar</button>
        <button type="button" data-act="del" class="danger">×</button>
      </div>
    </article>`;
}

function fieldsFor(step) {
  const mouseBtns = `
    <label>Botão
      <select data-k="button">
        <option value="left" ${step.button === "left" ? "selected" : ""}>Esquerdo</option>
        <option value="right" ${step.button === "right" ? "selected" : ""}>Direito</option>
        <option value="middle" ${step.button === "middle" ? "selected" : ""}>Meio</option>
      </select>
    </label>`;
  const keys = ((state && state.keys) || []).filter((k) => k !== "NONE");
  const keySel = `
    <label>Tecla
      <select data-k="key">${keys.map((k) => `<option ${step.key === k ? "selected" : ""}>${k}</option>`).join("")}</select>
    </label>`;
  if (step.type === "mouse_move") {
    return `
      <label>X <input type="number" data-k="x" value="${step.x ?? 0}" /></label>
      <label>Y <input type="number" data-k="y" value="${step.y ?? 0}" /></label>
      <button type="button" data-act="capture">Capturar posição (2s)</button>`;
  }
  if (step.type === "mouse_click" || step.type === "mouse_down" || step.type === "mouse_up") return mouseBtns;
  if (step.type === "key_tap" || step.type === "key_down" || step.type === "key_up") return keySel;
  if (step.type === "wheel") {
    return `<label>Delta <input type="number" data-k="delta" value="${step.delta ?? 120}" /></label>`;
  }
  return `<span>pausa antes do próximo passo</span>`;
}

function newStep(type) {
  const step = { id: uid(), type, ms: 100 };
  if (type === "mouse_move") {
    step.x = state ? state.mouse.x : 0;
    step.y = state ? state.mouse.y : 0;
    step.ms = 200;
  }
  if (type.startsWith("mouse_")) step.button = "left";
  if (type.startsWith("key_")) step.key = "F1";
  if (type === "mouse_click" || type === "key_tap") step.ms = 40;
  if (type === "wait") step.ms = 250;
  if (type === "wheel") step.delta = 120;
  return step;
}

function openBind(name) {
  bindTarget = name;
  const bind = config.mapper.binds[name] || { kind: "none" };
  $("bind-title").textContent = `Botão ${LABELS[name] || name}`;
  $("bind-kind").value = bind.kind || "none";
  $("bind-mouse").value = bind.button || "left";
  $("bind-key").value = bind.key || "SPACE";
  $("bind-seq").innerHTML = (config.sequences || []).map((s) =>
    `<option value="${s.id}" ${bind.sequenceId === s.id ? "selected" : ""}>${s.name}</option>`
  ).join("");
  if (bind.sequenceId) $("bind-seq").value = bind.sequenceId;
  toggleBindFields();
  $("bind-modal").classList.remove("hidden");
}

function toggleBindFields() {
  const kind = $("bind-kind").value;
  $("bind-mouse-wrap").style.display = kind === "mouse" ? "" : "none";
  $("bind-key-wrap").style.display = kind === "key" ? "" : "none";
  $("bind-seq-wrap").style.display = kind === "sequence" ? "" : "none";
}

async function captureMouse(step) {
  capturing = true;
  const overlay = $("overlay");
  overlay.classList.remove("hidden");
  $("overlay-title").textContent = "Posicione o mouse no ponto desejado";
  const started = Date.now();
  const tick = () => {
    const left = Math.max(0, 2000 - (Date.now() - started));
    $("overlay-count").textContent = `${(left / 1000).toFixed(1)}s`;
    if (left > 0 && capturing) requestAnimationFrame(tick);
  };
  tick();
  try {
    const pos = await api("/api/capture-mouse", { delayMs: 2000 });
    step.x = pos.x;
    step.y = pos.y;
    scheduleSave();
    renderSequences();
  } finally {
    capturing = false;
    overlay.classList.add("hidden");
  }
}

function bindEvents() {
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b === btn));
      $("view-map").classList.toggle("hidden", btn.dataset.tab !== "map");
      $("view-seq").classList.toggle("hidden", btn.dataset.tab !== "seq");
    });
  });

  $("mapper-toggle").addEventListener("change", async (e) => {
    await api("/api/mapper", { enabled: e.target.checked });
  });

  document.querySelector(".learn-row").addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-learn]");
    if (!btn) return;
    e.stopPropagation();
    const name = btn.dataset.learn;
    const overlay = $("overlay");
    overlay.classList.remove("hidden");
    $("overlay-title").textContent = `Aperte só o ${name} no controle`;
    $("overlay-count").textContent = "6s";
    try {
      const r = await api("/api/learn-paddle", { name });
      config.mapper.paddleMap = config.mapper.paddleMap || {};
      config.mapper.paddleMap[name] = r.binding;
      $("extra-signals").textContent = `${name} gravado (${r.binding.src})`;
    } catch (_) {
      $("extra-signals").textContent = `${name} não apareceu no Windows. No 8BitDo, mapeie M1/M2 no software da 8BitDo ou use o modo DirectInput (não Xbox).`;
    } finally {
      overlay.classList.add("hidden");
    }
  });

  ["left-stick", "right-stick", "curve"].forEach((id) => {
    $(id).addEventListener("change", () => {
      const map = { "left-stick": "leftStick", "right-stick": "rightStick", curve: "curve" };
      config.mapper[map[id]] = $(id).value;
      scheduleSave();
    });
  });
  $("sensitivity").addEventListener("input", () => {
    config.mapper.sensitivity = Number($("sensitivity").value);
    $("sensitivity-val").textContent = config.mapper.sensitivity;
    scheduleSave();
  });
  $("deadzone").addEventListener("input", () => {
    config.mapper.deadzone = Number($("deadzone").value) / 100;
    $("deadzone-val").textContent = config.mapper.deadzone.toFixed(2);
    scheduleSave();
  });
  $("invert-y").addEventListener("change", () => {
    config.mapper.invertY = $("invert-y").checked;
    scheduleSave();
  });

  $("bind-list").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-bind]");
    if (btn) openBind(btn.dataset.bind);
  });
  document.getElementById("gamepad").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-btn]");
    if (btn) openBind(btn.dataset.btn);
  });
  $("bind-kind").addEventListener("change", toggleBindFields);
  $("bind-cancel").addEventListener("click", () => $("bind-modal").classList.add("hidden"));
  $("bind-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const kind = $("bind-kind").value;
    const bind = { kind };
    if (kind === "mouse") bind.button = $("bind-mouse").value;
    if (kind === "key") bind.key = $("bind-key").value;
    if (kind === "sequence") bind.sequenceId = $("bind-seq").value;
    config.mapper.binds[bindTarget] = bind;
    $("bind-modal").classList.add("hidden");
    renderMapper();
    renderSequences();
    scheduleSave();
  });

  $("seq-select").addEventListener("change", () => {
    config.activeSequenceId = $("seq-select").value;
    renderSequences();
    scheduleSave();
  });
  $("seq-library").addEventListener("click", (e) => {
    const chip = e.target.closest("[data-seq]");
    if (!chip) return;
    config.activeSequenceId = chip.dataset.seq;
    renderSequences();
    scheduleSave();
  });
  $("seq-pad-bind").addEventListener("change", () => {
    const seqId = activeSequence().id;
    const btn = $("seq-pad-bind").value;
    Object.entries(config.mapper.binds).forEach(([name, bind]) => {
      if (bind && bind.kind === "sequence" && bind.sequenceId === seqId) {
        config.mapper.binds[name] = { kind: "none" };
      }
    });
    if (btn) config.mapper.binds[btn] = { kind: "sequence", sequenceId: seqId };
    renderMapper();
    renderSequences();
    scheduleSave();
  });
  $("seq-name").addEventListener("input", () => {
    activeSequence().name = $("seq-name").value;
    scheduleSave();
    const sel = $("seq-select");
    const opt = sel.selectedOptions[0];
    if (opt) opt.textContent = $("seq-name").value;
  });
  $("seq-start").addEventListener("input", () => {
    activeSequence().startDelayMs = Number($("seq-start").value) || 0;
    scheduleSave();
  });
  $("seq-repeat").addEventListener("input", () => {
    activeSequence().repeat = Math.max(1, Number($("seq-repeat").value) || 1);
    scheduleSave();
  });
  $("seq-new").addEventListener("click", () => {
    const n = config.sequences.length + 1;
    const seq = { id: uid(), name: `Sequência ${n}`, repeat: 1, startDelayMs: 0, steps: [newStep("mouse_move")] };
    config.sequences.push(seq);
    config.activeSequenceId = seq.id;
    renderSequences();
    scheduleSave();
  });
  $("seq-dup").addEventListener("click", () => {
    const copy = JSON.parse(JSON.stringify(activeSequence()));
    copy.id = uid();
    copy.name += " (cópia)";
    copy.steps.forEach((s) => { s.id = uid(); });
    config.sequences.push(copy);
    config.activeSequenceId = copy.id;
    renderSequences();
    scheduleSave();
  });
  $("seq-del").addEventListener("click", () => {
    if (config.sequences.length <= 1) return;
    const removed = config.activeSequenceId;
    config.sequences = config.sequences.filter((s) => s.id !== removed);
    Object.values(config.mapper.binds).forEach((bind) => {
      if (bind && bind.kind === "sequence" && bind.sequenceId === removed) {
        bind.kind = "none";
        delete bind.sequenceId;
      }
    });
    config.activeSequenceId = config.sequences[0].id;
    renderSequences();
    renderMapper();
    scheduleSave();
  });
  $("seq-play").addEventListener("click", async () => {
    await api("/api/config", config);
    await api("/api/sequence/play", { id: activeSequence().id });
  });
  $("seq-stop").addEventListener("click", () => api("/api/sequence/stop", {}));

  document.querySelector(".add-row").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-add]");
    if (!btn) return;
    activeSequence().steps.push(newStep(btn.dataset.add));
    renderSequences();
    scheduleSave();
  });

  $("steps").addEventListener("click", async (e) => {
    const stepEl = e.target.closest(".step");
    if (!stepEl) return;
    const seq = activeSequence();
    const idx = seq.steps.findIndex((s) => s.id === stepEl.dataset.id);
    const step = seq.steps[idx];
    const act = e.target.closest("[data-act]")?.dataset.act;
    if (act === "del") seq.steps.splice(idx, 1);
    if (act === "up" && idx > 0) [seq.steps[idx - 1], seq.steps[idx]] = [seq.steps[idx], seq.steps[idx - 1]];
    if (act === "down" && idx < seq.steps.length - 1) [seq.steps[idx + 1], seq.steps[idx]] = [seq.steps[idx], seq.steps[idx + 1]];
    if (act === "test") await api("/api/sequence/test-step", { step });
    if (act === "capture") await captureMouse(step);
    if (act) {
      renderSequences();
      scheduleSave();
    }
  });

  $("steps").addEventListener("change", (e) => {
    const stepEl = e.target.closest(".step");
    const key = e.target.dataset.k;
    if (!stepEl || !key) return;
    const step = activeSequence().steps.find((s) => s.id === stepEl.dataset.id);
    let value = e.target.value;
    if (e.target.type === "number") value = Number(value);
    step[key] = value;
    if (key === "type") {
      const next = newStep(value);
      next.id = step.id;
      Object.assign(step, next);
      renderSequences();
    }
    scheduleSave();
  });
}

async function poll() {
  try {
    state = await api("/api/state");
    renderHeader();
    const seq = $("view-seq");
    if (seq && !seq.classList.contains("hidden")) {
      document.querySelectorAll(".step").forEach((el, i) => {
        el.classList.toggle("active", !!(state.sequence.playing && state.sequence.index === i));
      });
    }
  } catch (_) { /* server still starting */ }
  setTimeout(poll, 80);
}

async function boot() {
  config = await api("/api/config");
  state = await api("/api/state");
  bindEvents();
  renderMapper();
  renderSequences();
  renderHeader();
  poll();
}

boot().catch((err) => {
  document.body.innerHTML = `<p style="padding:24px">Não foi possível abrir o PadDesk: ${err}</p>`;
});
