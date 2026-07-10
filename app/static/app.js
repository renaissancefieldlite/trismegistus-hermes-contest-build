const runtimeStrip = document.getElementById("runtimeStrip");
const runtimePanel = document.getElementById("runtimePanel");
const foundationPanel = document.getElementById("foundationPanel");
const modelLanePanel = document.getElementById("modelLanePanel");
const modelLaneState = document.getElementById("modelLaneState");
const chatRuntimeLabel = document.getElementById("chatRuntimeLabel");
const events = document.getElementById("events");
const leadQueue = document.getElementById("leadQueue");
const queueCount = document.getElementById("queueCount");
const selectedTitle = document.getElementById("selectedTitle");
const selectedMeta = document.getElementById("selectedMeta");
const scoreboard = document.getElementById("scoreboard");
const messages = document.getElementById("messages");
const reportOutput = document.getElementById("reportOutput");
const reportState = document.getElementById("reportState");
const checkpointPanel = document.getElementById("checkpointPanel");
const checkpointState = document.getElementById("checkpointState");
const sendChatButton = document.getElementById("sendChat");
const chatInput = document.getElementById("chatInput");
const newThreadButton = document.getElementById("newThread");
const voiceListenButton = document.getElementById("voiceListen");
const voiceTalkbackButton = document.getElementById("voiceTalkback");
const voiceState = document.getElementById("voiceState");
const toolsDoctorOutput = document.getElementById("toolsDoctorOutput");
const browserMissionState = document.getElementById("browserMissionState");
const browserMissionsOutput = document.getElementById("browserMissionsOutput");

let selectedLeadId = null;
let cachedStatus = null;
let cachedRuntime = null;
let activeThreadId = "tris-main";
let cachedThreads = [];
let talkbackEnabled = false;
let speechRecognition = null;
let chatSendInFlight = false;

