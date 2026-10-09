"use strict";

const state = {
  flags: [], sources: {}, anchors: null, integrity: {}, chain: null,
  leads: [], leadSeal: {}, queue: null, leadPage: 0,
};

const LEADS_PER_PAGE = 50;
const ENGINE_LABELS = {
  anomalias: "Referencia de mercado",
  convenio_marco: "Convenio Marco",
  precio_pares: "Precio entre pares",
};
const QUEUE_DATA_NAME = "osint-mercado-queue";
const NUMBER = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 2 });

const HORIZON_URL = "https://horizon-testnet.stellar.org";
const EXPLORER_TX_URL = "https://stellar.expert/explorer/testnet/tx/";
const STATUS_LABELS = {
  pending: "Comprobando",
  verified: "Verificado",
  tampered: "Alterado",
  unanchored: "Sin sellar",
};
const SEV_LABELS = { watch: "Moderada", high: "Alta", severe: "Severa" };

const CLP = new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 });
const RATIO = new Intl.NumberFormat("es-CL", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

function fmtClp(n) {
  return typeof n === "number" ? CLP.format(Math.round(n)) : "-";
}

function escapeHtml(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}

async function fetchJson(path, fallback) {
  try {
    const resp = await fetch(path, { cache: "no-store" });
    return resp.ok ? await resp.json() : fallback;
  } catch (_e) {
    return fallback;
  }
}

async function checkChain(anchors) {
  if (!anchors) return { status: "unanchored" };
  const localDigest = await digestOf(anchors.leaves);
  try {
    const resp = await fetch(`${HORIZON_URL}/transactions/${anchors.tx_hash}`);
    if (!resp.ok) return { status: "unreachable", localDigest };
    const tx = await resp.json();
    const onChain = memoHex(tx);
    const ok = tx.successful && onChain === anchors.digest && localDigest === anchors.digest;
    return { status: ok ? "verified" : "tampered", onChain, localDigest };
  } catch (_e) {
    return { status: "unreachable", localDigest };
  }
}

function mirrorPath(flag) {
  return `./data/mirror/${encodeURIComponent(flag.oc_id)}.json`;
}

async function checkMirror(flag) {
  if (!flag.mirror_sha256) return { mirrorOk: null, mirror: null };
  const mirror = await fetchJson(mirrorPath(flag), null);
  return { mirrorOk: mirror ? (await leafOf(mirror)) === flag.mirror_sha256 : false, mirror };
}

async function checkFlag(flag) {
  const source = state.sources[flag.id];
  let sourceOk = null;
  if (flag.source_sha256) {
    sourceOk = source ? (await leafOf(source)) === flag.source_sha256 : false;
  }
  const { mirrorOk, mirror } = await checkMirror(flag);
  const base = { sourceOk, source, mirrorOk, mirror };
  if (!state.anchors || !state.anchors.flag_ids.includes(flag.id)) {
    return { status: "unanchored", ...base };
  }
  const inAnchor = state.anchors.leaves.includes(await leafOf(flag));
  const chainOk = state.chain && state.chain.status === "verified";
  if (!inAnchor || sourceOk === false || mirrorOk === false
      || (state.chain && state.chain.status === "tampered")) {
    return { status: "tampered", ...base };
  }
  return { status: chainOk ? "verified" : "pending", ...base };
}

function actaMessage(anchors, chain) {
  if (!anchors) return "Esta publicación todavía no tiene sello.";
  const when = fmtTime(anchors.anchored_at);
  if (!chain) return "Comprobando el sello contra la red Stellar...";
  if (chain.status === "verified") return `Sellado en Stellar el ${when}. Su navegador acaba de comprobar que lo que ve es lo que se selló.`;
  if (chain.status === "tampered") return `Lo que ve no coincide con lo sellado en Stellar el ${when}. Algún dato cambió después de publicarse.`;
  return `Sellado en Stellar el ${when}, pero no pudimos consultar la red ahora. Los datos se muestran sin comprobar.`;
}

function renderActa() {
  const a = state.anchors;
  const c = state.chain;
  const status = !a ? "unanchored" : c ? c.status : "pending";
  const box = document.getElementById("acta-status");
  box.className = `acta-status ${status}`;
  const details = a ? `
    <dl class="acta-facts">
      <div><dt>Ledger</dt><dd>${escapeHtml(a.ledger)}</dd></div>
      <div><dt>Transacción</dt><dd><a href="${EXPLORER_TX_URL}${escapeHtml(a.tx_hash)}" target="_blank" rel="noopener">${escapeHtml(a.tx_hash.slice(0, 10))}...${escapeHtml(a.tx_hash.slice(-6))}</a></dd></div>
      <div class="wide"><dt>Huella del conjunto publicado</dt><dd class="hash">${escapeHtml(a.digest)}</dd></div>
    </dl>` : "";
  box.innerHTML = `<p class="status-line">${escapeHtml(actaMessage(a, c))}</p>${details}`;
  renderSeal(document.getElementById("seal"), { digest: a ? a.digest : "", ledger: a ? a.ledger : "", status });
}

function uniqueSorted(items, key) {
  return [...new Set(items.map((f) => f[key]).filter(Boolean))].sort((a, b) => a.localeCompare(b, "es"));
}

function fillOptions(selectId, values) {
  const select = document.getElementById(selectId);
  for (const value of values) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = value;
    select.appendChild(opt);
  }
}

