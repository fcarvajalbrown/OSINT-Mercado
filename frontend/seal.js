"use strict";

const SEAL_SIZE = 240;
const SEAL_CENTER = SEAL_SIZE / 2;

function sealTicks(digestHex) {
  if (!digestHex || digestHex.length < 64) return "";
  const bytes = fromHex(digestHex.slice(0, 64));
  const inner = 74;
  return [...bytes].map((byte, i) => {
    const angle = (i / bytes.length) * Math.PI * 2 - Math.PI / 2;
    const length = 6 + (byte / 255) * 16;
    const x1 = SEAL_CENTER + Math.cos(angle) * inner;
    const y1 = SEAL_CENTER + Math.sin(angle) * inner;
    const x2 = SEAL_CENTER + Math.cos(angle) * (inner + length);
    const y2 = SEAL_CENTER + Math.sin(angle) * (inner + length);
    return `<line x1="${x1.toFixed(2)}" y1="${y1.toFixed(2)}" x2="${x2.toFixed(2)}" y2="${y2.toFixed(2)}"/>`;
  }).join("");
}

function sealSvg({ digest, ledger, status }) {
  const word = status === "verified" ? "VERIFICADO"
    : status === "tampered" ? "NO COINCIDE"
    : status === "unreachable" ? "SIN CONEXIÓN"
    : "COMPROBANDO";
  const ring = `OSINT-MERCADO • SELLADO EN STELLAR • LEDGER ${ledger || "?"} • `;
  return `
    <svg viewBox="0 0 ${SEAL_SIZE} ${SEAL_SIZE}" width="${SEAL_SIZE}" height="${SEAL_SIZE}" role="img">
      <defs>
        <path id="seal-ring-path" d="M ${SEAL_CENTER} ${SEAL_CENTER} m -96 0 a 96 96 0 1 1 192 0 a 96 96 0 1 1 -192 0"/>
      </defs>
      <circle class="seal-outer" cx="${SEAL_CENTER}" cy="${SEAL_CENTER}" r="112"/>
      <circle class="seal-inner" cx="${SEAL_CENTER}" cy="${SEAL_CENTER}" r="72"/>
      <text class="seal-ring"><textPath href="#seal-ring-path" textLength="596">${ring}</textPath></text>
      <g class="seal-ticks">${sealTicks(digest)}</g>
      <text class="seal-word" x="${SEAL_CENTER}" y="${SEAL_CENTER - 4}" text-anchor="middle">${word}</text>
      <text class="seal-digest" x="${SEAL_CENTER}" y="${SEAL_CENTER + 18}" text-anchor="middle">${digest ? digest.slice(0, 8) + "…" + digest.slice(-8) : ""}</text>
    </svg>`;
}

function renderSeal(element, { digest, ledger, status }) {
  element.className = `seal ${status}`;
  element.innerHTML = sealSvg({ digest, ledger, status });
}
