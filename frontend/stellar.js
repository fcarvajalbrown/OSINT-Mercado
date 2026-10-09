"use strict";

const HORIZON = "https://horizon-testnet.stellar.org";
const EXPLORER_TX = "https://stellar.expert/explorer/testnet/tx/";
const EXPLORER_ACCOUNT = "https://stellar.expert/explorer/testnet/account/";
const DATA_NAME = "osint-mercado";
const STROOPS_PER_XLM = 10000000;

const KNOWN_ANCHORS = {
  ad864ba7a7a7afd3c70092b176eb0fc6e5d5694da18f698f99884ecabab95e8f: {
    count: 4,
    note: "Primera publicación: 4 banderas, cada una con la huella de su línea de orden de compra.",
  },
  "3e1753bec726543200962631a0438eeb1be81a32a859f360d71b0d326a48222e": {
    note: "Ancla intermedia, hecha durante el trabajo en la copia del registro oficial.",
  },
  b5c8ebc4340b1190416fcf1b5cae6428a69de90f158a56767875f865e5425f95: {
    note: "Ancla intermedia, hecha durante el trabajo en la copia del registro oficial.",
  },
  c75cde2d1edab2d1c181ef219dd01c2740f81f50e999f66df1e01f88535d3d7f: {
    note: "Corrección: San Bernardo y Pirque se retiraron tras una revisión de sus precios de referencia, con la decisión anotada en el registro de curaduría. Las publicaciones anteriores siguen en la cadena.",
  },
};

const MONEY = new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 });
const MONEY_EXACT = new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 2 });
const PLAIN = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 7 });
const RATIO = new Intl.NumberFormat("es-CL", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const SEVERITY = { watch: "Moderada", high: "Alta", severe: "Severa" };

const demo = {
  flags: [],
  sources: {},
  anchors: null,
  selectedId: null,
  chain: { status: "pending" },
  history: { status: "pending", entries: [] },
  tamperSeq: 0,
};

let demoReady = null;

function esc(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  })[c]);
}

function money(n, exact) {
  if (typeof n !== "number" || !Number.isFinite(n)) return "-";
  return (exact ? MONEY_EXACT : MONEY).format(n);
}

function shortHex(hex, size = 10) {
  return hex ? `${hex.slice(0, size)}...${hex.slice(-6)}` : "";
}

function hexHtml(hex, reference, groupSize) {
  if (!hex) return "";
  let html = "";
  for (let i = 0; i < hex.length; i += groupSize || hex.length) {
    const chunk = hex.slice(i, i + (groupSize || hex.length));
    let inner = "";
    for (let j = 0; j < chunk.length; j += 1) {
      const ch = chunk[j];
      const differs = reference && reference[i + j] !== ch;
      inner += differs ? `<span class="d">${ch}</span>` : ch;
    }
    html += groupSize ? `<span class="g">${inner}</span>` : inner;
  }
  return html;
}

function highlightJson(json, marks) {
  let html = esc(json);
  for (const mark of marks) {
    const needle = esc(mark);
    if (needle && html.includes(needle)) html = html.replace(needle, `<mark>${needle}</mark>`);
  }
  return html;
}

function editedPair(flag, source, edits) {
  const nextFlag = { ...flag };
  const nextSource = source ? { ...source } : null;
  if (edits && edits.paid !== undefined) nextFlag.unit_price_clp_gross = edits.paid;
  if (nextSource && edits && edits.unit !== undefined) nextSource.unit_price = edits.unit;
  return { flag: nextFlag, source: nextSource };
}

