const state = {
  mode: "auto",
  latestBatchText: "",
  latestDownloadName: "translations_updated.txt",
  liveRunning: false,
};

const karenRegex = /[\u1000-\u109F]/;
const leadingKarenLineRegex = /^\s*[\u1000-\u109F]/m;

const els = {
  routeStatus: document.getElementById("routeStatus"),
  searchInput: document.getElementById("searchInput"),
  runLookup: document.getElementById("runLookup"),
  clearLookup: document.getElementById("clearLookup"),
  copyResult: document.getElementById("copyResult"),
  lookupResult: document.getElementById("lookupResult"),
  processResult: document.getElementById("processResult"),
  lookupDetails: document.getElementById("lookupDetails"),
  auditTrail: document.getElementById("auditTrail"),
  clearAudit: document.getElementById("clearAudit"),
  batchFile: document.getElementById("batchFile"),
  batchInput: document.getElementById("batchInput"),
  batchOutput: document.getElementById("batchOutput"),
  runBatch: document.getElementById("runBatch"),
  downloadBatch: document.getElementById("downloadBatch"),
  refreshAttempts: document.getElementById("refreshAttempts"),
  attemptSummary: document.getElementById("attemptSummary"),
  attemptList: document.getElementById("attemptList"),
  runLiveFile: document.getElementById("runLiveFile"),
  stopLiveFile: document.getElementById("stopLiveFile"),
  liveSourceFile: document.getElementById("liveSourceFile"),
  liveOutputFile: document.getElementById("liveOutputFile"),
  liveMessage: document.getElementById("liveMessage"),
  liveProgressBar: document.getElementById("liveProgressBar"),
  liveProgressText: document.getElementById("liveProgressText"),
  liveTrying: document.getElementById("liveTrying"),
  liveExpected: document.getElementById("liveExpected"),
  liveDictionary: document.getElementById("liveDictionary"),
  liveChosen: document.getElementById("liveChosen"),
  liveRows: document.getElementById("liveRows"),
  liveOutputTail: document.getElementById("liveOutputTail"),
};

function addDetails(container, title, payload, open = false) {
  const detail = document.createElement("details");
  detail.open = open;
  const summary = document.createElement("summary");
  summary.textContent = title;
  const pre = document.createElement("pre");
  pre.textContent = typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
  detail.append(summary, pre);
  container.append(detail);
}

function clearLookupDetails() {
  els.lookupDetails.innerHTML = "";
}

function updateRouteStatus() {
  const text = els.searchInput.value;
  if (state.mode === "en-to-ksw") {
    els.routeStatus.textContent = "Manual: English to Karen";
    return;
  }
  if (state.mode === "ksw-to-en") {
    els.routeStatus.textContent = "Manual: Karen to English";
    return;
  }
  if (leadingKarenLineRegex.test(text)) {
    els.routeStatus.textContent = "Auto: Karen line detected";
    return;
  }
  if (karenRegex.test(text)) {
    els.routeStatus.textContent = "Auto: Karen text detected";
    return;
  }
  if (/[A-Za-z]/.test(text)) {
    els.routeStatus.textContent = "Auto: English text detected";
    return;
  }
  els.routeStatus.textContent = "Auto route idle";
}

function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll(".mode-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === mode);
  });
  updateRouteStatus();
}

function formatDetails(details = {}) {
  const entries = Object.entries(details).filter(([, value]) => value !== undefined && value !== null && value !== "");
  if (!entries.length) return "";
  return JSON.stringify(Object.fromEntries(entries), null, 2);
}

function appendAudit(payload) {
  const row = document.createElement("div");
  row.className = "audit-row";

  const meta = document.createElement("div");
  meta.className = "audit-meta";

  const badge = document.createElement("span");
  badge.className = `badge ${payload.stage || "event"}`;
  badge.textContent = payload.stage || "event";

  const time = document.createElement("span");
  time.className = "audit-time";
  time.textContent = new Date(payload.time || Date.now()).toLocaleTimeString();

  meta.append(badge, time);

  const message = document.createElement("div");
  message.className = "audit-message";
  message.textContent = payload.message || "";

  row.append(meta, message);

  const detailText = formatDetails(payload.details);
  if (detailText) {
    const details = document.createElement("div");
    details.className = "audit-details";
    details.textContent = detailText;
    row.append(details);
  }

  els.auditTrail.append(row);
  while (els.auditTrail.children.length > 1000) {
    els.auditTrail.firstElementChild.remove();
  }
  els.auditTrail.scrollTop = els.auditTrail.scrollHeight;
}

