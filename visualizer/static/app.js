const sessionSelect = document.getElementById("sessionSelect");
const delaySelect = document.getElementById("delaySelect");
const runButton = document.getElementById("runButton");
const stopButton = document.getElementById("stopButton");
const sessionMeta = document.getElementById("sessionMeta");
const targetBox = document.getElementById("targetBox");
const finalBox = document.getElementById("finalBox");
const turns = document.getElementById("turns");
const statusText = document.getElementById("statusText");

let source = null;

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

function setRunning(running) {
  runButton.disabled = running;
  stopButton.disabled = !running;
  sessionSelect.disabled = running;
  delaySelect.disabled = running;
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

function renderRecommendations(recommendations) {
  if (!recommendations || recommendations.length === 0) {
    return '<div class="muted">No valid recommendations returned.</div>';
  }
  return `
    <div class="rec-list">
      ${recommendations.map((item) => {
        const product = item.product || {};
        const categories = compactList(product.categories, 2);
        const price = product.price === null || product.price === undefined ? "" : `$${product.price}`;
        const meta = [item.parent_asin, price, categories].filter(Boolean).join(" · ");
        return `
          <div class="rec ${item.is_target ? "target" : ""}">
            <div class="rank">#${escapeHtml(item.rank)}</div>
            <div>
              <div class="rec-title">${escapeHtml(product.title || item.parent_asin)}</div>
              <div class="rec-meta">${escapeHtml(meta)}${item.is_target ? " · TARGET" : ""}</div>
            </div>
          </div>
        `;
      }).join("")}
    </div>
  `;
}

function appendTurn(payload) {
  const node = document.createElement("article");
  node.className = "turn";
  node.innerHTML = `
    <div class="turn-head">
      <div class="turn-title">Turn ${escapeHtml(payload.turn)}</div>
      <div class="badge ${payload.hit ? "hit" : "miss"}">
        ${payload.hit ? `Hit at rank ${escapeHtml(payload.target_rank)}` : "No hit"}
      </div>
    </div>
    <div class="turn-body">
      <div class="dialogue">
        <div class="speaker">
          <strong>Customer</strong>
          <div class="bubble">${escapeHtml(payload.user_message)}</div>
        </div>
        <div class="speaker">
          <strong>Agent</strong>
          <div class="bubble">${escapeHtml(payload.agent_message)}</div>
        </div>
        <div class="ask">ask_attribute: <strong>${escapeHtml(payload.ask_attribute ?? "null")}</strong></div>
        ${payload.error ? `<div class="error">${escapeHtml(payload.error)}</div>` : ""}
      </div>
      <div class="recs">
        ${renderRecommendations(payload.recommendations)}
      </div>
    </div>
  `;
  turns.appendChild(node);
  node.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderFinal(payload) {
  finalBox.innerHTML = `
    <div><strong>${payload.hit ? "Hit" : "Miss"}</strong></div>
    <div>First hit turn: ${escapeHtml(payload.first_hit_turn ?? "none")}</div>
    <div>Best rank: ${escapeHtml(payload.best_rank ?? "none")}</div>
    <div>Reciprocal rank: ${escapeHtml(Number(payload.reciprocal_rank || 0).toFixed(4))}</div>
  `;
}

async function loadSessions() {
  const response = await fetch("/api/sessions");
  const sessions = await response.json();
  sessionSelect.innerHTML = sessions.map((session) => {
    const label = `#${session.index} · ${session.scenario_type} · ${session.category}`;
    return `<option value="${session.index}">${escapeHtml(label)}</option>`;
  }).join("");
}

function stopRun() {
  if (source) {
    source.close();
    source = null;
  }
  setRunning(false);
  statusText.textContent = "Stopped";
}

function runSession() {
  stopRun();
  turns.innerHTML = "";
  sessionMeta.innerHTML = "";
  targetBox.textContent = "Waiting for session metadata.";
  finalBox.textContent = "Running.";
  statusText.textContent = "Connecting";
  setRunning(true);

  const index = sessionSelect.value || "0";
  const delay = delaySelect.value || "700";
  source = new EventSource(`/events?index=${encodeURIComponent(index)}&delay_ms=${encodeURIComponent(delay)}`);

  source.addEventListener("start", (event) => {
    const payload = JSON.parse(event.data);
    renderMeta(payload);
    statusText.textContent = "Running";
  });

  source.addEventListener("turn", (event) => {
    const payload = JSON.parse(event.data);
    appendTurn(payload);
  });

  source.addEventListener("done", (event) => {
    const payload = JSON.parse(event.data);
    renderFinal(payload);
    statusText.textContent = "Done";
    setRunning(false);
    source.close();
    source = null;
  });

  source.addEventListener("error", () => {
    if (source) {
      statusText.textContent = "Connection closed";
      setRunning(false);
      source.close();
      source = null;
    }
  });
}

runButton.addEventListener("click", runSession);
stopButton.addEventListener("click", stopRun);

loadSessions().catch((error) => {
  statusText.textContent = `Failed to load sessions: ${error.message}`;
});