async function evaluate(flag, source, anchors, chainDigest, edits) {
  const pair = editedPair(flag, source, edits);
  const sourceHash = pair.source ? await leafOf(pair.source) : null;
  const sourceOk = pair.source ? sourceHash === flag.source_sha256 : null;
  const leaf = await leafOf(pair.flag);
  const index = anchors ? anchors.flag_ids.indexOf(flag.id) : -1;
  const expectedLeaf = index >= 0 ? anchors.leaves[index] : null;
  const leaves = anchors ? anchors.leaves.map((value, i) => (i === index ? leaf : value)) : [leaf];
  const digest = await digestOf(leaves);
  const target = chainDigest || (anchors ? anchors.digest : null);
  const leafOk = leaf === expectedLeaf;
  const digestOk = digest === target;
  return {
    sourceHash,
    expectedSource: flag.source_sha256 || null,
    sourceOk,
    leaf,
    expectedLeaf,
    leafOk,
    digest,
    target,
    targetOnChain: Boolean(chainDigest),
    digestOk,
    ok: sourceOk !== false && leafOk && digestOk,
  };
}

function historyEntries(records, anchors) {
  const entries = [];
  for (const op of records || []) {
    const tx = op.transaction || {};
    const base = {
      hash: op.transaction_hash,
      ledger: tx.ledger,
      createdAt: op.created_at || tx.created_at,
      fee: tx.fee_charged,
    };
    if (op.type === "create_account") {
      entries.push({ ...base, kind: "create", balance: op.starting_balance });
    } else if (op.type === "manage_data" && op.name === DATA_NAME && op.value) {
      const value = base64Hex(op.value);
      const memo = memoHex(tx);
      const known = KNOWN_ANCHORS[op.transaction_hash] || {};
      const current = Boolean(anchors && op.transaction_hash === anchors.tx_hash);
      entries.push({
        ...base,
        kind: "anchor",
        digest: value,
        memo,
        memoMatches: memo === value,
        current,
        count: current ? anchors.leaves.length : known.count ?? null,
        note: known.note || "",
      });
    }
  }
  return entries;
}

function selectedFlag() {
  return demo.flags.find((f) => f.id === demo.selectedId) || demo.flags[0] || null;
}

function el(id) {
  return document.getElementById(id);
}

function setHtml(id, html) {
  const node = el(id);
  if (!node) return;
  node.scrambleToken = (node.scrambleToken || 0) + 1;
  node.innerHTML = html;
}

function checkLine(ok, yes, no) {
  if (ok === null || ok === undefined) return `<span class="pill muted">${esc(no)}</span>`;
  return ok ? `<span class="pill ok">Coincide</span> ${esc(yes)}` : `<span class="pill bad">No coincide</span> ${esc(no)}`;
}

function renderPicker() {
  const html = demo.flags.map((f) => {
    const pressed = f.id === demo.selectedId ? "true" : "false";
    return `<button type="button" class="chip" data-flag="${esc(f.id)}" aria-pressed="${pressed}">${esc(f.comuna)} <small>${esc(f.canonical_name)}</small></button>`;
  }).join("");
  setHtml("picker", html);
}