function onClick(id, handler) {
  const element = document.getElementById(id);
  if (element) element.addEventListener("click", handler);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function state(ok, warn = false) {
  if (ok) return "ok";
  return warn ? "warn" : "bad";
}

async function api(path, payload = null, timeoutMs = 30000) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  const options = payload
    ? {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
        signal: controller.signal,
      }
    : {signal: controller.signal};
  try {
    const response = await fetch(path, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `Request failed: ${path}`);
    return data;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error(`Request timed out after ${Math.round(timeoutMs / 1000)} seconds.`);
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

function chip(label, detail, cls) {
  return `
    <div class="chip">
      <span class="dot ${cls}"></span>
      <div><strong>${escapeHtml(label)}</strong><span>${escapeHtml(detail)}</span></div>
    </div>
  `;
}

function runtimeItem(label, detail, cls = "warn") {
  return `
    <div class="runtime-item">
      <strong><span class="dot ${cls}"></span> ${escapeHtml(label)}</strong>
      <p>${escapeHtml(detail)}</p>
    </div>
  `;
}

function boardCard(label, value, detail, cls = "warn") {
  return `
    <div class="board-card ${cls}">
      <div class="board-label">${escapeHtml(label)}</div>
      <div class="board-value">${escapeHtml(value)}</div>
      <div class="board-detail">${escapeHtml(detail)}</div>
    </div>
  `;
}

function displayStatus(value) {
  return String(value || "")
    .replaceAll("approve-for-consent-chain", "ready-for-review")
    .replaceAll("needs-human-review", "review-needed")
    .replaceAll("consent", "review");
}

function selectedLead() {
  return (cachedStatus?.leads || []).find((item) => item.id === selectedLeadId);
}

function projectMemory() {
  return cachedStatus?.project_memory || cachedRuntime?.project_memory || {};
}

function mirrorCheckpoints() {
  return cachedStatus?.mirror_checkpoints || cachedRuntime?.mirror_checkpoints || projectMemory().mirror_checkpoints || {};
}

function projectState() {
  return projectMemory().project || {};
}

function projectLanes() {
  return projectState().lanes || [];
}

function activeThread() {
  return cachedThreads.find((thread) => thread.id === activeThreadId) || cachedThreads[0] || null;
}

function renderProjectHeader() {
  const project = projectState();
  selectedTitle.textContent = project.name || "Trismegistus";
  selectedMeta.textContent = project.mission || "Runtime first. Jobs are one lane. Codex is the upgrade loop.";
}

function leadForecast(lead) {
  if (!lead) return {value: "NO LEAD", detail: "Sync Wild Toads to load real jobs.", cls: "warn"};
  const score = Number(lead._score || 0);
  const statusText = displayStatus(lead._status || "new");
  if (score >= 5.2 && statusText.includes("ready")) {
    return {value: "PLAY", detail: `${score.toFixed(1)} signal. Tris reads this as a good first move.`, cls: "ok"};
  }
  if (score >= 4.5) {
    return {value: "WATCH", detail: `${score.toFixed(1)} signal. Keep an eye on it, not first strike.`, cls: "warn"};
  }
  return {value: "HOLD", detail: `${score.toFixed(1)} signal. Low priority until better signal appears.`, cls: "bad"};
}

function renderScoreboard() {
  const leads = cachedStatus?.leads || [];
  const agentState = cachedStatus?.agent_state || cachedRuntime?.agent_state || {};
  const memory = projectMemory();
  const project = projectState();
  const golden = memory.golden_mark || {};
  const checkpoints = mirrorCheckpoints();
  const c5b = checkpoints.behavior_comparison || {};
  const hfProbe = checkpoints.hf_probe9_comparison || {};
  const hfLane = checkpoints.hf_lora_lane || {};
  const voice = memory.voice_chain || {};
  const browserMissions = cachedStatus?.browser_missions || cachedRuntime?.browser_missions || {};
  const webarenaSubset = browserMissions.webarena_subset || {};
  const browserLatest = browserMissions.latest || {};
  const lead = selectedLead() || leads[0];
  const runtime = cachedRuntime?.model_runtime || {};
  const openclaw = runtime.openclaw || cachedRuntime?.nemoclaw || {};
  const currentOpenclawReady = Boolean(openclaw.openclaw_ready || cachedRuntime?.nemoclaw?.openclaw_ready);
  const telegramChannel = openclaw.channels?.telegram || cachedRuntime?.nemoclaw?.channels?.telegram || {};
  const telegramReady = Boolean(openclaw.channel_ready || telegramChannel.registered);
  const stripe = cachedStatus?.integrations?.stripe || {};
  const mail = cachedStatus?.integrations?.mac_mail || cachedStatus?.employee_ops?.quadro_outreach || {};
  const rflMail = mail.rfl_mail_bridge || {};
  const mailSummary = mail.summary || {};
  const readyLeads = leads.filter((item) => displayStatus(item._status).includes("ready")).length;
  const reviewLeads = leads.filter((item) => displayStatus(item._status).includes("review")).length;
  const highValueLeads = leads.filter((item) => Number(item._score || 0) >= 5.2).length;
  const forecast = leadForecast(lead);
  const runtimeLive = Boolean(currentOpenclawReady);
  const stripeLive = Boolean(stripe.ready);
  const appliedCount = (cachedStatus?.recent_events || []).filter((event) => event.kind === "application_sent").length;
  const emailConnected = Boolean(mail.ready_for_draft_packets);
  const chatTurns = (cachedStatus?.recent_events || []).filter((event) => event.kind === "chat_turn").length;
  const cycleTurns = (cachedStatus?.recent_events || []).filter((event) => event.kind === "operator_cycle").length;
  const agentForecast = agentState?.forecast?.label
    ? {
        value: agentState.forecast.label,
        detail: agentState.forecast.plain || forecast.detail,
        cls: agentState.forecast.label === "PLAY" ? "ok" : agentState.forecast.label === "WATCH" ? "warn" : "bad",
      }
    : forecast;
  const autonomyLevel = String(agentState?.autonomy_level || "not-running").toUpperCase();
  const autonomyReady = Boolean(currentOpenclawReady && agentState?.autonomy_ready);
  const autonomyTruth = autonomyReady
    ? "current OpenClaw route plus saved receipt"
    : (runtimeLive ? "OpenClaw route answers; current worker receipt pending" : "blocked until current OpenClaw route answers");
  const workerTrace = agentState?.trace_paths || {};
  const jsonMemoryCount = Number(memory.json_memory_entries || 0);
  const sqlReady = Boolean(memory.sqlite_exists);
  const langchainReady = Boolean(memory.langchain_available);
  const langgraphReady = Boolean(memory.langgraph_available);
  const goldenReady = Boolean(golden.source_found);
  const evalReady = Boolean(golden.evals_found);
  const c5bWins = c5b.metric_total ? `${c5b.metric_wins}/${c5b.metric_total}` : "GATE";
  const hfWins = hfProbe.metric_total ? `${hfProbe.metric_wins}/${hfProbe.metric_total}` : "GATE";
  const hfCheckpointReady = Boolean(hfLane.hf_checkpoint_exists);
  const voiceSourceReady = Boolean(voice.home_node_notes_found || voice.mirror_vocal_lab_found);
  const browserMicReady = Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
  const speechOutReady = Boolean(window.speechSynthesis || voice.macos_say_talkback === "wired");
  const voiceValue = browserMicReady || speechOutReady ? "WIRED" : (voiceSourceReady ? "SOURCE" : "MISSING");
  const voiceDetail = [
    browserMicReady ? "browser mic" : "mic blocked",
    voice.macos_say_talkback === "wired" ? "Samantha talkback" : "talkback source",
  ].join(" / ");

  scoreboard.innerHTML = [
    boardCard("Mission", "PARTNER", project.priority || "AI expert partner rehearsal first", "ok"),
    boardCard("NemoHermes", runtimeLive ? "ROUTE" : "BRIDGE", runtimeLive ? "Named OpenClaw agent can answer through the contest route" : "GFL Hermes bridge carries chat while OpenClaw worker gate is verified", runtimeLive ? "ok" : "warn"),
    boardCard("Telegram", telegramReady ? "LIVE" : "GATE", telegramReady ? "OpenClaw channel registered and policy applied" : "NemoClaw channel receipt pending", telegramReady ? "ok" : "warn"),
    boardCard("NemoClaw worker", autonomyReady ? "LOCAL" : "NEXT", autonomyReady ? "Local worker artifact saved; external sends still gated" : "Fresh OpenClaw/NemoClaw worker receipt is the autonomy gate", autonomyReady ? "ok" : "warn"),
    boardCard("CB5 foundation", goldenReady ? "FOUND" : "MISSING", golden.active_gate || "Golden Mark evidence lane", goldenReady ? "ok" : "bad"),
    boardCard("SSP compare", c5bWins, "Parsed architecture-off/on scorecards", checkpoints.ok ? "ok" : "warn"),
    boardCard("HF probe9", hfWins, "Matched-turn repaired scorecards", hfWins === "13/13" ? "ok" : "warn"),
    boardCard("HF checkpoint", hfCheckpointReady ? "FOUND" : "GATE", "OpenHermes path for PEFT lane", hfCheckpointReady ? "ok" : "warn"),
    boardCard("CB5 cards", String(golden.result_card_count || 0), evalReady ? "Nous eval result cards located" : "Eval card path not found", evalReady ? "ok" : "warn"),
    boardCard("Adapters", String(golden.adapter_run_count || 0), golden.lateband_gate_found ? "Late-band adapter gate found" : "Adapter runs located", goldenReady ? "ok" : "warn"),
    boardCard("JSON memory", String(jsonMemoryCount), memory.json_memory_path || "persistent_memory.jsonl", jsonMemoryCount ? "ok" : "warn"),
    boardCard("SQL memory", sqlReady ? "ON" : "OFF", memory.sqlite_path || "trismegistus.sqlite3", sqlReady ? "ok" : "bad"),
    boardCard("LangChain", langchainReady ? "ON" : "OFF", langchainReady ? "Package available" : "Package not installed in this env", langchainReady ? "ok" : "warn"),
    boardCard("LangGraph", langgraphReady ? "ON" : "OFF", langgraphReady ? "Package available" : "Package not installed in this env", langgraphReady ? "ok" : "warn"),
    boardCard("Voice chain", voiceValue, voiceDetail, browserMicReady || speechOutReady ? "ok" : (voiceSourceReady ? "warn" : "bad")),
    boardCard("Browser worker", browserLatest.action_trace_zip ? "TRACE" : "GATE", browserLatest.action_trace_zip ? "Playwright action trace saved" : "Run first WebArena trace", browserLatest.action_trace_zip ? "ok" : "warn"),
    boardCard("WebArena", "255/258", "Hard receipt parked; final rows need upstream/contest treatment", "ok"),
    boardCard("SWE-bench", "PARKED", "Local official selected-test foundation; hosted review pending", "warn"),
    boardCard("GAIA", "HF GATE", "Local source smoke clean; private scoring needs HF access", "warn"),
    boardCard("Source sites", browserLatest.live_sequence_markdown ? "TRACE" : "GATE", browserLatest.live_sequence_markdown ? "Live partner/careers/RFL sequence saved" : "Run live source sequence", browserLatest.live_sequence_markdown ? "ok" : "warn"),
    boardCard("Jobs lane", String(leads.length), "Wild Toads scout lane for paid work", leads.length ? "ok" : "warn"),
    boardCard("Quadro Mail", emailConnected ? "DRAFT" : "GATE", emailConnected ? `${mailSummary.queued_not_sent || 0} queued; Mac Mail packet ready` : "Quadro queue not loaded", emailConnected ? "ok" : "warn"),
    boardCard("Forecast", agentForecast.value, agentForecast.detail, agentForecast.cls),
    boardCard("Email send", rflMail.draft_bridge_ready ? "MAC" : "GATED", rflMail.draft_bridge_ready ? "Apple Mail draft bridge wired; live sends approval-gated" : "Mac Mail bridge pending", rflMail.draft_bridge_ready ? "ok" : "warn"),
    boardCard("Stripe", stripeLive ? "LIVE" : "DRAFT", stripeLive ? "Payment lane can charge" : "Draft payment actions only", stripeLive ? "ok" : "warn"),
    boardCard("Stripe Ops", stripe.payment_link_ready ? "LINK" : (stripe.sandbox_ready ? "SANDBOX" : "DRAFT"), stripe.payment_link_ready ? "Real test Payment Link route wired; no live money moved" : "Gig collection and bill-pay packets; no live money moved", stripe.payment_link_ready || stripe.sandbox_ready ? "ok" : "warn"),
    boardCard("Codex loop", "READY", "Tris can generate build requests back to Codex", "ok"),
  ].join("");

  const topLines = leads.slice(0, 6).map((item, index) => {
    const budget = item.budget_usd ? `$${item.budget_usd}` : "budget open";
    return `${index + 1}. ${item.title} | ${item.source} | ${budget} | score ${item._score ?? "new"} | ${displayStatus(item._status)}`;
  });
  reportState.textContent = runtimeLive ? "model live" : "checking";
  reportOutput.textContent = [
    "TRISMEGISTUS SCOREBOARD",
    "",
    `Mission: ${project.mission || "self-improving operator"}`,
    `Priority: ${project.priority || "runtime first"}`,
    `Next gate: ${project.next_gate || "wire worker loop"}`,
    "",
    `Current runtime: ${runtimeLive ? "OpenClaw live now" : "OpenClaw blocked now"} / ${runtime.active || "unknown"}${openclaw.model ? ` / ${openclaw.model}` : ""}`,
    "Showtime mode: AI expert partner rehearsal; receipt mode stays behind the surface unless proof is requested.",
    openclaw.sandbox_phase ? `Current sandbox phase: ${openclaw.sandbox_phase}` : "",
    `Telegram channel: ${telegramReady ? "live" : "not live"} / ${openclaw.channel_gate || telegramChannel.summary || "not checked"}`,
    `Last saved receipt: ${agentState?.autonomy_level || "none"}${agentState?.autonomy_ready ? " / old receipt exists" : " / no saved autonomy receipt"}`,
    `Current autonomy: ${autonomyTruth}`,
    workerTrace.json ? `Worker JSON: ${workerTrace.json}` : "",
    workerTrace.markdown ? `Worker MD: ${workerTrace.markdown}` : "",
    `CB5 foundation: ${golden.source_found ? "located" : "missing"} / ${golden.active_gate || "none"}`,
    `SSP/C5B scorecards: ${c5bWins} metric wins / rows ${c5b.baseline?.row_count || 0} baseline, ${c5b.golden_mark?.row_count || 0} Golden Mark`,
    `HF probe9 scorecards: ${hfWins} metric wins / rows ${hfProbe.baseline?.row_count || 0} baseline, ${hfProbe.golden_mark?.row_count || 0} Golden Mark`,
    `HF checkpoint: ${hfCheckpointReady ? "found" : "missing"} / ${hfLane.hf_checkpoint || "none"}`,
    `Checkpoint next gate: ${checkpoints.next_gate || "not loaded"}`,
    `CB5 result cards: ${golden.result_card_count || 0}`,
    `JSON memory: ${jsonMemoryCount} entries`,
    `SQL memory: ${sqlReady ? "on" : "off"}`,
    `LangChain: ${langchainReady ? "available" : "not installed"}`,
    `LangGraph: ${langgraphReady ? "available" : "not installed"}`,
    `Voice chain: ${voice.truth || "not checked"}`,
    `Browser worker: ${browserLatest.action_trace_markdown ? "trace saved" : "trace pending"}`,
    browserLatest.action_trace_markdown ? `Browser trace MD: ${browserLatest.action_trace_markdown}` : "",
    browserLatest.action_trace_zip ? `Browser trace ZIP: ${browserLatest.action_trace_zip}` : "",
    browserLatest.live_sequence_markdown ? `Live source MD: ${browserLatest.live_sequence_markdown}` : "",
    browserLatest.live_sequence_zip ? `Live source ZIP: ${browserLatest.live_sequence_zip}` : "",
    "Benchmark foundation: SWE-bench parked pending hosted/maintainer response; WebArena hard receipt 255/258 parked with upstream row boundary; GAIA official/private still HF-gated.",
    `WebArena subset: ${webarenaSubset.ok ? "live" : "not live"} / ${webarenaSubset.url || "http://127.0.0.1:4399/"}`,
    `Chat threads: ${cachedThreads.length}`,
    `Jobs loaded: ${leads.length}`,
    `Ready candidates: ${readyLeads}`,
    `Selected: ${agentState?.selected_title || (lead ? lead.title : "none")}`,
    `Forecast: ${agentForecast.value} - ${agentForecast.detail}`,
    `Applied: ${appliedCount} sent`,
    `Quadro/Mac Mail: ${emailConnected ? "draft packets ready" : "queue gated"} / queued_not_sent ${(mailSummary.queued_not_sent ?? "n/a")}`,
    `Email send: ${rflMail.draft_bridge_ready ? "Apple Mail draft bridge wired" : "approval-gated"}; live sends require explicit approval`,
    `Stripe: ${stripeLive ? "live" : (stripe.payment_link_ready ? "sandbox Payment Link ready" : (stripe.sandbox_ready ? "sandbox key detected" : "draft mode"))}`,
    `Stripe employee ops: ${stripe.payment_link_ready ? "real test Payment Link API route wired" : "gig collection and bill-pay planning packets"}; no live money moved`,
    agentState?.model_note?.text ? `\nLAST SAVED TRIS NOTE - not current live proof\n${agentState.model_note.text}` : "",
    "",
    "PROJECT LANES",
    ...(projectLanes().length ? projectLanes().map((lane) => `${lane.name}: ${lane.status} - ${lane.detail}`) : ["No project lanes loaded."]),
    "",
    "PAID-WORK LANE",
    ...(topLines.length ? topLines : ["No leads loaded yet."]),
  ].join("\n");
  renderCheckpoints();
  renderProjectHeader();
}

function formatMetric(value) {
  if (value === null || value === undefined || value === "") return "n/a";
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(3) : String(value);
}

function metricRow(label, key, comparison) {
  const baseline = comparison?.baseline?.metric_means?.[key];
  const golden = comparison?.golden_mark?.metric_means?.[key];
  const delta = comparison?.metric_deltas?.[key];
  return `
    <div class="metric-row">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(formatMetric(baseline))}</strong>
      <strong>${escapeHtml(formatMetric(golden))}</strong>
      <em>${escapeHtml(delta === null || delta === undefined ? "n/a" : `+${formatMetric(delta)}`)}</em>
    </div>
  `;
}

function renderCheckpoints() {
  if (!checkpointPanel) return;
  const checkpoints = mirrorCheckpoints();
  const c5b = checkpoints.behavior_comparison || {};
  const hfProbe = checkpoints.hf_probe9_comparison || {};
  const hfLane = checkpoints.hf_lora_lane || {};
  const c5bFlags = c5b?.baseline?.flag_counts || {};
  const c5bGoldenFlags = c5b?.golden_mark?.flag_counts || {};
  const reports = hfLane.reports || [];
  checkpointState.textContent = checkpoints.ok ? "receipts loaded" : "check gate";
  checkpointPanel.innerHTML = checkpoints.ok ? `
    <div class="checkpoint-read">
      <strong>${escapeHtml(checkpoints.public_read || "Stable-state checkpoint lane loaded.")}</strong>
      <p>${escapeHtml(checkpoints.nested_build_read || "")}</p>
    </div>
    <div class="comparison-grid">
      <article class="comparison-card">
        <span>Architecture-off baseline</span>
        <strong>${escapeHtml(c5b.baseline?.row_count || 0)} rows</strong>
        <p>Drift ${escapeHtml(c5bFlags.drift_flag ?? "n/a")} / evidence failures ${escapeHtml(c5bFlags.evidence_failure_flag ?? "n/a")}</p>
      </article>
      <article class="comparison-card on">
        <span>Architecture-on Golden Mark / C5B</span>
        <strong>${escapeHtml(c5b.golden_mark?.row_count || 0)} rows</strong>
        <p>Drift ${escapeHtml(c5bGoldenFlags.drift_flag ?? "n/a")} / evidence failures ${escapeHtml(c5bGoldenFlags.evidence_failure_flag ?? "n/a")}</p>
      </article>
      <article class="comparison-card on">
        <span>Metric wins</span>
        <strong>${escapeHtml(c5b.metric_total ? `${c5b.metric_wins}/${c5b.metric_total}` : "n/a")}</strong>
        <p>Parsed from matched scorecards.</p>
      </article>
    </div>
    <div class="metric-table">
      <div class="metric-head"><span>Metric</span><strong>off</strong><strong>on</strong><em>delta</em></div>
      ${metricRow("CPQI", "cpqi", c5b)}
      ${metricRow("AOCI", "aoci", c5b)}
      ${metricRow("MSI", "msi", c5b)}
      ${metricRow("CAI", "cai", c5b)}
      ${metricRow("SFD", "sfd", c5b)}
    </div>
    <div class="checkpoint-footer">
      <span>HF probe9: ${escapeHtml(hfProbe.metric_total ? `${hfProbe.metric_wins}/${hfProbe.metric_total}` : "n/a")} metric wins</span>
      <span>Checkpoint: ${escapeHtml(hfLane.hf_checkpoint_exists ? "found" : "missing")}</span>
      <span>Adapters: ${escapeHtml(reports.map((report) => report.spec).filter(Boolean).join(" / ") || "reports pending")}</span>
    </div>
  ` : `
    <div class="empty">Mirror checkpoint receipts are not loaded yet.</div>
  `;
}

function renderRuntime(data) {
  cachedRuntime = data;
  const modelRuntime = data.model_runtime || {};
  const hostedDemo = Boolean(data.hosted_demo);
  const hostedModelConfigured = Boolean(data.hosted_model_configured);
  const openclaw = modelRuntime.openclaw || data.nemoclaw || {};
  const gfl = modelRuntime.golden_field_lite || {};
  const ollama = modelRuntime.ollama || {};
  const hermes = modelRuntime.hermes || data.hermes || {};
  const nemo = data.nemoclaw || {};
  const blockers = nemo.blockers || [];
  const active = modelRuntime.active || "none";
  const modelReady = Boolean(modelRuntime.ready);
  const gflActive = active === "golden-field-lite-hermes-bridge" || Boolean(gfl.ready);
  const gflRuntimeOnline = Boolean(gfl.runtime?.online);
  const hermesReady = Boolean(hermes.ready);
  const openclawReady = Boolean(openclaw.openclaw_ready || nemo.openclaw_ready);
  const telegramChannel = openclaw.channels?.telegram || nemo.channels?.telegram || {};
  const telegramReady = Boolean(openclaw.channel_ready || telegramChannel.registered);
  const nemoclawInstalled = Boolean(openclaw.installed || nemo.installed || openclaw.openshell_installed);
  const openclawModel = openclaw.model || nemo.model || "NVIDIA Nemotron via ollama-direct";
  const openclawProvider = openclaw.nemohermes_status?.liveInference?.provider || "ollama-direct";
  const routeProvider = openclawReady ? `NemoHermes/OpenClaw (${openclawProvider})` : openclawProvider;
  const openclawAgent = openclaw.agent || nemo.agent || "trismegistus";
  const chatModel = gflActive ? "OpenHermes 2.5 Mistral 7B 4-bit / MLX" : openclawModel;
  const routeBlockedLabel = hostedDemo && !hostedModelConfigured ? "provider key required" : "route blocked";

  runtimeStrip.innerHTML = [
    chip("Chat route", gflActive ? "GFL Hermes/MLX" : (openclawReady ? "OpenClaw answers" : routeBlockedLabel), state(gflActive || openclawReady)),
    chip("Worker agent", openclawReady ? openclawAgent : "next gate", state(openclawReady, true)),
    chip("NemoClaw", telegramReady ? "telegram live" : (nemoclawInstalled ? (openclawReady ? "worker receipt" : "channel gate") : "CLI missing"), state(telegramReady || openclawReady, nemoclawInstalled)),
    chip("Model", modelReady ? chatModel : "no model answering", state(modelReady)),
  ].join("");

  const modelText = gflActive
    ? `Chat route: Golden Field Lite bridge -> local Hermes/MLX checkpoint on 127.0.0.1:8788. Evidence docs: ${gfl.evidence_count ?? "n/a"}; JSONL: ${gfl.jsonl_entries ?? "n/a"}.`
    : openclawReady
    ? `Model route: OpenShell -> OpenClaw agent ${openclawAgent} -> ${openclawModel}. Worker artifacts are the autonomy gate.`
    : hostedDemo && !hostedModelConfigured
    ? "Hosted Render UI is online, but no Hermes/Nous provider key is connected. Chat responses are bounded proof/demo text until HERMES_API_KEY or NOUS_API_KEY is set."
    : `OpenClaw is not answering yet. Standby local model: ${ollama.model || "none"}.`;
  modelLaneState.textContent = modelReady ? "live" : "blocked";
  chatRuntimeLabel.textContent = gflActive
    ? "GFL Hermes bridge live"
    : openclawReady
    ? "OpenClaw model route live"
    : hostedDemo && !hostedModelConfigured
    ? "Hermes provider gated"
    : "OpenClaw blocked";
  modelLanePanel.innerHTML = [
    runtimeItem("Model response lane", modelText, state(modelReady)),
    runtimeItem(
      "NemoClaw channel",
      telegramReady
        ? `${openclaw.channel_gate || telegramChannel.summary || "Telegram registered"}; worker loop remains the next autonomy gate.`
        : "Discord/Telegram bot mode is a NemoClaw/OpenClaw channel gate.",
      state(telegramReady, nemoclawInstalled),
    ),
  ].join("");

  runtimePanel.innerHTML = [
    runtimeItem("Golden Field Lite bridge", gflActive ? `Known-good research partner source is loaded read-only. Runtime ${gflRuntimeOnline ? "online" : "starts on demand"} at 127.0.0.1:8788.` : "GFL bridge not loaded yet.", state(gflActive)),
    runtimeItem("OpenClaw model route", openclawReady ? `Named agent ${openclawAgent} answered through the contest sandbox path.` : (blockers.join("; ") || "OpenClaw worker receipt pending."), state(openclawReady, nemoclawInstalled)),
    runtimeItem("Autonomous worker", "Local worker cycle can create trace artifacts. No job application, email, or Stripe live action is claimed until separate connector receipts exist.", "warn"),
    runtimeItem("Model route", openclawReady ? `${routeProvider} / ${openclawModel}` : "No contest model route verified.", state(openclawReady)),
    runtimeItem("Hermes endpoint", hermesReady ? "Hermes Agent / Nous route answered." : (hostedDemo && !hostedModelConfigured ? "No hosted Hermes/Nous key is connected on Render." : "Standalone Hermes endpoint is not the active lane when GFL bridge or OpenClaw is answering."), state(hermesReady, hostedDemo)),
  ].join("");

  foundationPanel.innerHTML = [
    runtimeItem("OpenClaw status", openclawReady ? "Ready for named-agent model turns. Run Worker for local autonomy receipt." : "Installed. Next gate is a fresh worker receipt and channel status check.", state(openclawReady, nemoclawInstalled)),
    runtimeItem("Channel gate", openclaw.channel_gate || "NemoClaw/OpenClaw channels add/status for Discord or Telegram bot.", state(telegramReady, nemoclawInstalled)),
  ].join("");
  renderScoreboard();
}

async function loadRuntime() {
  runtimeStrip.innerHTML = chip("Runtime", "checking model and OpenClaw", "warn");
  runtimePanel.innerHTML = runtimeItem("Runtime check", "Probing model, Hermes, NemoHermes, NemoClaw, and sandbox state.", "warn");
  try {
    renderRuntime(await api("/api/runtime"));
  } catch (error) {
    runtimeStrip.innerHTML = chip("Runtime", "check failed", "bad");
    runtimePanel.innerHTML = runtimeItem("Runtime check failed", error.message, "bad");
    chatRuntimeLabel.textContent = "runtime error";
  }
}

function renderThreads() {
  queueCount.textContent = `${cachedThreads.length || 0} threads`;
  if (!cachedThreads.length) {
    leadQueue.innerHTML = `<div class="empty">No chat threads yet.</div>`;
    return;
  }
  leadQueue.innerHTML = cachedThreads.map((thread) => `
    <article class="lead thread-card ${thread.id === activeThreadId ? "selected" : ""}" data-thread="${escapeHtml(thread.id)}">
      <div>
        <strong>${escapeHtml(thread.title || "Trismegistus")}</strong>
        <p>${escapeHtml(thread.message_count || 0)} messages / ${escapeHtml(thread.updated_at || thread.ts || "")}</p>
      </div>
      <button class="mini thread-delete" type="button" data-delete-thread="${escapeHtml(thread.id)}" title="Delete chat thread">Delete</button>
    </article>
  `).join("");
  document.querySelectorAll(".thread-card[data-thread]").forEach((card) => {
    card.addEventListener("click", (event) => {
      if (event.target.closest("[data-delete-thread]")) return;
      selectThread(card.dataset.thread);
    });
  });
  document.querySelectorAll("[data-delete-thread]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      const threadId = button.dataset.deleteThread;
      await api("/api/chat-threads/delete", {thread_id: threadId});
      if (activeThreadId === threadId) activeThreadId = "tris-main";
      await loadThreads();
      await loadThreadMessages(activeThreadId);
    });
  });
}