function clearAudit() {
  els.auditTrail.innerHTML = "";
}

function renderLookupResult(result) {
  if (!result) return;
  clearLookupDetails();
  if (result.direction === "en-to-ksw") {
    const context = result.internet_context || {};
    const contextLines = [];
    if ((context.keywords || []).length) {
      contextLines.push(`internet keywords: ${context.keywords.join(", ")}`);
    }
    if ((context.results || []).length) {
      contextLines.push("internet context:");
      context.results.slice(0, 3).forEach((item) => {
        contextLines.push(`- ${item.title || ""} ${item.snippet || ""}`.trim());
      });
    }
    els.lookupResult.textContent = result.output || "";
    els.processResult.textContent = [
      `source: ${result.source || ""}`,
      `full description target: ${result.mini_lm?.full_description_goal || result.description || ""}`,
      `description: ${result.description || ""}`,
      `grammarized: ${result.mini_lm?.grammarized_english_goal || result.grammarized || ""}`,
      ...contextLines,
    ].join("\n");
    addDetails(els.lookupDetails, "Mini grammar model connector plan", result.mini_lm || {}, true);
    addDetails(els.lookupDetails, "Internet related words and snippets", context, true);
    addDetails(els.lookupDetails, "Per-word thoughts", result.word_thoughts || [], true);
    addDetails(els.lookupDetails, "Complete English→Karen result object", result, false);
    return;
  }

  els.lookupResult.textContent = result.output || "";
  els.processResult.textContent = [
    result.whole_match ? `whole match: ${result.whole_match.result} (${result.whole_match.source})` : "whole match: none",
    `syllables: ${(result.syllables || []).join(" | ")}`,
    `connectors: ${(result.connectors || []).map((item) => `${item.connector}=${item.meaning}`).join(" | ") || "none"}`,
    `breakdown: ${result.breakdown || ""}`,
    `candidate attempts shown: ${(result.parse_attempts || []).length}`,
  ].join("\n");
  addDetails(els.lookupDetails, "Karen syllables", result.syllables || [], true);
  addDetails(els.lookupDetails, "Connectors chosen", result.connectors || [], true);
  addDetails(els.lookupDetails, "Syllable combinations already tried", result.parse_attempts || [], true);
  addDetails(els.lookupDetails, "Complete Karen→English result object", result, false);
}

function handleComplete(payload) {
  if (payload.result?.processed_text !== undefined) {
    state.latestBatchText = payload.result.processed_text;
    state.latestDownloadName = payload.result.download_name || "translations_updated.txt";
    els.batchOutput.value = state.latestBatchText;
    els.downloadBatch.disabled = false;
    appendAudit({
      stage: "complete",
      message: `Batch ready: ${payload.result.changed_count} filled, ${payload.result.parsed_count} parsed.`,
      time: payload.time,
      details: { output_file: payload.result.output_file },
    });
    refreshAttempts();
    return;
  }

  renderLookupResult(payload.result);
  appendAudit({
    stage: "complete",
    message: "Lookup complete.",
    time: payload.time,
    details: { direction: payload.result?.direction, source: payload.result?.source },
  });
  refreshAttempts();
}