function renderCards() {
  const flag = selectedFlag();
  if (!flag) {
    setHtml("flag-card", "<p>No hay banderas publicadas.</p>");
    setHtml("source-card", "");
    return;
  }
  const source = demo.sources[flag.id];
  const sev = flag.severity || "watch";
  setHtml("flag-card", `
    <span class="label">Bandera publicada</span>
    <h4>${esc(flag.comuna)}: ${esc(flag.canonical_name)}</h4>
    <dl class="kv">
      <dt>Pagado por unidad (con IVA)</dt><dd class="num strong">${money(flag.unit_price_clp_gross)}</dd>
      <dt>Precio de referencia</dt><dd class="num">${money(flag.reference_price_clp)}</dd>
      <dt>Sobreprecio</dt><dd class="num">+${esc(flag.overprice_pct)}% <small>(${typeof flag.overprice_ratio === "number" ? RATIO.format(flag.overprice_ratio) : "-"}x)</small></dd>
      <dt>Severidad</dt><dd><span class="badge ${esc(sev)}">${esc(SEVERITY[sev] || sev)}</span></dd>
      <dt>Revisada</dt><dd>${esc(flag.reviewed_at)}</dd>
      <dt>Identificador</dt><dd><code>${esc(flag.id)}</code></dd>
    </dl>`);
  if (!source) {
    setHtml("source-card", `<span class="label">Línea de la orden de compra</span><p>Esta bandera no tiene una línea capturada publicada.</p>`);
    return;
  }
  const supplier = source.espec_proveedor ? `<dt>Ofrecido por el proveedor</dt><dd>${esc(source.espec_proveedor)}</dd>` : "";
  setHtml("source-card", `
    <span class="label">Línea de la orden de compra, capturada</span>
    <h4>${esc(source.buyer_name)}</h4>
    <dl class="kv">
      <dt>Orden y línea</dt><dd><code>${esc(source.oc_id)}</code>, línea ${esc(source.correlativo)}</dd>
      <dt>Pedido por el municipio</dt><dd>${esc(source.espec_comprador)}</dd>
      ${supplier}
      <dt>Cantidad</dt><dd class="num">${esc(source.quantity)}</dd>
      <dt>Precio unitario (sin IVA)</dt><dd class="num strong">${money(source.unit_price, true)}</dd>
      <dt>IVA</dt><dd class="num">${esc(source.porcentaje_iva)}%</dd>
      <dt>Estado de la orden</dt><dd>${esc(source.estado)}</dd>
      <dt>Capturada</dt><dd>${esc(fmtTime(source.captured_at))}</dd>
    </dl>
    <p class="meta"><a href="${esc(source.oc_url)}" target="_blank" rel="noopener">Ficha oficial en Mercado Público</a> (puede pedir inicio de sesión)</p>`);
}

async function renderHashes() {
  const flag = selectedFlag();
  if (!flag) return;
  const source = demo.sources[flag.id];
  const result = await evaluate(flag, source, demo.anchors, null, {});
  if (source) {
    setHtml("source-json", highlightJson(canonical(source), [`"unit_price":${canonical(source.unit_price)}`]));
    setHtml("source-hash", hexHtml(result.sourceHash));
  } else {
    setHtml("source-json", "");
    setHtml("source-hash", "");
  }
  setHtml("source-check", checkLine(result.sourceOk, "con source_sha256 guardado en la bandera.", "sin línea capturada para comparar."));
  setHtml("flag-json", highlightJson(canonical(flag), [
    `"source_sha256":"${flag.source_sha256 || ""}"`,
    `"unit_price_clp_gross":${canonical(flag.unit_price_clp_gross)}`,
  ]));
  setHtml("flag-hash", hexHtml(result.leaf));
  setHtml("flag-check", checkLine(result.leafOk, "con la huella registrada en anchors.json.", "con la huella registrada en anchors.json."));
}

async function renderMerge() {
  const a = demo.anchors;
  if (!a) {
    setHtml("leaves", "<li>No hay un ancla publicada.</li>");
    return;
  }
  const local = {};
  for (const flag of demo.flags) local[flag.id] = await leafOf(flag);
  const rows = a.leaves.map((leaf, i) => ({ leaf, id: a.flag_ids[i] }))
    .sort((x, y) => (x.leaf < y.leaf ? -1 : x.leaf > y.leaf ? 1 : 0));
  const html = rows.map((row, i) => {
    const flag = demo.flags.find((f) => f.id === row.id);
    const name = flag ? `${flag.comuna}: ${flag.canonical_name}` : row.id;
    const selected = row.id === demo.selectedId ? " selected" : "";
    const match = local[row.id] === row.leaf;
    return `<li class="leaf${selected}">
      <span class="leaf-order">${i + 1}</span>
      <span class="leaf-name">${esc(name)}</span>
      <code class="hex">${hexHtml(row.leaf)}</code>
      <span class="pill ${match ? "ok" : "bad"}">${match ? "Recalculada" : "No coincide"}</span>
    </li>`;
  }).join("");
  setHtml("leaves", html);
  setHtml("merge-join", `<span class="label">Unidas en orden: ${a.leaves.length} x 32 bytes = ${a.leaves.length * 32} bytes</span>`);
  const digest = await digestOf(a.leaves);
  setHtml("digest", hexHtml(digest));
  setHtml("digest-check", checkLine(digest === a.digest, "con la huella guardada en anchors.json.", "con la huella guardada en anchors.json."));
}