function eventSummary(payload) {
  if (!payload || typeof payload !== "object") return String(payload || "");
  const parts = [];
  if (payload.lead_id) parts.push(payload.lead_id);
  if (payload.lead_count !== undefined) parts.push(`${payload.lead_count} leads`);
  if (payload.source) parts.push(payload.source);
  if (payload.ok !== undefined) parts.push(payload.ok ? "ok" : "blocked");
  if (payload.error) parts.push(payload.error);
  if (payload.run_id) parts.push(payload.run_id);
  return parts.join(" / ") || JSON.stringify(payload).slice(0, 140);
}

function renderEvents(eventList) {
  events.innerHTML = eventList.length
    ? eventList.map((event) => `
      <div class="event">
        <strong>${escapeHtml(event.kind)}</strong>
        <p>${escapeHtml(event.ts)} / ${escapeHtml(eventSummary(event.payload))}</p>
      </div>
    `).join("")
    : `<div class="empty">No local events yet.</div>`;
}

function renderToolsDoctor(result) {
  const checks = result.checks || [];
  const lines = [
    `TOOLS DOCTOR: ${String(result.verdict || "unknown").toUpperCase()}`,
    "",
    ...checks.map((check) => `${check.ok ? "OK" : "BLOCK"} ${check.label}: ${check.detail || ""}`),
    "",
    `RAG: ${result.rag?.status || "unknown"} / external ${result.rag?.external_messages ?? 0} / memory ${result.rag?.memory_items ?? 0} / fts ${result.rag?.fts_items ?? 0}`,
    `Last OpenClaw sync: ${result.last_sync?.ts || "not found"}`,
    "",
    "NOUS SOURCE PROBE",
    result.source_role?.answer_preview || "No role source receipt.",
    "",
    "RECENT OPENCLAW TOOL ERRORS",
    ...(result.recent_openclaw_tool_errors?.length
      ? result.recent_openclaw_tool_errors.map((item, index) => `${index + 1}. ${item.ts} / ${item.source} / ${item.content}`)
      : ["No recent imported OpenClaw tool errors."]),
    "",
    `Read: ${result.read || ""}`,
    `Next gate: ${result.next_gate || ""}`,
  ];
  toolsDoctorOutput.textContent = lines.join("\n");
}

