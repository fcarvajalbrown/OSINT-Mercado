"use strict";

const state = { flags: [], sources: {}, anchors: null, integrity: {}, chain: null };

const HORIZON_TX_URL = "https://horizon-testnet.stellar.org/transactions/";
const CHILE_TIME = new Intl.DateTimeFormat("es-CL", {
  timeZone: "America/Santiago", dateStyle: "medium", timeStyle: "short",
});
const UTC_TIME = new Intl.DateTimeFormat("es-CL", { timeZone: "UTC", timeStyle: "short" });
const INTEGRITY_LABELS = {
  pending: "Verificando...",
  verified: "Verificado",
  tampered: "Alterado",
  unanchored: "Sin anclar",
};

const CLP = new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 });
const SEV_LABELS = { watch: "Moderada", high: "Alta", severe: "Severa" };

function fmtClp(n) {
  return typeof n === "number" ? CLP.format(Math.round(n)) : "-";
}

function fmtTime(iso) {
  if (!iso) return "";
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return "";
  return `${CHILE_TIME.format(when)} (${UTC_TIME.format(when)} UTC)`;
}

function normalise(value) {
  if (Array.isArray(value)) return value.map(normalise);
  if (value && typeof value === "object") {
    const out = {};
    for (const key of Object.keys(value).sort()) out[key] = normalise(value[key]);
    return out;
  }
  return value;
}

function canonical(obj) {
  return JSON.stringify(normalise(obj));
}