function renderCompare(localDigest) {
  const c = demo.chain;
  const onChain = c.memo || "";
  setHtml("cmp-local", hexHtml(localDigest, onChain || null, 8));
  setHtml("cmp-chain", onChain ? hexHtml(onChain, localDigest, 8) : `<span class="muted">${c.status === "pending" ? "Consultando..." : "Sin respuesta"}</span>`);
  const verdict = el("cmp-verdict");
  const box = el("compare");
  let text = "Consultando Stellar...";
  let cls = "pending";
  if (c.status === "error") {
    text = "No se pudo consultar Horizon";
    cls = "error";
  } else if (c.status === "ok") {
    const ok = c.successful && onChain === localDigest;
    text = ok ? "Coinciden" : "No coinciden";
    cls = ok ? "ok" : "bad";
  }
  if (verdict) verdict.textContent = text;
  if (box) box.className = `compare ${cls}`;
}

function renderFacts() {
  const a = demo.anchors;
  const c = demo.chain;
  if (!a) {
    setHtml("tx-facts", "");
    return;
  }
  const fee = c.fee ? `${esc(c.fee)} stroops (${esc(PLAIN.format(Number(c.fee) / STROOPS_PER_XLM))} XLM de prueba)` : "...";
  const data = c.accountData
    ? `${checkLine(c.accountData === a.digest, "con la huella anclada.", "con la huella anclada.")}`
    : "...";
  setHtml("tx-facts", `
    <div><dt>Transacción</dt><dd><code>${esc(shortHex(a.tx_hash, 16))}</code></dd></div>
    <div><dt>Ledger</dt><dd>${esc(c.ledger || a.ledger)}</dd></div>
    <div><dt>Fecha</dt><dd>${esc(fmtTime(c.createdAt || a.anchored_at))}</dd></div>
    <div><dt>Cuenta</dt><dd><code>${esc(shortHex(a.account, 8))}</code></dd></div>
    <div><dt>Comisión</dt><dd>${fee}</dd></div>
    <div><dt>Dato "${DATA_NAME}" de la cuenta</dt><dd>${data}</dd></div>`);
  setHtml("tx-actions", `
    <a class="btn" href="${EXPLORER_TX}${esc(a.tx_hash)}" target="_blank" rel="noopener">Ver la transacción en Stellar Expert</a>
    <a class="btn ghost" href="${HORIZON}/transactions/${esc(a.tx_hash)}" target="_blank" rel="noopener">Respuesta original de Horizon</a>
    ${c.status === "error" ? "<button type=\"button\" class=\"btn\" data-action=\"retry\">Reintentar</button>" : ""}`);
}

async function renderChainStep() {
  const localDigest = demo.anchors ? await digestOf(demo.anchors.leaves) : "";
  renderCompare(localDigest);
  renderFacts();
}

function readEdits() {
  const edits = {};
  const flag = selectedFlag();
  const source = flag ? demo.sources[flag.id] : null;
  const paid = el("edit-paid");
  const unit = el("edit-unit");
  if (flag && paid && String(paid.value) !== String(flag.unit_price_clp_gross)) {
    edits.paid = String(paid.value).trim() === "" ? null : Number(paid.value);
  }
  if (source && unit && String(unit.value) !== String(source.unit_price)) {
    edits.unit = String(unit.value).trim() === "" ? null : Number(unit.value);
  }
  return edits;
}