function currentFilters() {
  return {
    comuna: document.getElementById("filter-comuna").value,
    categoria: document.getElementById("filter-categoria").value,
    severidad: document.getElementById("filter-severidad").value,
  };
}

function matches(flag, f) {
  return (!f.comuna || flag.comuna === f.comuna)
    && (!f.categoria || flag.category === f.categoria)
    && (!f.severidad || flag.severity === f.severidad);
}

function fichaChecks(result) {
  const lines = [];
  if (result.source) lines.push(`Línea de la orden capturada el ${fmtTime(result.source.captured_at)}`);
  if (result.sourceOk === false) lines.push("La línea capturada no coincide con su huella");
  if (result.mirror) lines.push(`Copia del registro oficial del ${fmtTime(result.mirror.fetched_at)}`);
  if (result.mirrorOk === false) lines.push("La copia del registro oficial no coincide con su huella");
  return lines.map((l) => `<li>${escapeHtml(l)}</li>`).join("");
}

function fichaHtml(flag) {
  const result = state.integrity[flag.id] || { status: "pending" };
  const sev = flag.severity || "watch";
  const ratio = typeof flag.overprice_ratio === "number" ? RATIO.format(flag.overprice_ratio) : "";
  const links = [];
  if (flag.oc_url) links.push(`<a href="${escapeHtml(flag.oc_url)}" target="_blank" rel="noopener">Orden ${escapeHtml(flag.oc_id)} en Mercado Público</a>`);
  if (flag.mirror_sha256) links.push(`<a href="${mirrorPath(flag)}" target="_blank" rel="noopener">Copia del registro oficial</a>`);
  return `
    <article class="ficha ${result.status}">
      <header class="ficha-head">
        <h3><span class="comuna">${escapeHtml(flag.comuna)}</span> ${escapeHtml(flag.canonical_name || flag.sku_id)}</h3>
        <p class="ficha-cat">${escapeHtml(flag.category)}</p>
      </header>
      <dl class="precios">
        <div><dt>Pagó la municipalidad</dt><dd>${fmtClp(flag.unit_price_clp_gross)}</dd></div>
        <div><dt>Referencia</dt><dd>${fmtClp(flag.reference_price_clp)}</dd></div>
        <div class="ratio ${sev}"><dt>Diferencia</dt><dd>${ratio} veces <span class="sev">${SEV_LABELS[sev] || sev}</span></dd></div>
      </dl>
      <div class="ficha-sello">
        <span class="mini-seal ${result.status}" aria-hidden="true"></span>
        <div>
          <p class="sello-label">${STATUS_LABELS[result.status] || escapeHtml(result.status)}</p>
          <ul class="checks">${fichaChecks(result)}</ul>
        </div>
      </div>
      ${flag.curation_note ? `<p class="nota">Nota de revisión: ${escapeHtml(flag.curation_note)}</p>` : ""}
      <p class="fuentes">${links.join(" ")}</p>
    </article>`;
}

function render() {
  const list = document.getElementById("fichas");
  const empty = document.getElementById("empty");
  const count = document.getElementById("count");
  const filtered = state.flags.filter((flag) => matches(flag, currentFilters()));
  if (state.flags.length === 0) {
    empty.hidden = false;
    list.innerHTML = "";
    count.textContent = "";
    return;
  }
  empty.hidden = true;
  count.textContent = filtered.length === state.flags.length
    ? `${state.flags.length} publicados`
    : `${filtered.length} de ${state.flags.length}`;
  list.innerHTML = filtered.map((flag) => `<li>${fichaHtml(flag)}</li>`).join("");
}

