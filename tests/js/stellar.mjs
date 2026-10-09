import { readFileSync } from "node:fs";
import { join } from "node:path";
import vm from "node:vm";

const [siteDir] = process.argv.slice(2);
const read = (name) => JSON.parse(readFileSync(join(siteDir, "data", name), "utf-8"));
const flags = read("flags.json");
const sources = read("sources.json");
const anchors = read("anchors.json");
const HORIZON = "https://horizon-testnet.stellar.org";
const b64 = (hex) => Buffer.from(hex, "hex").toString("base64");

class FakeElement {
  constructor(id) {
    this.id = id;
    this.innerHTML = "";
    this.textContent = "";
    this.value = "";
    this.disabled = false;
    this.className = "";
    this.dataset = {};
    this.listeners = {};
    this.classList = { add() {}, remove() {}, toggle() {} };
  }

  addEventListener(type, fn) {
    (this.listeners[type] ||= []).push(fn);
  }

  async fire(type, event = {}) {
    for (const fn of this.listeners[type] || []) await fn({ target: this, preventDefault() {}, ...event });
  }

  querySelectorAll() {
    return [];
  }
}

const nodes = new Map();
const node = (id) => {
  if (!nodes.has(id)) nodes.set(id, new FakeElement(id));
  return nodes.get(id);
};

const chainTx = {
  hash: anchors.tx_hash,
  successful: true,
  ledger: anchors.ledger,
  created_at: anchors.anchored_at,
  fee_charged: "100",
  memo_type: "hash",
  memo: b64(anchors.digest),
};
const horizon = {
  [`${HORIZON}/transactions/${anchors.tx_hash}`]: chainTx,
  [`${HORIZON}/accounts/${anchors.account}`]: { data: { "osint-mercado": b64(anchors.digest) } },
  [`${HORIZON}/accounts/${anchors.account}/operations?order=asc&limit=200&join=transactions`]: {
    _embedded: {
      records: [
        { type: "create_account", transaction_hash: "f".repeat(64), created_at: "2026-10-09T21:04:12Z", starting_balance: "10000.0000000", transaction: { ledger: 1, fee_charged: "100", memo_type: "none" } },
        { type: "manage_data", name: "osint-mercado", value: b64(anchors.digest), transaction_hash: anchors.tx_hash, created_at: anchors.anchored_at, transaction: chainTx },
      ],
    },
  },
};

const respond = (body) => Promise.resolve({ ok: body !== undefined, status: body === undefined ? 404 : 200, json: async () => body });
const fetchStub = (url) => {
  if (url.startsWith("./data/")) return respond(read(url.slice("./data/".length)));
  return respond(horizon[url]);
};

const context = vm.createContext({
  crypto: globalThis.crypto,
  TextEncoder,
  atob,
  Intl,
  console,
  performance,
  fetch: fetchStub,
  document: {
    getElementById: node,
    querySelectorAll: () => [],
    addEventListener() {},
    body: { classList: { add() {} } },
  },
});
for (const script of ["shared.js", "stellar.js"]) {
  vm.runInContext(readFileSync(join(siteDir, script), "utf-8"), context);
}
await vm.runInContext("demoReady", context);

const failures = [];
const expect = (cond, message) => {
  if (!cond) failures.push(message);
};
const plain = (html) => html.replace(/<[^>]+>/g, "");

for (const [i, flag] of flags.entries()) {
  const leaf = await context.leafOf(flag);
  expect(leaf === anchors.leaves[i], `flag ${flag.id}: leaf ${leaf} != ${anchors.leaves[i]}`);
  const clean = await context.evaluate(flag, sources[flag.id], anchors, anchors.digest, {});
  expect(clean.ok && clean.digest === anchors.digest, `flag ${flag.id}: untouched data does not verify`);
  expect(clean.sourceHash === flag.source_sha256, `flag ${flag.id}: source hash mismatch`);

  const paid = await context.evaluate(flag, sources[flag.id], anchors, anchors.digest, { paid: flag.reference_price_clp });
  expect(!paid.ok && !paid.leafOk && !paid.digestOk && paid.sourceOk, `flag ${flag.id}: paid-price edit not caught at leaf and digest`);

  const unit = await context.evaluate(flag, sources[flag.id], anchors, anchors.digest, { unit: 1 });
  expect(!unit.ok && unit.sourceOk === false && unit.leafOk, `flag ${flag.id}: source-price edit not caught at the source hash`);

  const forged = await context.evaluate(flag, sources[flag.id], anchors, "0".repeat(64), {});
  expect(!forged.ok && !forged.digestOk, `flag ${flag.id}: a different on-chain digest is not caught`);

  await vm.runInContext(`selectFlag(${JSON.stringify(flag.id)})`, context);
  expect(plain(node("flag-hash").innerHTML) === anchors.leaves[i], `flag ${flag.id}: step 2 shows a different leaf`);
  expect(plain(node("source-hash").innerHTML) === flag.source_sha256, `flag ${flag.id}: step 2 shows a different source hash`);
  expect(node("tamper-row").innerHTML.includes("Verificado"), `flag ${flag.id}: untouched row is not Verificado`);

  node("edit-paid").value = String(flag.reference_price_clp);
  await node("edit-paid").fire("input");
  expect(node("tamper-row").innerHTML.includes("Alterado"), `flag ${flag.id}: edited paid price does not turn the row Alterado`);
  expect(node("tamper-checks").innerHTML.includes("No coincide"), `flag ${flag.id}: edited paid price shows no failing check`);

  await node("tamper-reset").fire("click");
  expect(node("tamper-row").innerHTML.includes("Verificado"), `flag ${flag.id}: reset does not restore Verificado`);
  expect(node("edit-paid").value === String(flag.unit_price_clp_gross), `flag ${flag.id}: reset does not restore the price`);

  node("edit-unit").value = "1";
  await node("edit-unit").fire("input");
  expect(node("tamper-row").innerHTML.includes("Alterado"), `flag ${flag.id}: edited source price does not turn the row Alterado`);
  await node("tamper-reset").fire("click");
}

expect(plain(node("digest").innerHTML) === anchors.digest, "step 3 digest differs from anchors.json");
const leafList = node("leaves").innerHTML;
const leafItems = (leafList.match(/<li /g) || []).length;
expect(leafItems <= flags.length + 7, `step 3 lists ${leafItems} entries; it must show a sample, not every sealed row`);
expect(!leafList.includes("No coincide"), "step 3 marks a sealed entry as No coincide");
if (anchors.leaves.length > flags.length + 6) expect(leafList.includes("huellas más"), "step 3 does not state how many entries are left out");
expect(node("cmp-verdict").textContent === "Coinciden", `step 4 verdict is "${node("cmp-verdict").textContent}"`);

const history = context.historyEntries(horizon[`${HORIZON}/accounts/${anchors.account}/operations?order=asc&limit=200&join=transactions`]._embedded.records, anchors);
const current = history.find((e) => e.current);
expect(history.length === 2 && history[0].kind === "create", "history does not list the account creation");
expect(current && current.count === anchors.leaves.length && current.memoMatches && current.digest === anchors.digest, "history does not mark the current anchor");
expect(node("timeline").innerHTML.includes("Vigente"), "timeline does not render the current anchor");

if (failures.length) {
  console.log(failures.join("\n"));
  process.exit(1);
}
console.log(`stellar page ok: ${flags.length} flags, tamper paths caught, digest ${anchors.digest}`);
