"use strict";

const CHILE_TIME = new Intl.DateTimeFormat("es-CL", {
  timeZone: "America/Santiago", dateStyle: "medium", timeStyle: "short",
});
const UTC_TIME = new Intl.DateTimeFormat("es-CL", { timeZone: "UTC", timeStyle: "short" });

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

function base64Hex(b64) {
  return toHex(Uint8Array.from(atob(b64), (c) => c.charCodeAt(0)));
}

function memoHex(tx) {
  if (tx.memo_type !== "hash" || !tx.memo) return "";
  return base64Hex(tx.memo);
}
