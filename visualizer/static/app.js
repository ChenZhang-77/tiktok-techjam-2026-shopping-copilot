const experimentSelect = document.getElementById("experimentSelect");
const sessionSelect = document.getElementById("sessionSelect");
const overallMetrics = document.getElementById("overallMetrics");
const scenarioMetrics = document.getElementById("scenarioMetrics");
const sessionMeta = document.getElementById("sessionMeta");
const sessionOutcome = document.getElementById("sessionOutcome");
const chat = document.getElementById("chat");
const statusText = document.getElementById("statusText");
const turnProgress = document.getElementById("turnProgress");
const intervalInput = document.getElementById("intervalInput");
const startButton = document.getElementById("startButton");
const stopButton = document.getElementById("stopButton");
let activeEventSource = null;
let runStartedAt = 0;

function selectedExperiment() {
  return experimentSelect.value || "current";
}

function experimentQuery() {
  return `experiment=${encodeURIComponent(selectedExperiment())}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function compactList(values, limit = 2) {
  if (!Array.isArray(values) || values.length === 0) return "";
  return values.slice(0, limit).map((item) => String(item)).join(" / ");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("\n", "&#10;");
}

function renderMeta(payload) {
  sessionMeta.innerHTML = `
    <dt>Index</dt><dd>${escapeHtml(payload.session_index)}</dd>
    <dt>Sample</dt><dd>${escapeHtml(payload.sample_id)}</dd>
    <dt>Scenario</dt><dd>${escapeHtml(payload.scenario_type)}</dd>
    <dt>Session</dt><dd>${escapeHtml(payload.session_id)}</dd>
    <dt>Max turns</dt><dd>${escapeHtml(payload.max_turns)}</dd>
  `;

}

function fmt(value, digits = 4) {
  if (value === null || value === undefined) return "none";
  if (typeof value === "number") return value.toFixed(digits);
  return String(value);
}

function renderOverall(payload) {
  const evaluation = payload.evaluation || {};
  overallMetrics.innerHTML = `
    <dt>Source</dt><dd>${escapeHtml(payload.source)}</dd>
    <dt>Evidence</dt><dd>${escapeHtml(payload.evidence_status)}</dd>
    <dt>Mode</dt><dd>${escapeHtml(evaluation.mode || "historical / unspecified")}</dd>
    <dt>Split</dt><dd>${escapeHtml(evaluation.split || "unspecified")}</dd>
    <dt>Samples</dt><dd>${escapeHtml(payload.sample_count)}</dd>
    <dt>HitRate@10</dt><dd>${escapeHtml(fmt(payload.hit_rate_at_10, 6))}</dd>
    <dt>MRR</dt><dd>${escapeHtml(fmt(payload.mrr, 6))}</dd>
    <dt>MTTC</dt><dd>${escapeHtml(fmt(payload.mttc, 4))}</dd>
    <dt>Efficiency</dt><dd>${escapeHtml(fmt(payload.efficiency, 6))}</dd>
    <dt>TechnicalScore</dt><dd>${escapeHtml(fmt(payload.technical_score, 6))}</dd>
  `;
  const scenarios = payload.scenario_metrics || {};
  scenarioMetrics.innerHTML = Object.entries(scenarios).map(([name, metrics]) => `
    <div class="scenario-row">
      <div class="scenario-name">${escapeHtml(name)}</div>
      <div>Hit ${escapeHtml(fmt(metrics.hit_rate_at_10, 3))}</div>
      <div>MRR ${escapeHtml(fmt(metrics.mrr, 3))}</div>
      <div>MTTC ${escapeHtml(fmt(metrics.mttc, 2))}</div>
    </div>
  `).join("");
}

function renderRecommendations(recommendations, turnPayload = {}) {
  if (!recommendations || recommendations.length === 0) {
    return '<div class="mini-recs empty">No valid recommendations</div>';
  }
  return `
    <div class="mini-recs" aria-label="Top 10 recommendations">
      ${recommendations.map((item) => {
        const product = item.product || {};
        const categories = compactList(product.categories, 2);
        const price = product.price === null || product.price === undefined ? "" : `$${product.price}`;
        const features = compactList(product.features, 2);
        const tip = [
          `Title: ${product.title || item.parent_asin}`,
          `ASIN: ${item.parent_asin}`,
          categories ? `Category: ${categories}` : "",
          price ? `Price: ${price}` : "",
          product.store ? `Store: ${product.store}` : "",
          product.average_rating ? `Rating: ${product.average_rating} (${product.rating_number || 0})` : "",
          features ? `Features: ${features}` : "",
        ].filter(Boolean).join("\n");
        const name = product.title || item.parent_asin;
        const isHit = turnPayload.hit === true && item.is_target && item.rank !== undefined;
        return `
          <div class="mini-rec ${isHit ? "target" : ""}" data-tip="${escapeAttr(tip)}">
            <span class="mini-rank">#${escapeHtml(item.rank)}</span>
            <span class="mini-title">${escapeHtml(name)}</span>
            ${isHit ? '<span class="target-dot">Evaluator HIT</span>' : ""}
          </div>
        `;
      }).join("")}
    </div>
  `;
}

function bubble(role, html, meta = "") {
  const node = document.createElement("div");
  node.className = `message-row ${role}`;
  node.innerHTML = `
    <div class="avatar">${role === "customer" ? "C" : "A"}</div>
    <div class="message-stack">
      ${meta ? `<div class="message-meta">${escapeHtml(meta)}</div>` : ""}
      <div class="message-bubble">${html}</div>
    </div>
  `;
  chat.appendChild(node);
}

function appendCustomer(message, meta = "") {
  if (!message) return;
  bubble("customer", escapeHtml(message), meta);
}

function appendAgent(payload) {
  const ask = payload.ask_attribute ?? "null";
  const diagnostics = payload.agent_diagnostics || {};
  const delivery = diagnostics.delivery || {};
  const html = `
    <div class="agent-text">${escapeHtml(payload.agent_message)}</div>
    <div class="agent-toolbar">
      <span>ask_attribute: <strong>${escapeHtml(ask)}</strong></span>
      <span>Mode: ${escapeHtml(delivery.requested_mode || "unknown")} · ${escapeHtml(delivery.turn_status || "unknown")}</span>
    </div>
    <details><summary>Agent-only diagnostics and usage</summary><pre>${escapeHtml(JSON.stringify({diagnostics, usage: payload.usage || {}}, null, 2))}</pre></details>
    ${payload.error ? `<div class="error">${escapeHtml(payload.error)}</div>` : ""}
    ${renderRecommendations(payload.recommendations, payload)}
  `;
  bubble("agent", html, `Turn ${payload.turn}`);
}

function appendSystem(text) {
  const node = document.createElement("div");
  node.className = "system-line";
  node.textContent = text;
  chat.appendChild(node);
}

function renderFinal(payload) {
  sessionOutcome.className = `session-outcome ${payload.hit ? "hit" : "miss"}`;
  sessionOutcome.innerHTML = payload.hit
    ? `<strong>Evaluator hit</strong><br>First hit: turn ${escapeHtml(payload.first_hit_turn)}<br>Rank: ${escapeHtml(payload.best_rank)}`
    : "Evaluator: no hit within 10 turns.";
  appendSystem("Offline simulation complete. Aggregate metrics are a separate recorded evaluation.");
}

function renderTraceStart(payload) {
  renderMeta(payload);
  appendSystem("Live offline simulation · no external LLM calls. Hit annotations are evaluator-only.");
  appendCustomer(payload.initial_user_message, "Simulated initial request");
}

function renderTraceTurn(payload) {
  appendAgent(payload);
}

async function loadSessions() {
  const response = await fetch(`/api/sessions?${experimentQuery()}`);
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || "Failed to load sessions");
  }
  const sessions = await response.json();
  sessionSelect.innerHTML = sessions.map((session) => {
    const label = `#${session.index} · ${session.scenario_type} · ${session.category}`;
    return `<option value="${session.index}">${escapeHtml(label)}</option>`;
  }).join("");
}