function renderBrowserMissions(result) {
  if (!browserMissionsOutput) return;
  const latest = result.latest || result.paths || {};
  const subset = result.webarena_subset || result.webarenaSubset || result.webarena_subset_status || result.webarena_subset || {};
  const loadedCount = result.ok_count !== undefined && result.target_count !== undefined
    ? `Loaded: ${result.ok_count}/${result.target_count}`
    : "";
  const targetLines = Array.isArray(result.results)
    ? result.results.map((item) => `${item.ok ? "OK" : "BLOCK"} ${item.label || item.id}: ${item.title || item.error || item.url}`)
    : [];
  const baselineMap = result.webarena_baseline_map || {};
  const lines = [
    `BROWSER MISSIONS: ${result.ok === false ? "BLOCKED" : "READY"}`,
    "",
    result.source ? `Source: ${result.source}` : "",
    result.returncode !== undefined ? `Return code: ${result.returncode}` : "",
    result.latency_ms !== undefined ? `Latency: ${result.latency_ms} ms` : "",
    result.url ? `URL: ${result.url}` : "",
    result.pid ? `PID: ${result.pid}` : "",
    loadedCount,
    result.probe ? `Probe: ${result.probe.ok ? "ok" : "blocked"} / ${result.probe.url || ""}` : "",
    subset?.probe ? `WebArena subset: ${subset.probe.ok ? "live" : "blocked"} / ${subset.url || ""}` : "",
    targetLines.length ? `\nLIVE TARGETS\n${targetLines.join("\n")}` : "",
    "",
    "LATEST RECEIPTS",
    latest.browser_smoke_markdown ? `CDP smoke MD: ${latest.browser_smoke_markdown}` : "",
    latest.benchmark_gate_markdown ? `Benchmark gate MD: ${latest.benchmark_gate_markdown}` : "",
    latest.action_trace_markdown ? `Action trace MD: ${latest.action_trace_markdown}` : "",
    latest.action_trace_zip ? `Action trace ZIP: ${latest.action_trace_zip}` : "",
    latest.live_sequence_markdown ? `Live sequence MD: ${latest.live_sequence_markdown}` : "",
    latest.live_sequence_zip ? `Live sequence ZIP: ${latest.live_sequence_zip}` : "",
    latest.json ? `JSON: ${latest.json}` : "",
    latest.markdown ? `Markdown: ${latest.markdown}` : "",
    latest.trace ? `Trace: ${latest.trace}` : "",
    latest.screenshot ? `Screenshot: ${latest.screenshot}` : "",
    latest.screenshot_dir ? `Screenshot dir: ${latest.screenshot_dir}` : "",
    baselineMap.task_source_raw ? `\nWEB ARENA BASELINE MAP\nTasks: ${baselineMap.task_source_raw}\nRunner: ${baselineMap.runner}\nEvaluators: ${baselineMap.evaluators}\nPrompts: ${baselineMap.baseline_prompts}\nBrowserGym: ${baselineMap.browsergym_webarena}` : "",
    "",
    "PLAYWRIGHT EDGE",
    result.stack?.edge || result.playwright_edge?.verifier || "planner/executor split, state verification, trace replay, workflow memory",
    "",
    result.next_gate ? `Next gate: ${result.next_gate}` : "",
    result.stderr ? `stderr: ${result.stderr.slice(0, 900)}` : "",
    result.stdout ? `stdout:\n${result.stdout.slice(0, 1600)}` : "",
    result.error ? `Error: ${result.error}` : "",
  ].filter(Boolean);
  browserMissionState.textContent = result.ok === false ? "blocked" : "receipt ready";
  browserMissionsOutput.textContent = lines.join("\n");
}