function fillTamperInputs() {
  const flag = selectedFlag();
  if (!flag) return;
  const source = demo.sources[flag.id];
  const paid = el("edit-paid");
  const unit = el("edit-unit");
  if (paid) paid.value = String(flag.unit_price_clp_gross);
  if (unit) {
    unit.value = source ? String(source.unit_price) : "";
    unit.disabled = !source;
  }
  setHtml("tamper-target", `Bandera: <strong>${esc(flag.comuna)}: ${esc(flag.canonical_name)}</strong>`);
}

function checkItem(title, computed, expected, ok, expectedLabel) {
  const status = ok === null ? "muted" : ok ? "ok" : "bad";
  const label = ok === null ? "Sin dato" : ok ? "Coincide" : "No coincide";
  return `<li class="check-item ${status}">
    <div class="check-title"><span class="pill ${status}">${label}</span> ${esc(title)}</div>
    <div class="check-hex"><span class="label">Calculada ahora</span><code class="hex">${hexHtml(computed, expected)}</code></div>
    <div class="check-hex"><span class="label">${esc(expectedLabel)}</span><code class="hex">${hexHtml(expected)}</code></div>
  </li>`;
}

async function applyTamper() {
  const flag = selectedFlag();
  if (!flag || !demo.anchors) return null;
  const seq = ++demo.tamperSeq;
  const edits = readEdits();
  const chainDigest = demo.chain.status === "ok" ? demo.chain.memo : null;
  const result = await evaluate(flag, demo.sources[flag.id], demo.anchors, chainDigest, edits);
  if (seq !== demo.tamperSeq) return result;
  const edited = Object.keys(edits).length > 0;
  const shownPrice = edits.paid !== undefined ? edits.paid : flag.unit_price_clp_gross;
  const status = result.ok ? "verified" : "tampered";
  const row = el("tamper-row");
  if (row) row.className = `row-preview ${status}${edited ? " edited" : ""}`;
  setHtml("tamper-row", `
    <span class="row-name">${esc(flag.comuna)}: ${esc(flag.canonical_name)}</span>
    <span class="row-price num">${money(shownPrice, true)}</span>
    <span class="integrity ${status}">${result.ok ? "Verificado" : "Alterado"}</span>`);
  const targetLabel = result.targetOnChain ? "Memo en Stellar" : "Huella en anchors.json (Stellar sin respuesta)";
  setHtml("tamper-checks", [
    checkItem("Huella de la línea capturada", result.sourceHash, result.expectedSource, result.sourceOk, "source_sha256 en la bandera"),
    checkItem("Huella de la bandera", result.leaf, result.expectedLeaf, result.leafOk, "Huella anclada"),
    checkItem("Huella del conjunto", result.digest, result.target, result.digestOk, targetLabel),
  ].join(""));
  return result;
}

function resetTamper() {
  fillTamperInputs();
  return applyTamper();
}