function leadFilters() {
  return {
    search: document.getElementById("lead-search").value.trim().toLocaleLowerCase("es"),
    comuna: document.getElementById("lead-comuna").value,
    engine: document.getElementById("lead-engine").value,
    status: document.getElementById("lead-status").value,
  };
}

function leadMatches(lead, f) {
  return (!f.comuna || lead.comuna === f.comuna)
    && (!f.engine || lead.engine === f.engine)
    && (!f.status || lead.status === f.status)
    && (!f.search || String(lead.product || "").toLocaleLowerCase("es").includes(f.search));
}

function leadStatusCell(lead) {
  if (lead.status === "descartado") {
    return `<span class="estado descartado">Descartado</span><small>${escapeHtml(lead.review_note || "")}</small>`;
  }
  return `<span class="estado en_revision">En revisión</span><small>${escapeHtml(ENGINE_LABELS[lead.engine] || lead.engine)}</small>`;
}

function leadSealCell(lead) {
  const seal = state.leadSeal[lead.id];
  const status = seal || "pending";
  return `<span class="mini-dot ${status}" aria-hidden="true"></span>${STATUS_LABELS[status] || escapeHtml(status)}`;
}

function renderLeads() {
  const body = document.getElementById("lead-rows");
  const filtered = state.leads.filter((lead) => leadMatches(lead, leadFilters()));
  const pages = Math.max(1, Math.ceil(filtered.length / LEADS_PER_PAGE));
  state.leadPage = Math.min(state.leadPage, pages - 1);
  const start = state.leadPage * LEADS_PER_PAGE;
  const slice = filtered.slice(start, start + LEADS_PER_PAGE);
  document.getElementById("lead-count").textContent = filtered.length === state.leads.length
    ? `${NUMBER.format(state.leads.length)} casos`
    : `${NUMBER.format(filtered.length)} de ${NUMBER.format(state.leads.length)}`;
  document.getElementById("lead-page").textContent = `Página ${state.leadPage + 1} de ${pages}`;
  document.getElementById("lead-prev").disabled = state.leadPage === 0;
  document.getElementById("lead-next").disabled = state.leadPage >= pages - 1;
  body.innerHTML = slice.map((lead) => `
    <tr>
      <td>${escapeHtml(lead.comuna)}</td>
      <td class="producto">${escapeHtml(lead.product)}</td>
      <td class="num">${typeof lead.quantity === "number" ? NUMBER.format(lead.quantity) : "-"}</td>
      <td class="num">${fmtClp(lead.price_paid_clp)}<small>${lead.price_basis === "neto" ? "neto" : "con IVA"}</small></td>
      <td>${lead.oc_url ? `<a href="${escapeHtml(lead.oc_url)}" target="_blank" rel="noopener">${escapeHtml(lead.oc_id)}</a>` : escapeHtml(lead.oc_id)}<small>línea ${escapeHtml(lead.correlativo)}</small></td>
      <td>${leadStatusCell(lead)}</td>
      <td class="sello">${leadSealCell(lead)}</td>
    </tr>`).join("");
}

function setupLeadControls() {
  fillOptions("lead-comuna", uniqueSorted(state.leads, "comuna"));
  const engineSelect = document.getElementById("lead-engine");
  for (const engine of [...new Set(state.leads.map((l) => l.engine))]) {
    const opt = document.createElement("option");
    opt.value = engine;
    opt.textContent = ENGINE_LABELS[engine] || engine;
    engineSelect.appendChild(opt);
  }
  for (const id of ["lead-search", "lead-comuna", "lead-engine", "lead-status"]) {
    document.getElementById(id).addEventListener("input", () => {
      state.leadPage = 0;
      renderLeads();
    });
  }
  document.getElementById("lead-prev").addEventListener("click", () => {
    state.leadPage = Math.max(0, state.leadPage - 1);
    renderLeads();
  });
  document.getElementById("lead-next").addEventListener("click", () => {
    state.leadPage += 1;
    renderLeads();
  });
}