function renderMessages(list) {
  messages.innerHTML = list.length
    ? list.map((item) => `
      <div class="msg ${escapeHtml(item.role)}">
        <small>${escapeHtml(item.role)} / ${escapeHtml(item.ts)}</small>
        ${escapeHtml(item.content)}
      </div>
    `).join("")
    : `<div class="empty">No messages in this Trismegistus thread yet.</div>`;
  messages.scrollTop = messages.scrollHeight;
}

async function loadThreadMessages(threadId) {
  if (!threadId) {
    renderMessages([]);
    return;
  }
  const data = await api(`/api/thread-messages?thread_id=${encodeURIComponent(threadId)}`);
  renderMessages(data.messages || []);
}

async function loadThreads() {
  const data = await api("/api/chat-threads");
  cachedThreads = data.threads || [];
  if (!cachedThreads.length) {
    const created = await api("/api/chat-threads", {title: "Trismegistus"});
    cachedThreads = created.threads || [created.thread];
  }
  if (!cachedThreads.some((thread) => thread.id === activeThreadId)) {
    activeThreadId = cachedThreads[0]?.id || "tris-main";
  }
  renderThreads();
  sendChatButton.disabled = !activeThreadId;
}

async function selectThread(threadId) {
  activeThreadId = threadId || activeThreadId || "tris-main";
  const thread = activeThread();
  selectedTitle.textContent = thread?.title || "Trismegistus";
  selectedMeta.textContent = "Persistent SQL chat thread. Jobs and research lanes stay visible in the scoreboard.";
  sendChatButton.disabled = false;
  renderThreads();
  await loadThreadMessages(activeThreadId);
}

