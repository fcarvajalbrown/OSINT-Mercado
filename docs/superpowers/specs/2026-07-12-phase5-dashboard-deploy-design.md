# Phase 5 — Static dashboard & deploy (design spec)

**Date:** 2026-07-12
**Status:** Approved (design ratification + live deploy deferred to end-of-run), ready for implementation
**Shaped by:** ADR 0001, 0003 (transport superseded here), 0004, 0007; new ADR 0015

## Goal

Publish the human-confirmed flags on a static, verifiable public dashboard, built in GitHub
Actions and deployed to Hostinger over SSH. Readers filter confirmed flags by commune,
category, and severity; each row shows unit-paid (gross CLP) vs baseline, overprice %,
severity, and a link back to the official Mercado Público order (ADR 0007). All filtering is
client-side (no server, per ADR 0001).

## Components

### Basket category (small enabling change)
The PRD requires category filtering, but SKUs carry no category. Add a `category` field to
each SKU in `data/basket.json` and to `basket.Sku` (default ""). Three coarse groups:
"Oficina y computación", "Seguridad y EPP", "Limpieza".

### `build_site.py` (`osint-build-site`)
- `build_flags(confirmed: list[dict], skus: list[Sku]) -> list[dict]`: enrich each confirmed
  flag with `canonical_name`, `category` (from the SKU), and `overprice_pct =
  round((overprice_ratio - 1) * 100)`. Deterministic ordering. Pure; TDD'd.
- `build(confirmed_path, basket_path, frontend_dir, out_dir)`: copy the static frontend
  assets to `out_dir` (default `dist/`) and write `out_dir/data/flags.json` from
  `build_flags`. No network, no external runtime deps.

### Frontend (`frontend/`, static, self-contained)
- `index.html`, `app.js`, `styles.css`. On load, fetch `./data/flags.json`, render a table,
  and filter client-side by commune / category / severity. Empty state ("no confirmed flags
  yet") when the dataset is empty — which is the current state until the auditor curates.
- No external CDNs/fonts/scripts (works on plain static hosting; nothing to block).

### Deploy (SSH, supersedes ADR 0003's native-Git transport)
- `scripts/deploy.sh`: `rsync -az --delete dist/ <user>@<host>:<remote_path>` over SSH,
  non-interactive via `sshpass -e` (password from `SSHPASS`/`SSH_HOSTINGER`). Supports
  `--dry-run` (`rsync -n`) for testing without a live push. Host, port, user, and remote path
  come from non-secret env/args; the password is the only secret.
- `.github/workflows/build-deploy.yml`: build the site, then deploy. The deploy step is
  gated on the `SSH_HOSTINGER` secret and, for safety, on an explicit trigger
  (`workflow_dispatch`) so no push silently publishes.

## Secrets / config (needed from the user before a live deploy)
- `SSH_HOSTINGER` — the Hostinger SSH password (gitignored `.env` locally, GitHub Actions
  secret in CI). Never printed or committed.
- Non-secret build-time values: SSH host, port, username, remote path (`public_html`).

## Testing (TDD)
- `build_flags`: enrichment (canonical_name, category, overprice_pct), deterministic order,
  empty input → empty output.
- `build`: writes `dist/index.html` and `dist/data/flags.json`; flags.json matches
  `build_flags`.
- `deploy.sh --dry-run`: runs `rsync -n` and exits 0 without contacting a real host (invoked
  against a local target in the test, or asserted to construct the right command).

## Hard stop
The first real deploy to the public site is a hard-to-reverse, publicly-visible action. Build
and dry-run everything, then STOP and get the `SSH_HOSTINGER` credential + host/port/user and
explicit go-ahead from the user before any live push.

## Out of scope
Robust statistics, historical trends, cryptographic provenance (later phases).
