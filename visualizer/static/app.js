const experimentSelect = document.getElementById("experimentSelect");
const sessionSelect = document.getElementById("sessionSelect");
const overallMetrics = document.getElementById("overallMetrics");
const scenarioMetrics = document.getElementById("scenarioMetrics");
const sessionMeta = document.getElementById("sessionMeta");
const targetBox = document.getElementById("targetBox");
const finalBox = document.getElementById("finalBox");
const chat = document.getElementById("chat");
const statusText = document.getElementById("statusText");

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
  return escapeHtml(value).replaceAll("\n", " ");
}

function renderMeta(payload) {
  sessionMeta.innerHTML = `
    <dt>Index</dt><dd>${escapeHtml(payload.session_index)}</dd>
    <dt>Sample</dt><dd>${escapeHtml(payload.sample_id)}</dd>
    <dt>Scenario</dt><dd>${escapeHtml(payload.scenario_type)}</dd>
    <dt>Session</dt><dd>${escapeHtml(payload.session_id)}</dd>
    <dt>Max turns</dt><dd>${escapeHtml(payload.max_turns)}</dd>
  `;

  const product = payload.target_product || {};
  const categories = compactList(product.categories, 3);
  const features = compactList(product.features, 3);
  targetBox.innerHTML = `
    <div class="target-title">${escapeHtml(product.title || payload.target)}</div>
    <div class="muted">${escapeHtml(payload.target)}</div>
    <div>${categories ? escapeHtml(categories) : "No category"}</div>
    <div class="muted">${features ? escapeHtml(features) : ""}</div>
  `;
}

function fmt(value, digits = 4) {
  if (value === null || value === undefined) return "none";
  if (typeof value === "number") return value.toFixed(digits);
  return String(value);
}

function renderOverall(payload) {
  overallMetrics.innerHTML = `
    <dt>Source</dt><dd>${escapeHtml(payload.source)}</dd>
    <dt>Samples</dt><dd>${escapeHtml(payload.sample_count)}</dd>
    <dt>HitRate@10</dt><dd>${escapeHtml(fmt(payload.hit_rate_at_10, 6))}</dd>
    <dt>MRR</dt><dd>${escapeHtml(fmt(payload.mrr, 6))}</dd>
    <dt>MTTC</dt><dd>${escapeHtml(fmt(payload.mttc, 4))}</dd>
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

function renderRecommendations(recommendations) {
  if (!recommendations || recommendations.length === 0) {
    return '<div class="mini-recs empty">No valid recommendations</div>';
  }
  return `
    <div class="mini-recs" aria-label="Top 10 recommendations">
      ${recommendations.map((item) => {
        const product = item.product || {};
        const categories = compactList(product.categories, 3);
        const price = product.price === null || product.price === undefined ? "" : `$${product.price}`;
        const features = compactList(product.features, 3);
        const tip = [
          product.title || item.parent_asin,
          item.parent_asin,
          price,
          categories,
          features,
          product.store ? `Store: ${product.store}` : "",
          product.average_rating ? `Rating: ${product.average_rating} (${product.rating_number || 0})` : "",
        ].filter(Boolean).join("\n");
        const name = product.title || item.parent_asin;
        return `
          <div class="mini-rec ${item.is_target ? "target" : ""}" data-tip="${escapeAttr(tip)}">
            <span class="mini-rank">#${escapeHtml(item.rank)}</span>
            <span class="mini-title">${escapeHtml(name)}</span>
            ${item.is_target ? '<span class="target-dot">TARGET</span>' : ""}
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
  const status = payload.hit ? `Hit at rank ${payload.target_rank}` : "No hit";
  const html = `
    <div class="agent-text">${escapeHtml(payload.agent_message)}</div>
    <div class="agent-toolbar">
      <span>ask_attribute: <strong>${escapeHtml(ask)}</strong></span>
      <span class="${payload.hit ? "hit-text" : "muted"}">${escapeHtml(status)}</span>
    </div>
    ${payload.error ? `<div class="error">${escapeHtml(payload.error)}</div>` : ""}
    ${renderRecommendations(payload.recommendations)}
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
  finalBox.innerHTML = `
    <div><strong>${payload.hit ? "Hit" : "Miss"}</strong></div>
    <div>First hit turn: ${escapeHtml(payload.first_hit_turn ?? "none")}</div>
    <div>Best rank: ${escapeHtml(payload.best_rank ?? "none")}</div>
    <div>Reciprocal rank: ${escapeHtml(Number(payload.reciprocal_rank || 0).toFixed(4))}</div>
  `;
  appendSystem(payload.hit
    ? `Session stopped after finding the target at turn ${payload.first_hit_turn}, rank ${payload.best_rank}.`
    : "Session reached turn 10 without finding the target.");
}

function renderTraceStart(payload) {
  renderMeta(payload);
  appendCustomer(payload.initial_user_message, "Initial request");
}

function renderTraceTurn(payload) {
  appendAgent(payload);
  if (payload.next_user_message) {
    appendCustomer(payload.next_user_message, "Customer follow-up");
  }
}

async function loadSessions() {
  const response = await fetch("/api/sessions");
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
    const status = experiment.has_results ? "" : " · no local result";
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

async function loadSelectedTrace() {
  chat.innerHTML = "";
  sessionMeta.innerHTML = "";
  targetBox.textContent = "Waiting for session metadata.";
  finalBox.textContent = "Loading.";
  statusText.textContent = "Loading";
  sessionSelect.disabled = true;

  const index = sessionSelect.value || "0";
  const response = await fetch(`/api/session_trace?index=${encodeURIComponent(index)}&${experimentQuery()}`);
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || "Failed to load session trace");
  }
  const payload = await response.json();
  renderTraceStart(payload.start);
  payload.turns.forEach(renderTraceTurn);
  renderFinal(payload.final);
  requestAnimationFrame(() => {
    chat.scrollTop = 0;
  });
  statusText.textContent = "Loaded";
  sessionSelect.disabled = false;
}

experimentSelect.addEventListener("change", () => {
  const params = new URLSearchParams(window.location.search);
  if (selectedExperiment() === "current") {
    params.delete("experiment");
  } else {
    params.set("experiment", selectedExperiment());
  }
  const query = params.toString();
  window.history.replaceState(null, "", query ? `?${query}` : window.location.pathname);
  Promise.all([loadOverall(), loadSelectedTrace()]).catch((error) => {
    statusText.textContent = error.message;
    sessionSelect.disabled = false;
  });
});

sessionSelect.addEventListener("change", () => {
  loadSelectedTrace().catch((error) => {
    statusText.textContent = error.message;
    sessionSelect.disabled = false;
  });
});

Promise.all([loadExperiments(), loadSessions()])
  .then(() => loadOverall())
  .then(() => loadSelectedTrace())
  .catch((error) => {
  statusText.textContent = `Failed to load sessions: ${error.message}`;
});