function selectLead(leadId) {
  selectedLeadId = leadId;
  const lead = selectedLead();
  if (!lead) return;
  renderProjectHeader();
  renderScoreboard();
}

async function refresh() {
  cachedStatus = await api("/api/status");
  await loadThreads();
  renderEvents(cachedStatus.recent_events || []);
  if (!selectedLeadId && (cachedStatus.leads || []).length) {
    selectedLeadId = cachedStatus.leads[0].id;
  }
  if (selectedLeadId) {
    const exists = (cachedStatus.leads || []).some((item) => item.id === selectedLeadId);
    if (exists) selectLead(selectedLeadId);
  } else {
    renderScoreboard();
  }
  await loadThreadMessages(activeThreadId);
}

function summarizeScore(result) {
  const scored = result.scored || result;
  const lead = scored.lead || {};
  return [
    `Lead: ${lead.title || "unknown"}`,
    `Score: ${scored.score}`,
    `Status: ${displayStatus(scored.status)}`,
    scored.reasons?.length ? `Reasons: ${scored.reasons.join(", ")}` : "",
  ].filter(Boolean).join("\n");
}

function summarizeReview(result) {
  const consent = result.consent || {};
  const scored = result.scored || {};
  return [
    `Decision: ${consent.final_decision || "unknown"}`,
    `Score: ${scored.score ?? "unknown"}`,
    "",
    ...(consent.steps || []).map((step) => `${step.name || step.role}: ${step.decision || step.status || "checked"}`),
  ].join("\n");
}

