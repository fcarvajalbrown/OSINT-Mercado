"use strict";

const state = { flags: [] };

const CLP = new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 });
const SEV_LABELS = { watch: "Moderada", high: "Alta", severe: "Severa" };

function fmtClp(n) {
  return typeof n === "number" ? CLP.format(Math.round(n)) : "-";
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

async function load() {
  try {
    const resp = await fetch("./data/flags.json", { cache: "no-store" });
    state.flags = resp.ok ? await resp.json() : [];
  } catch (_e) {
    state.flags = [];
  }
  fillOptions("filter-comuna", uniqueSorted(state.flags, "comuna"));
  fillOptions("filter-categoria", uniqueSorted(state.flags, "category"));
  for (const id of ["filter-comuna", "filter-categoria", "filter-severidad"]) {
    document.getElementById(id).addEventListener("change", render);
  }
  render();
}

load();