function toHex(buffer) {
  return [...new Uint8Array(buffer)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function fromHex(hex) {
  return new Uint8Array(hex.match(/../g).map((h) => parseInt(h, 16)));
}

async function sha256Hex(bytes) {
  return toHex(await crypto.subtle.digest("SHA-256", bytes));
}

async function leafOf(obj) {
  return sha256Hex(new TextEncoder().encode(canonical(obj)));
}

async function digestOf(leaves) {
  const sorted = [...leaves].sort();
  const raw = new Uint8Array(sorted.length * 32);
  sorted.forEach((hex, i) => raw.set(fromHex(hex), i * 32));
  return sha256Hex(raw);
}

function memoHex(tx) {
  if (tx.memo_type !== "hash" || !tx.memo) return "";
  return toHex(Uint8Array.from(atob(tx.memo), (c) => c.charCodeAt(0)));
}

async function checkChain(anchors) {
  if (!anchors) return { status: "unanchored" };
  const localDigest = await digestOf(anchors.leaves);
  try {
    const resp = await fetch(HORIZON_TX_URL + anchors.tx_hash);
    if (!resp.ok) return { status: "unreachable", localDigest };
    const tx = await resp.json();
    const onChain = memoHex(tx);
    const ok = tx.successful && onChain === anchors.digest && localDigest === anchors.digest;
    return { status: ok ? "verified" : "tampered", onChain, localDigest };
  } catch (_e) {
    return { status: "unreachable", localDigest };
  }
}

async function checkFlag(flag) {
  const source = state.sources[flag.id];
  let sourceOk = null;
  if (flag.source_sha256) {
    sourceOk = source ? (await leafOf(source)) === flag.source_sha256 : false;
  }
  if (!state.anchors || !state.anchors.flag_ids.includes(flag.id)) {
    return { status: "unanchored", sourceOk, source };
  }
  const inAnchor = state.anchors.leaves.includes(await leafOf(flag));
  const chainOk = state.chain && state.chain.status === "verified";
  if (!inAnchor || sourceOk === false || (state.chain && state.chain.status === "tampered")) {
    return { status: "tampered", sourceOk, source };
  }
  return { status: chainOk ? "verified" : "pending", sourceOk, source };
}

function renderChain() {
  const panel = document.getElementById("chain");
  const a = state.anchors;
  const c = state.chain;
  if (!a) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  const statusText = !c ? "Consultando la red Stellar..."
    : c.status === "verified" ? "El registro publicado coincide con el anclado en Stellar."
    : c.status === "tampered" ? "El registro publicado no coincide con el anclado en Stellar."
    : "No se pudo consultar la red Stellar en este momento.";
  panel.className = `chain ${c ? c.status : "pending"}`;
  panel.innerHTML = `
    <strong>Registro de integridad en Stellar (testnet)</strong>
    <span>${statusText}</span>
    <span class="meta">Anclado: ${fmtTime(a.anchored_at)} &middot; ledger ${a.ledger}
      &middot; <a href="${a.explorer_url}" target="_blank" rel="noopener">ver transacción</a></span>
    <code title="Huella SHA-256 del conjunto publicado">${a.digest}</code>`;
}

function integrityCell(flag) {
  const result = state.integrity[flag.id] || { status: "pending" };
  const label = INTEGRITY_LABELS[result.status] || result.status;
  const captured = result.source ? `<small>Fuente capturada ${fmtTime(result.source.captured_at)}</small>` : "";
  const sourceWarn = result.sourceOk === false ? "<small>La copia de la fuente no coincide</small>" : "";
  return `<span class="integrity ${result.status}">${label}</span>${captured}${sourceWarn}`;
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

function uniqueSorted(items, key) {
  return [...new Set(items.map((f) => f[key]).filter(Boolean))].sort((a, b) => a.localeCompare(b, "es"));
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

function render() {
  const table = document.getElementById("flags");
  const empty = document.getElementById("empty");
  const tbody = table.querySelector("tbody");
  const count = document.getElementById("count");

  const filtered = state.flags.filter((flag) => matches(flag, currentFilters()));
  tbody.textContent = "";

  if (state.flags.length === 0) {
    empty.hidden = false;
    table.hidden = true;
    count.textContent = "";
    return;
  }

  empty.hidden = true;
  table.hidden = false;
  count.textContent = `${filtered.length} de ${state.flags.length} banderas`;

  for (const flag of filtered) {
    const tr = document.createElement("tr");
    const sev = flag.severity || "watch";
    const mult = flag.overprice_ratio ? `${flag.overprice_ratio.toFixed(1)}x` : "";
    const pct = typeof flag.overprice_pct === "number" ? `+${flag.overprice_pct}%` : "";
    const cells = [
      flag.comuna || "",
      flag.canonical_name || flag.sku_id || "",
      flag.category || "",
      { html: `<span class="num">${fmtClp(flag.unit_price_clp_gross)}</span>`, cls: "num" },
      { html: `<span class="num">${fmtClp(flag.reference_price_clp)}</span>`, cls: "num" },
      { html: `<span class="num mult">${pct} <small>(${mult})</small></span>`, cls: "num" },
      { html: `<span class="badge ${sev}">${SEV_LABELS[sev] || sev}</span>` },
      { html: flag.oc_url ? `<a href="${flag.oc_url}" target="_blank" rel="noopener">orden</a>` : "" },
      { html: integrityCell(flag), cls: "integrity-cell" },
    ];
    for (const cell of cells) {
      const td = document.createElement("td");
      if (typeof cell === "string") {
        td.textContent = cell;
      } else {
        td.innerHTML = cell.html;
        if (cell.cls) td.className = cell.cls;
      }
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
}

async function fetchJson(path, fallback) {
  try {
    const resp = await fetch(path, { cache: "no-store" });
    return resp.ok ? await resp.json() : fallback;
  } catch (_e) {
    return fallback;
  }
}

async function verify() {
  renderChain();
  state.chain = await checkChain(state.anchors);
  renderChain();
  for (const flag of state.flags) {
    state.integrity[flag.id] = await checkFlag(flag);
  }
  render();
}

async function load() {
  [state.flags, state.sources, state.anchors] = await Promise.all([
    fetchJson("./data/flags.json", []),
    fetchJson("./data/sources.json", {}),
    fetchJson("./data/anchors.json", null),
  ]);
  fillOptions("filter-comuna", uniqueSorted(state.flags, "comuna"));
  fillOptions("filter-categoria", uniqueSorted(state.flags, "category"));
  for (const id of ["filter-comuna", "filter-categoria", "filter-severidad"]) {
    document.getElementById(id).addEventListener("change", render);
  }
  render();
  verify();
}

load();