async function loadExperiments() {
  const response = await fetch("/api/experiments");
  const experiments = await response.json();
  const params = new URLSearchParams(window.location.search);
  const requested = params.get("experiment") || "current";
  experimentSelect.innerHTML = experiments.map((experiment) => {
    const status = experiment.can_rerun ? " · offline rerun" : " · historical metrics only";
    const label = `${experiment.label}${status}`;
    return `<option value="${escapeAttr(experiment.id)}">${escapeHtml(label)}</option>`;
  }).join("");
  const ids = new Set(experiments.map((experiment) => experiment.id));
  experimentSelect.value = ids.has(requested) ? requested : "current";
}

async function loadOverall() {
  const response = await fetch(`/api/overall?${experimentQuery()}`);
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || "Failed to load overall metrics");
  }
  const payload = await response.json();
  renderOverall(payload);
}

function clearTrace() {
  if (activeEventSource) {
    activeEventSource.close();
    activeEventSource = null;
  }
  chat.innerHTML = "";
  sessionMeta.innerHTML = "";
  sessionOutcome.className = "session-outcome";
  sessionOutcome.textContent = "Waiting for dialogue.";
  statusText.textContent = selectedExperiment() === "current" ? "Ready · offline simulation" : "Historical metrics only";
  turnProgress.textContent = "Ready";
  startButton.disabled = selectedExperiment() !== "current";
  stopButton.disabled = true;
}