function renderHistory() {
  const h = demo.history;
  const a = demo.anchors;
  if (a) {
    setHtml("account-line", `Cuenta <a href="${EXPLORER_ACCOUNT}${esc(a.account)}" target="_blank" rel="noopener"><code>${esc(a.account)}</code></a>`);
  }
  if (h.status === "pending") {
    setHtml("timeline", "<li class=\"tl-item muted\">Consultando Horizon...</li>");
    return;
  }
  if (h.status === "error") {
    setHtml("timeline", "<li class=\"tl-item muted\">No se pudo consultar el historial en Horizon.</li>");
    setHtml("timeline-actions", "<button type=\"button\" class=\"btn\" data-action=\"retry\">Reintentar</button>");
    return;
  }
  setHtml("timeline-actions", "");
  let previousCount = null;
  const html = h.entries.map((entry) => {
    const when = esc(fmtTime(entry.createdAt));
    const link = `<a href="${EXPLORER_TX}${esc(entry.hash)}" target="_blank" rel="noopener"><code>${esc(shortHex(entry.hash, 12))}</code></a>`;
    if (entry.kind === "create") {
      return `<li class="tl-item create">
        <div class="tl-dot" aria-hidden="true"></div>
        <div class="tl-body">
          <p class="tl-title">Cuenta creada en testnet</p>
          <p class="meta">${when} &middot; ledger ${esc(entry.ledger)} &middot; ${link}</p>
          <p>Fondos de prueba: ${esc(PLAIN.format(Number(entry.balance)))} XLM de testnet, sin valor real.</p>
        </div>
      </li>`;
    }
    const count = entry.count === null ? "" : `<span class="tl-count${previousCount !== null && entry.count < previousCount ? " down" : ""}">${previousCount !== null && entry.count !== previousCount ? `<s>${previousCount}</s> ` : ""}${entry.count} ${entry.count === 1 ? "bandera" : "banderas"}</span>`;
    if (entry.count !== null) previousCount = entry.count;
    const badge = entry.current ? "<span class=\"pill ok\">Vigente en este sitio</span>" : "";
    const memo = entry.memoMatches ? "Memo y entrada manage_data con la misma huella" : "Memo y entrada manage_data distintos";
    return `<li class="tl-item anchor${entry.current ? " current" : ""}">
      <div class="tl-dot" aria-hidden="true"></div>
      <div class="tl-body">
        <p class="tl-title">Ancla ${count} ${badge}</p>
        <p class="meta">${when} &middot; ledger ${esc(entry.ledger)} &middot; ${link} &middot; comisión ${esc(entry.fee)} stroops</p>
        <code class="hex">${hexHtml(entry.digest)}</code>
        <p class="meta">${memo}</p>
        ${entry.note ? `<p class="tl-note">${esc(entry.note)}</p>` : ""}
      </div>
    </li>`;
  }).join("");
  setHtml("timeline", html || "<li class=\"tl-item muted\">Sin transacciones.</li>");
}