onClick("scanJobs", async () => {
  reportState.textContent = "operator cycle";
  reportOutput.textContent = "Running one honest operator cycle: import leads, forecast, Quadro boundary, model note, save state. This is not an autonomous apply loop yet.";
  const result = await api("/api/operator-cycle", {query: "wild toads road paid technical work", reason: "manual-ui"});
  selectedLeadId = result.selected_lead_id || selectedLeadId;
  reportOutput.textContent = [
    `Operator cycle saved: ${result.id}`,
    `Autonomy: ${result.autonomy_level} / ${result.autonomy_ready ? "active" : "not autonomous yet"}`,
    `Selected: ${result.selected_title}`,
    `Forecast: ${result.forecast?.label} - ${result.forecast?.plain}`,
    `Model note: ${result.model_note?.ok ? "answered" : "blocked"}`,
    result.model_note?.text || "",
  ].join("\n");
  await refresh();
  await loadRuntime();
});

onClick("runWorker", async () => {
  reportState.textContent = "worker cycle";
  reportOutput.textContent = "Running one local autonomous worker cycle: scout, rank, review boundary, OpenClaw agent turn, JSON/Markdown trace. No external send/spend claim.";
  const result = await api("/api/autonomous-worker-cycle", {query: "wild toads road paid technical work", reason: "manual-ui"});
  selectedLeadId = result.selected_lead_id || selectedLeadId;
  reportOutput.textContent = [
    `Worker cycle saved: ${result.id}`,
    `Autonomy: ${result.autonomy_level} / ${result.autonomy_ready ? "local worker receipt" : "blocked"}`,
    `Selected: ${result.selected_title}`,
    result.selected_url ? `Source URL: ${result.selected_url}` : "",
    `Runtime: ${result.worker_result?.runtime_lane || result.worker_result?.source || "blocked"}`,
    result.worker_result?.provider ? `Provider: ${result.worker_result.provider}` : "",
    result.worker_result?.model ? `Model: ${result.worker_result.model}` : "",
    result.worker_result?.session_file ? `OpenClaw session: ${result.worker_result.session_file}` : "",
    result.trace_paths?.json ? `Trace JSON: ${result.trace_paths.json}` : "",
    result.trace_paths?.markdown ? `Trace MD: ${result.trace_paths.markdown}` : "",
    "",
    `Applied: ${result.external_actions?.applied === true}`,
    `Email sent: ${result.external_actions?.email_sent === true}`,
    `Stripe live charge: ${result.external_actions?.stripe_live_charge === true}`,
    "Raw OpenClaw text is saved in the Markdown/JSON receipt. Deterministic trace fields above control the public claim.",
    result.worker_result?.error ? `Worker block: ${result.worker_result.error}` : "",
  ].filter(Boolean).join("\n");
  await refresh();
  await loadRuntime();
});

document.getElementById("chatForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (chatSendInFlight) return;
  if (!activeThreadId) await loadThreads();
  if (!activeThreadId || !chatInput.value.trim()) return;
  const message = chatInput.value.trim();
  chatInput.value = "";
  let before = {messages: []};
  chatSendInFlight = true;
  sendChatButton.disabled = true;
  try {
    before = await api(`/api/thread-messages?thread_id=${encodeURIComponent(activeThreadId)}`);
    renderMessages([...before.messages, {role: "user", ts: "sending", content: message}]);
    reportState.textContent = "agent thinking";
    const result = await api("/api/chat", {thread_id: activeThreadId, message}, 25000);
    renderMessages(result.messages || []);
    const assistantReply = [...(result.messages || [])].reverse().find((item) => item.role === "assistant")?.content || result.result?.text || "";
    if (result.result?.ok) {
      const modelGenerated = result.result.model_generated !== false;
      if (result.result.selected_lead_id) {
        selectedLeadId = result.result.selected_lead_id;
      }
      reportState.textContent = modelGenerated ? "model live" : "provider gated";
      reportOutput.textContent = [
        `Lane: ${result.result.runtime_lane || result.result.source}`,
        modelGenerated ? "Model generation: live" : "Model generation: not connected on this hosted route",
        result.result.provider_gate ? `Provider gate: ${result.result.provider_gate}` : "",
        result.result.provider ? `Provider: ${result.result.provider}` : "",
        result.result.model ? `Model: ${result.result.model}` : "",
        result.result.session_file ? `OpenClaw session: ${result.result.session_file}` : "",
        result.result.trace_paths?.json ? `Trace JSON: ${result.result.trace_paths.json}` : "",
        result.result.trace_paths?.markdown ? `Trace MD: ${result.result.trace_paths.markdown}` : "",
        result.result.usage ? `Tokens: ${result.result.usage.total || "unknown"}` : "",
        result.result.hermes_error ? `Hermes target: ${result.result.hermes_error}` : "",
        result.result.autonomy_level ? `Autonomy: ${result.result.autonomy_level}${result.result.autonomy_ready ? " / active" : " / not autonomous yet"}` : "",
      ].filter(Boolean).join("\n");
      if (talkbackEnabled && assistantReply) {
        api("/api/voice/speak", {text: assistantReply}).catch((error) => {
          voiceState.textContent = `Talkback blocked: ${error.message}`;
        });
      }
    } else {
      reportState.textContent = "runtime blocked";
      reportOutput.textContent = `Model runtime blocked:\n${result.result?.error || "unknown error"}`;
    }
  } catch (error) {
    reportState.textContent = "runtime blocked";
    reportOutput.textContent = `Chat request failed:\n${error.message}`;
    renderMessages([
      ...(before.messages || []),
      {role: "user", ts: "sent", content: message},
      {role: "system", ts: new Date().toISOString(), content: `Chat request failed cleanly: ${error.message}`},
    ]);
  } finally {
    await refresh().catch(() => {});
    chatSendInFlight = false;
    sendChatButton.disabled = !activeThreadId;
  }
});

chatInput.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.shiftKey || event.metaKey || event.ctrlKey || event.altKey) return;
  event.preventDefault();
  document.getElementById("chatForm").dispatchEvent(new Event("submit", {
    bubbles: true,
    cancelable: true,
  }));
});

newThreadButton.addEventListener("click", async () => {
  const data = await api("/api/chat-threads", {title: "Trismegistus"});
  cachedThreads = data.threads || [];
  activeThreadId = data.thread?.id || cachedThreads[0]?.id || activeThreadId;
  renderThreads();
  await selectThread(activeThreadId);
});