async function verifyLeads() {
  if (!state.anchors) return;
  const anchored = new Set(state.anchors.leaves);
  const ids = new Set(state.anchors.flag_ids);
  const chainOk = state.chain && state.chain.status === "verified";
  const leaves = await Promise.all(state.leads.map((lead) => leafOf(lead)));
  state.leads.forEach((lead, i) => {
    if (!ids.has(lead.id)) state.leadSeal[lead.id] = "unanchored";
    else if (!anchored.has(leaves[i]) || (state.chain && state.chain.status === "tampered")) state.leadSeal[lead.id] = "tampered";
    else state.leadSeal[lead.id] = chainOk ? "verified" : "pending";
  });
  renderLeads();
}

async function checkQueue() {
  const box = document.getElementById("queue-status");
  const queue = state.queue;
  const anchors = state.anchors;
  if (!queue || !anchors || !anchors.queue_digest) {
    box.className = "queue-status unanchored";
    box.textContent = "La cola de revisión todavía no tiene sello.";
    return;
  }
  const localDigest = await digestOf(queue.lead_hashes);
  const ops = await fetchJson(`${HORIZON_URL}/transactions/${anchors.tx_hash}/operations?limit=10`, null);
  const records = ops && ops._embedded ? ops._embedded.records : [];
  const entry = records.find((op) => op.type === "manage_data" && op.name === QUEUE_DATA_NAME);
  const total = NUMBER.format(queue.total);
  if (!entry) {
    box.className = "queue-status unreachable";
    box.textContent = `Cola de revisión de ${total} casos. No pudimos leer su sello en la red Stellar ahora.`;
    return;
  }
  const onChain = base64Hex(entry.value);
  const ok = onChain === anchors.queue_digest && localDigest === anchors.queue_digest;
  box.className = `queue-status ${ok ? "verified" : "tampered"}`;
  box.innerHTML = ok
    ? `La cola de ${escapeHtml(total)} casos en revisión está sellada en la misma transacción. Si alguien quita un caso, el sello deja de coincidir. <span class="hash">${escapeHtml(onChain.slice(0, 16))}...</span>`
    : `La cola de revisión publicada no coincide con la sellada en Stellar.`;
}

async function loadTimeline() {
  const list = document.getElementById("timeline");
  const account = state.anchors && state.anchors.account;
  if (!account) {
    list.innerHTML = "<li class=\"timeline-empty\">Esta publicación todavía no tiene sello.</li>";
    return;
  }
  const page = await fetchJson(`${HORIZON_URL}/accounts/${account}/transactions?order=desc&limit=50`, null);
  const records = page && page._embedded ? page._embedded.records : [];
  const seals = records.filter((tx) => tx.memo_type === "hash" && tx.successful);
  if (!seals.length) {
    list.innerHTML = "<li class=\"timeline-empty\">No pudimos leer el historial desde la red Stellar en este momento.</li>";
    return;
  }
  list.innerHTML = seals.map((tx) => {
    const digest = memoHex(tx);
    const current = state.anchors && tx.hash === state.anchors.tx_hash;
    return `
      <li class="${current ? "current" : ""}">
        <span class="dot" aria-hidden="true"></span>
        <div>
          <p class="when">${escapeHtml(fmtTime(tx.created_at))}${current ? " <strong>sello vigente</strong>" : ""}</p>
          <p class="meta">Ledger ${escapeHtml(tx.ledger)}, huella <span class="hash">${escapeHtml(digest.slice(0, 12))}...</span>
            <a href="${EXPLORER_TX_URL}${escapeHtml(tx.hash)}" target="_blank" rel="noopener">ver transacción</a></p>
        </div>
      </li>`;
  }).join("");
}

async function verify() {
  renderActa();
  state.chain = await checkChain(state.anchors);
  renderActa();
  for (const flag of state.flags) {
    state.integrity[flag.id] = await checkFlag(flag);
  }
  render();
}

async function load() {
  [state.flags, state.sources, state.anchors, state.leads, state.queue] = await Promise.all([
    fetchJson("./data/flags.json", []),
    fetchJson("./data/sources.json", {}),
    fetchJson("./data/anchors.json", null),
    fetchJson("./data/leads.json", []),
    fetchJson("./data/queue.json", null),
  ]);
  setupLeadControls();
  renderLeads();
  fillOptions("filter-comuna", uniqueSorted(state.flags, "comuna"));
  fillOptions("filter-categoria", uniqueSorted(state.flags, "category"));
  for (const id of ["filter-comuna", "filter-categoria", "filter-severidad"]) {
    document.getElementById(id).addEventListener("change", render);
  }
  render();
  await Promise.all([verify().then(verifyLeads), loadTimeline(), checkQueue()]);
}

load();