function stopTrace(status = "Stopped") {
  if (activeEventSource) {
    activeEventSource.close();
    activeEventSource = null;
  }
  sessionSelect.disabled = false;
  experimentSelect.disabled = false;
  startButton.disabled = selectedExperiment() !== "current";
  stopButton.disabled = true;
  statusText.textContent = status;
  turnProgress.textContent = status;
}

async function startSelectedTrace() {
  if (selectedExperiment() !== "current") return;
  if (activeEventSource) stopTrace("Stopped");
  chat.innerHTML = "";
  sessionMeta.innerHTML = "";
  sessionOutcome.className = "session-outcome";
  sessionOutcome.textContent = "Running.";
  statusText.textContent = "Starting";
  turnProgress.textContent = "Starting";
  runStartedAt = performance.now();
  sessionSelect.disabled = true;
  experimentSelect.disabled = true;
  startButton.disabled = true;
  stopButton.disabled = false;

  const index = sessionSelect.value || "0";
  const intervalSeconds = Number(intervalInput.value);
  if (!Number.isFinite(intervalSeconds) || intervalSeconds < 0 || intervalSeconds > 60) {
    throw new Error("Interval must be a number from 0 to 60 seconds.");
  }
  const delay = Math.round(intervalSeconds * 1000);
  const source = new EventSource(
    `/events?index=${encodeURIComponent(index)}&${experimentQuery()}&delay_ms=${encodeURIComponent(delay)}`
  );
  activeEventSource = source;
  let finished = false;
  source.addEventListener("start", (event) => {
    renderTraceStart(JSON.parse(event.data));
    statusText.textContent = "Running";
  });
  source.addEventListener("turn", (event) => {
    const payload = JSON.parse(event.data);
    renderTraceTurn(payload);
    const elapsed = ((performance.now() - runStartedAt) / 1000).toFixed(1);
    turnProgress.textContent = `Turn ${payload.turn}/10 · ${elapsed}s`;
  });
  source.addEventListener("customer", (event) => {
    const payload = JSON.parse(event.data);
    appendCustomer(payload.message, payload.label || "Customer follow-up");
  });
  source.addEventListener("done", (event) => {
    finished = true;
    renderFinal(JSON.parse(event.data));
    statusText.textContent = "Loaded";
    turnProgress.textContent = "";
    sessionSelect.disabled = false;
    experimentSelect.disabled = false;
    startButton.disabled = selectedExperiment() !== "current";
    stopButton.disabled = true;
    source.close();
    if (activeEventSource === source) activeEventSource = null;
    requestAnimationFrame(() => {
      chat.scrollTop = 0;
    });
  });
  source.addEventListener("error", (event) => {
    if (finished) return;
    let message = "Failed to stream session trace";
    if (event.data) {
      try { message = JSON.parse(event.data).message || message; } catch (_) {}
    }
    statusText.textContent = message;
    sessionSelect.disabled = false;
    experimentSelect.disabled = false;
    startButton.disabled = selectedExperiment() !== "current";
    stopButton.disabled = true;
    source.close();
    if (activeEventSource === source) activeEventSource = null;
  });
}

experimentSelect.addEventListener("change", () => {
  stopTrace("Ready");
  const params = new URLSearchParams(window.location.search);
  if (selectedExperiment() === "current") {
    params.delete("experiment");
  } else {
    params.set("experiment", selectedExperiment());
  }
  const query = params.toString();
  window.history.replaceState(null, "", query ? `?${query}` : window.location.pathname);
  Promise.all([loadSessions(), loadOverall()])
    .then(() => clearTrace())
    .catch((error) => {
    statusText.textContent = error.message;
    sessionSelect.disabled = false;
  });
});

sessionSelect.addEventListener("change", () => {
  clearTrace();
});

startButton.addEventListener("click", () => {
  startSelectedTrace().catch((error) => {
    statusText.textContent = error.message;
    stopTrace("Error");
  });
});

stopButton.addEventListener("click", () => stopTrace());

loadExperiments()
  .then(() => Promise.all([loadSessions(), loadOverall()]))
  .then(() => clearTrace())
  .catch((error) => {
  statusText.textContent = `Failed to load sessions: ${error.message}`;
});
