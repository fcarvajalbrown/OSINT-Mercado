import { readFileSync } from "node:fs";
import { join } from "node:path";
import vm from "node:vm";

const [siteDir] = process.argv.slice(2);
const read = (name) => JSON.parse(readFileSync(join(siteDir, "data", name), "utf-8"));

const element = () => new Proxy({}, {
  get: (target, key) => (key in target ? target[key] : key === "querySelector" ? element : () => element()),
  set: (target, key, value) => { target[key] = value; return true; },
});

const context = vm.createContext({
  crypto: globalThis.crypto,
  TextEncoder,
  atob,
  Intl,
  console,
  fetch: () => Promise.reject(new Error("offline")),
  document: { getElementById: element, createElement: element },
});
for (const script of ["shared.js", "seal.js", "app.js"]) {
  vm.runInContext(readFileSync(join(siteDir, script), "utf-8"), context);
}

const flags = read("flags.json");
const sources = read("sources.json");
const anchors = read("anchors.json");

const failures = [];
let mirrored = 0;
for (const [i, flag] of flags.entries()) {
  const leaf = await context.leafOf(flag);
  if (leaf !== anchors.leaves[i]) failures.push(`flag ${flag.id}: leaf ${leaf} != ${anchors.leaves[i]}`);
  const source = sources[flag.id];
  if (source && (await context.leafOf(source)) !== flag.source_sha256) {
    failures.push(`flag ${flag.id}: source hash mismatch`);
  }
  if (flag.mirror_sha256) {
    const mirror = read(join("mirror", `${flag.oc_id}.json`));
    if ((await context.leafOf(mirror)) !== flag.mirror_sha256) {
      failures.push(`flag ${flag.id}: mirror hash mismatch`);
    }
    mirrored += 1;
  }
}
let leadCount = 0;
try {
  const leads = read("leads.json");
  const anchored = new Set(anchors.leaves);
  const withheld = ["overprice_ratio", "ratio", "severity", "reference_price_clp", "cm_reference_per_unit",
    "peer_median_clp", "mad_clp", "robust_z", "overprice_pct"];
  for (const lead of leads) {
    const leak = withheld.filter((k) => k in lead);
    if (leak.length) failures.push(`lead ${lead.id}: estimate field published (${leak.join(", ")})`);
    if (anchors.flag_ids.includes(lead.id) && !anchored.has(await context.leafOf(lead))) {
      failures.push(`lead ${lead.id}: not in the anchored leaves`);
    }
    leadCount += 1;
  }
} catch (e) {
  if (e.code !== "ENOENT") throw e;
}
const digest = await context.digestOf(anchors.leaves);
if (digest !== anchors.digest) failures.push(`digest ${digest} != ${anchors.digest}`);

if (failures.length) {
  console.log(failures.join("\n"));
  process.exit(1);
}
console.log(`parity ok: ${flags.length} flags, ${Object.keys(sources).length} sources, ${mirrored} mirrors, ${leadCount} leads, digest ${digest}`);