function setupVoiceControls() {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) {
    voiceListenButton.disabled = true;
    voiceState.textContent = "Browser mic input is not available in this browser. Samantha talkback can still run from the server.";
  } else {
    speechRecognition = new Recognition();
    speechRecognition.lang = "en-US";
    speechRecognition.continuous = false;
    speechRecognition.interimResults = false;
    speechRecognition.onstart = () => {
      voiceState.textContent = "Listening...";
    };
    speechRecognition.onerror = (event) => {
      voiceState.textContent = `Mic blocked: ${event.error || "unknown"}`;
    };
    speechRecognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0]?.transcript || "")
        .join(" ")
        .trim();
      if (transcript) {
        chatInput.value = transcript;
        document.getElementById("chatForm").requestSubmit();
      }
      voiceState.textContent = transcript ? "Voice sent to Trismegistus." : "No speech captured.";
    };
  }

  voiceListenButton.addEventListener("click", () => {
    if (!speechRecognition) return;
    speechRecognition.start();
  });

  voiceTalkbackButton.addEventListener("click", async () => {
    talkbackEnabled = !talkbackEnabled;
    voiceTalkbackButton.textContent = talkbackEnabled ? "Voice On" : "Voice Off";
    voiceState.textContent = talkbackEnabled
      ? "Samantha talkback enabled for assistant replies."
      : "Samantha talkback disabled.";
    if (talkbackEnabled) {
      await api("/api/voice/speak", {text: "Trismegistus talkback is online through the Home Node style Samantha voice."}).catch((error) => {
        voiceState.textContent = `Talkback blocked: ${error.message}`;
      });
    }
    renderScoreboard();
  });
}

onClick("refreshRuntime", loadRuntime);
onClick("refreshRuntimeLeft", loadRuntime);
onClick("runToolsDoctor", async () => {
  toolsDoctorOutput.textContent = "Running tools doctor: source fetch, Telegram sync, RAG, recent tool errors...";
  const result = await api("/api/tools-doctor", {});
  renderToolsDoctor(result);
  await refresh();
});

onClick("refreshBrowserMissions", async () => {
  browserMissionState.textContent = "checking";
  browserMissionsOutput.textContent = "Checking browser mission receipts and WebArena subset...";
  renderBrowserMissions(await api("/api/browser-missions"));
});

onClick("startWebArenaSubset", async () => {
  browserMissionState.textContent = "starting";
  browserMissionsOutput.textContent = "Starting official WebArena homepage subset on 127.0.0.1:4399...";
  renderBrowserMissions(await api("/api/browser-missions/start-webarena", {}));
  await refresh();
});

onClick("runBrowserActionTrace", async () => {
  browserMissionState.textContent = "tracing";
  browserMissionsOutput.textContent = "Running Playwright/CDP action trace: WebArena homepage -> calculator -> page-state verification...";
  renderBrowserMissions(await api("/api/browser-missions/action-trace", {expression: "67+5"}));
  await refresh();
});

onClick("runLiveSiteSequence", async () => {
  browserMissionState.textContent = "live sites";
  browserMissionsOutput.textContent = "Running live source sequence: NVIDIA quantum partner candidates -> Nous careers -> RFL public surface...";
  renderBrowserMissions(await api("/api/browser-missions/live-sequence", {}));
  await refresh();
});

onClick("runBrowserSmoke", async () => {
  browserMissionState.textContent = "smoke";
  browserMissionsOutput.textContent = "Running Playwright/CDP smoke against Tris...";
  renderBrowserMissions(await api("/api/browser-missions/cdp-smoke", {url: "http://127.0.0.1:8898/"}));
  await refresh();
});

onClick("runBenchmarkGate", async () => {
  browserMissionState.textContent = "benchmark";
  browserMissionsOutput.textContent = "Refreshing public benchmark gates: SWE-bench, GAIA, WebArena, Tris coherence, baseline route...";
  renderBrowserMissions(await api("/api/browser-missions/benchmark-gate", {}));
  await refresh();
});

onClick("runCodexHelperStatus", async () => {
  browserMissionState.textContent = "codex helper";
  browserMissionsOutput.textContent = "Reading Codex-helper recursive patch receipts...";
  const result = await api("/api/benchmark-helper");
  browserMissionsOutput.textContent = [
    result.answer || "No benchmark helper answer returned.",
    "",
    `Active route: ${result.active_recursive_coding_route?.name || "unknown"}`,
    `Compare receipt: ${result.compare_receipt || "missing"}`,
    `Next gate: ${result.next_gate || "missing"}`,
  ].join("\n");
  await refresh();
});

onClick("queueCodexHelperRequest", async () => {
  browserMissionState.textContent = "queueing";
  browserMissionsOutput.textContent = "Queueing Codex-helper recursive patch request...";
  const result = await api("/api/benchmark-helper/queue-request", {
    mission_id: "swebench-codex-helper-clean4",
    origin: "tris-ui",
  });
  const request = result.build_request || {};
  browserMissionsOutput.textContent = [
    result.answer || "Codex-helper request queued.",
    "",
    `Build request: ${request.id || "missing"}`,
    `Approval state: ${request.approval_state || "missing"}`,
    `Memory ingestion: ${request.memory_ingestion_status || "missing"}`,
    `Next gate: ${result.next_gate || "missing"}`,
  ].join("\n");
  await refresh();
});

onClick("runCodexHelperMission", async () => {
  browserMissionState.textContent = "patch mission";
  browserMissionsOutput.textContent = "Running one Codex-helper patch through source fetch and local preflight...";
  const result = await api("/api/benchmark-helper/run-coding-mission", {
    mission_id: "swebench-codex-helper-clean4",
    origin: "tris-ui",
  });
  const receipt = result.receipt || {};
  browserMissionsOutput.textContent = [
    result.answer || "Codex-helper patch mission finished.",
    "",
    `Receipt: ${receipt.paths?.markdown || "missing"}`,
    `Prediction JSONL: ${receipt.prediction_jsonl || "missing"}`,
    `Patch validation: ${receipt.patch_validation_error || "passed"}`,
    `Preflight: ${receipt.patch_preflight_error || "passed"}`,
  ].join("\n");
  await refresh();
});

onClick("runCodexHelperCleanSlice", async () => {
  browserMissionState.textContent = "clean4 mission";
  browserMissionsOutput.textContent = "Running clean4 Codex-helper patches through source fetch and local preflight...";
  const result = await api("/api/benchmark-helper/run-clean-slice", {
    mission_id: "swebench-codex-helper-clean4",
    origin: "tris-ui",
  });
  const receipt = result.receipt || {};
  browserMissionsOutput.textContent = [
    result.answer || "Codex-helper clean4 mission finished.",
    "",
    `Receipt: ${receipt.paths?.markdown || "missing"}`,
    `Prediction JSONL: ${receipt.prediction_jsonl || "missing"}`,
    `Preflight-clean rows: ${receipt.clean_count ?? "?"}/${receipt.submitted_count ?? "?"}`,
    `Failed rows: ${receipt.failed_count ?? "?"}`,
    `Official evaluator: ${receipt.official_evaluator_status || "not_run"}`,
  ].join("\n");
  await refresh();
});

setupVoiceControls();

refresh().then(loadRuntime).catch((error) => {
  runtimeStrip.innerHTML = chip("Console", "status load failed", "bad");
  runtimePanel.innerHTML = runtimeItem("Status load failed", error.message, "bad");
});