async function readSseStream(response) {
  if (!response.ok || !response.body) {
    throw new Error(`Request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";

    for (const event of events) {
      const line = event.split("\n").find((item) => item.startsWith("data:"));
      if (!line) continue;
      const payload = JSON.parse(line.slice(5).trim());
      if (payload.stage === "complete") {
        handleComplete(payload);
      } else if (payload.stage === "batch_row") {
        appendAudit(payload);
        refreshLiveState();
      } else {
        appendAudit(payload);
      }
    }
  }
}

async function runLookup() {
  const text = els.searchInput.value.trim();
  if (!text) return;
  els.runLookup.disabled = true;
  els.lookupResult.textContent = "";
  els.processResult.textContent = "";
  clearLookupDetails();
  appendAudit({ stage: "route", message: "Manual lookup requested.", time: new Date().toISOString(), details: { mode: state.mode } });

  try {
    const response = await fetch("/api/lookup-stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, mode: state.mode }),
    });
    await readSseStream(response);
  } catch (error) {
    appendAudit({ stage: "error", message: error.message, time: new Date().toISOString(), details: {} });
  } finally {
    els.runLookup.disabled = false;
  }
}

async function runBatch() {
  const form = new FormData();
  const file = els.batchFile.files[0];
  if (file) {
    form.append("file", file);
  } else {
    form.append("content", els.batchInput.value);
  }
  form.append("mode", state.mode);

  els.runBatch.disabled = true;
  els.downloadBatch.disabled = true;
  els.batchOutput.value = "";
  appendAudit({ stage: "batch_line", message: "Batch processing requested.", time: new Date().toISOString(), details: { has_file: Boolean(file) } });

  try {
    const response = await fetch("/api/batch-stream", {
      method: "POST",
      body: form,
    });
    await readSseStream(response);
  } catch (error) {
    appendAudit({ stage: "error", message: error.message, time: new Date().toISOString(), details: {} });
  } finally {
    els.runBatch.disabled = false;
  }
}

async function refreshAttempts() {
  try {
    const response = await fetch("/api/attempts?limit=80");
    const payload = await response.json();
    els.attemptSummary.textContent = `${payload.total} attempts stored. Showing ${payload.attempts.length}.`;
    els.attemptList.innerHTML = "";
    payload.attempts.slice().reverse().forEach((attempt) => {
      const item = document.createElement("details");
      item.className = "attempt-item";
      const summary = document.createElement("summary");
      summary.textContent = `${attempt.stage} / ${attempt.source} / ${attempt.status}: ${shorten(attempt.query, 70)}`;
      const pre = document.createElement("pre");
      pre.textContent = JSON.stringify(attempt, null, 2);
      item.append(summary, pre);
      els.attemptList.append(item);
    });
  } catch (error) {
    els.attemptSummary.textContent = error.message;
  }
}

function formatDictionaryList(dictionary = []) {
  if (!dictionary.length) return "No dictionary result for this line yet.";
  return dictionary
    .map((item) => {
      const results = (item.results || []).length ? item.results.join(" | ") : "empty";
      return `${item.source}: ${item.status || ""}\nquery: ${item.query || ""}\nresults: ${results}`;
    })
    .join("\n\n");
}

function formatWordThoughts(thoughts = []) {
  if (!thoughts.length) return "";
  return thoughts
    .map((thought) => {
      return `${thought.word}: ${thought.decision || ""}\nknown: ${thought.known_karen || "none"}\ndictionary: ${thought.dictionary_result || "none"} ${thought.source ? `(${thought.source})` : ""}`;
    })
    .join("\n\n");
}

function shorten(value = "", limit = 180) {
  const text = String(value || "");
  return text.length > limit ? `${text.slice(0, limit)}...` : text;
}

function renderLiveRows(rows = []) {
  els.liveRows.innerHTML = "";
  rows.slice().reverse().slice(0, 120).forEach((row) => {
    const tr = document.createElement("tr");
    const cells = [
      row.line_no,
      row.trying,
      row.expected_target,
      row.direction,
      row.lookup_status,
      formatDictionaryList(row.dictionary),
      row.chosen || row.breakdown,
    ];
    cells.forEach((value) => {
      const td = document.createElement("td");
      td.textContent = shorten(value, 260);
      tr.append(td);
    });
    els.liveRows.append(tr);
  });
}

function renderLiveState(payload) {
  if (!payload) return;
  const total = payload.total_lines || 0;
  const processed = payload.processed_lines || 0;
  const percent = total ? Math.min(100, Math.round((processed / total) * 100)) : 0;
  const current = payload.current || {};

  state.liveRunning = Boolean(payload.running);
  els.runLiveFile.disabled = state.liveRunning;
  els.stopLiveFile.disabled = !state.liveRunning;
  els.liveSourceFile.textContent = payload.source_file || "";
  els.liveOutputFile.textContent = payload.output_file || "";
  els.liveMessage.textContent = payload.message || (state.liveRunning ? "Running." : "Idle.");
  els.liveProgressBar.style.width = `${percent}%`;
  els.liveProgressText.textContent = `${processed} / ${total} lines · ${percent}% · ${payload.changed_count || 0} filled · ${payload.parsed_count || 0} parsed`;
  els.liveTrying.textContent = current.trying || "";
  els.liveExpected.textContent = current.expected_target || "";
  els.liveDictionary.textContent = formatDictionaryList(current.dictionary || []);
  els.liveChosen.textContent = [current.chosen || "", current.breakdown || "", formatWordThoughts(current.word_thoughts || [])].filter(Boolean).join("\n\n");
  els.liveOutputTail.value = payload.output_tail || "";
  renderLiveRows(payload.rows || []);
}

async function refreshLiveState() {
  try {
    const response = await fetch("/api/live-state", { cache: "no-store" });
    renderLiveState(await response.json());
  } catch (error) {
    els.liveMessage.textContent = error.message;
  }
}

async function runLiveFile() {
  els.runLiveFile.disabled = true;
  appendAudit({ stage: "batch_line", message: "Full translations_website.txt run requested.", time: new Date().toISOString(), details: { mode: state.mode } });
  try {
    const response = await fetch("/api/live-file-stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: state.mode }),
    });
    await readSseStream(response);
  } catch (error) {
    appendAudit({ stage: "error", message: error.message, time: new Date().toISOString(), details: {} });
  } finally {
    await refreshLiveState();
    els.runLiveFile.disabled = state.liveRunning;
  }
}

async function stopLiveFile() {
  try {
    await fetch("/api/live-stop", { method: "POST" });
    await refreshLiveState();
  } catch (error) {
    appendAudit({ stage: "error", message: error.message, time: new Date().toISOString(), details: {} });
  }
}

function downloadBatch() {
  if (!state.latestBatchText) return;
  const blob = new Blob([state.latestBatchText], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = state.latestDownloadName;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

document.querySelectorAll(".mode-button").forEach((button) => {
  button.addEventListener("click", () => setMode(button.dataset.mode));
});

document.querySelectorAll("[data-key]").forEach((button) => {
  button.addEventListener("click", () => {
    const start = els.searchInput.selectionStart;
    const end = els.searchInput.selectionEnd;
    const value = els.searchInput.value;
    const key = button.dataset.key;
    els.searchInput.value = `${value.slice(0, start)}${key}${value.slice(end)}`;
    els.searchInput.focus();
    els.searchInput.selectionStart = start + key.length;
    els.searchInput.selectionEnd = start + key.length;
    updateRouteStatus();
  });
});

els.searchInput.addEventListener("input", updateRouteStatus);
els.runLookup.addEventListener("click", runLookup);
els.clearLookup.addEventListener("click", () => {
  els.searchInput.value = "";
  els.lookupResult.textContent = "";
  els.processResult.textContent = "";
  clearLookupDetails();
  updateRouteStatus();
});
els.copyResult.addEventListener("click", () => navigator.clipboard.writeText(els.lookupResult.textContent || ""));
els.clearAudit.addEventListener("click", clearAudit);
els.runBatch.addEventListener("click", runBatch);
els.downloadBatch.addEventListener("click", downloadBatch);
els.refreshAttempts.addEventListener("click", refreshAttempts);
els.runLiveFile.addEventListener("click", runLiveFile);
els.stopLiveFile.addEventListener("click", stopLiveFile);
els.batchFile.addEventListener("change", async () => {
  const file = els.batchFile.files[0];
  if (!file) return;
  els.batchInput.value = await file.text();
});

updateRouteStatus();
refreshAttempts();
refreshLiveState();
window.setInterval(refreshLiveState, 500);