async function getJson(url, options) {
  const resp = await fetch(url, options);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

async function fetchJson(path, fallback) {
  try {
    return await getJson(path, { cache: "no-store" });
  } catch (_e) {
    return fallback;
  }
}

async function loadChain() {
  const a = demo.anchors;
  if (!a) {
    demo.chain = { status: "error" };
    demo.history = { status: "error", entries: [] };
    return;
  }
  demo.chain = { status: "pending" };
  demo.history = { status: "pending", entries: [] };
  await renderChainStep();
  renderHistory();
  const account = encodeURIComponent(a.account);
  const [tx, acct, ops] = await Promise.allSettled([
    getJson(`${HORIZON}/transactions/${encodeURIComponent(a.tx_hash)}`),
    getJson(`${HORIZON}/accounts/${account}`),
    getJson(`${HORIZON}/accounts/${account}/operations?order=asc&limit=200&join=transactions`),
  ]);
  if (tx.status === "fulfilled") {
    const t = tx.value;
    const dataValue = acct.status === "fulfilled" && acct.value.data ? acct.value.data[DATA_NAME] : null;
    demo.chain = {
      status: "ok",
      memo: memoHex(t),
      successful: Boolean(t.successful),
      ledger: t.ledger,
      createdAt: t.created_at,
      fee: t.fee_charged,
      accountData: dataValue ? base64Hex(dataValue) : null,
    };
  } else {
    demo.chain = { status: "error" };
  }
  if (ops.status === "fulfilled") {
    const records = (ops.value._embedded && ops.value._embedded.records) || [];
    demo.history = { status: "ok", entries: historyEntries(records, a) };
  } else {
    demo.history = { status: "error", entries: [] };
  }
  await renderChainStep();
  renderHistory();
  await applyTamper();
}

async function selectFlag(id) {
  demo.selectedId = id;
  renderPicker();
  renderCards();
  fillTamperInputs();
  await Promise.all([renderHashes(), renderMerge(), applyTamper()]);
}

function reduceMotion() {
  return typeof matchMedia !== "function" || matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function scramble(node) {
  if (reduceMotion() || typeof requestAnimationFrame !== "function" || !node.textContent) return;
  const finalHtml = node.innerHTML;
  const finalText = node.textContent;
  const token = (node.scrambleToken || 0) + 1;
  node.scrambleToken = token;
  const start = performance.now();
  const duration = 650;
  const digits = "0123456789abcdef";
  const step = (now) => {
    if (node.scrambleToken !== token || node.textContent.length !== finalText.length) return;
    const done = Math.min(1, (now - start) / duration);
    const fixed = Math.floor(done * finalText.length);
    if (done >= 1) {
      node.innerHTML = finalHtml;
      return;
    }
    let text = finalText.slice(0, fixed);
    for (let i = fixed; i < finalText.length; i += 1) text += digits[Math.floor(Math.random() * 16)];
    node.textContent = text;
    requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function setupReveal() {
  const steps = [...document.querySelectorAll(".step")];
  const chips = [...document.querySelectorAll("#stepper a")];
  if (typeof IntersectionObserver !== "function") return;
  document.body.classList.add("js-reveal");
  const reveal = new IntersectionObserver((items) => {
    for (const item of items) {
      if (!item.isIntersecting) continue;
      item.target.classList.add("is-visible");
      item.target.querySelectorAll(".hex-out").forEach(scramble);
      reveal.unobserve(item.target);
    }
  }, { threshold: 0.15 });
  const active = new IntersectionObserver((items) => {
    for (const item of items) {
      if (!item.isIntersecting) continue;
      const step = item.target.dataset.step;
      chips.forEach((chip) => chip.classList.toggle("active", chip.dataset.step === step));
    }
  }, { rootMargin: "-40% 0px -55% 0px" });
  steps.forEach((s) => {
    reveal.observe(s);
    active.observe(s);
  });
}

function jumpStep(delta) {
  const steps = [...document.querySelectorAll(".step")];
  if (!steps.length) return;
  const marker = window.innerHeight * 0.3;
  let index = steps.findIndex((s) => s.getBoundingClientRect().top > marker);
  index = index === -1 ? steps.length : index;
  const target = delta > 0 ? steps[index] : steps[Math.max(0, index - 2)];
  if (target) target.scrollIntoView({ behavior: reduceMotion() ? "auto" : "smooth", block: "start" });
}

function bindEvents() {
  const picker = el("picker");
  if (picker) {
    picker.addEventListener("click", (event) => {
      const button = event.target.closest("[data-flag]");
      if (button) selectFlag(button.dataset.flag);
    });
  }
  for (const id of ["edit-paid", "edit-unit"]) {
    const input = el(id);
    if (input) input.addEventListener("input", () => applyTamper());
  }
  const reset = el("tamper-reset");
  if (reset) reset.addEventListener("click", () => resetTamper());
  const form = el("tamper-form");
  if (form) form.addEventListener("submit", (event) => event.preventDefault());
  document.addEventListener("click", (event) => {
    if (event.target.closest && event.target.closest("[data-action=retry]")) loadChain();
  });
  document.addEventListener("keydown", (event) => {
    const tag = event.target && event.target.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    if (event.key === "ArrowRight") jumpStep(1);
    if (event.key === "ArrowLeft") jumpStep(-1);
  });
}

async function init() {
  [demo.flags, demo.sources, demo.anchors] = await Promise.all([
    fetchJson("./data/flags.json", []),
    fetchJson("./data/sources.json", {}),
    fetchJson("./data/anchors.json", null),
  ]);
  demo.selectedId = demo.flags.length ? demo.flags[0].id : null;
  bindEvents();
  await selectFlag(demo.selectedId);
  setupReveal();
  await loadChain();
}

if (typeof document !== "undefined" && document.getElementById("demo")) {
  demoReady = init();
}
