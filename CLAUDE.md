# OSINT-Mercado

Public-interest webapp that audits Chilean municipal procurement for overpricing. A Python
pipeline (external compute) ingests purchase orders from the Mercado Público / ChileCompra
API, compares them against a curated retail baseline for a controlled basket of commoditized
goods, flags deviations, routes them through a human curation gate, and publishes confirmed
flags to a static dashboard where each one links back to its official source order.

**Vision and scope:** `PRD.md`. **Phase status:** `ROADMAP.md`. **Every significant
decision:** `docs/adr/` (these are the source of truth; the root `docs/OSINT_Mercado_PRD.pdf`
is a superseded historical artifact).

## Current scope (v1)

- **Coverage:** the 52 municipalities of the Región Metropolitana, queried by-organism
  (`CodigoOrganismo`). Long-term goal: national, broad product categories.
- **Data acquisition:** live API, `ordenesdecompra.json?fecha=…&CodigoOrganismo=…` per
  municipal code, then detail-per-order for prices. The bulk open-data dumps are not usable
  (tenders-only, stale) — see the acquisition ADR.
- **Basket:** a tight controlled set of commoditized SKUs (~15-25).

## Architecture

Split across three planes (ADR 0001): a Python + Polars pipeline runs on **external compute**
(GitHub Actions — Python does not run on the target Hostinger shared host); the store is
**versioned data files** in the repo (ADR 0004); the presentation plane is a **static
frontend** deployed to Hostinger by rsync-over-SSH from GitHub Actions (ADR 0015, key auth
per ADR 0025; supersedes the native Git integration of ADR 0003). No Rust/PyO3
(ADR 0002). Matching is a **controlled-basket classifier** (ADR 0005). Every published flag
passes a **human curation gate** (ADR 0006) and carries a **provenance link** (ADR 0007).

## Commits and PRs
- Use **Conventional Commits** (`feat:`, `fix:`, `docs:`, `test:`, `chore:`,
  `refactor:`, `ci:`), scoped where useful (`feat(ir): ...`).
- **Always commit and push as you go**: one commit per completed, logical unit of
  work (not one giant commit at the end). If a remote `origin` is configured,
  push right after each commit — don't let local commits pile up unpushed. If no
  remote is configured yet, just commit locally; don't create a GitHub repo on
  your own initiative to enable pushing.
- **Never open a pull request unless explicitly asked** in that same request.
- **No AI attribution** anywhere: no `Co-Authored-By` trailers, no "Generated
  with ..." lines in commits, PRs, code, or docs.

## Writing
- **No emojis** anywhere: code, comments, docs, commit messages, chat.
- **Outward-facing non-technical prose** (README, announcements, marketing copy)
  must go through the humanizer pass before publishing, to strip AI-writing tells
  (em-dash-as-aside, "not just X, but Y" parallelism, uniform sentence rhythm,
  repeated stock adjectives). Technical documents are exempt: ADRs, PRD, code
  comments, this file.
- Keep the doc structure: `PRD.md` (stable vision), `ROADMAP.md` (phase status),
  `docs/adr/` (one MADR-lite file per decision, immutable once Accepted; supersede
  via a new ADR). Decisions are settled in the ADRs. Do not silently diverge; if
  something seems wrong, stop and ask.

## Development
- Python 3.11+ (dev machine: 3.14). Package layout under `src/osint_mercado/`.
- Venv: `python -m venv .venv` then `.venv/Scripts/python -m pip install -e ".[dev]"`
  (Windows path uses `Scripts/`, not `bin/`).
- **TDD:** write the failing test first, confirm it fails, implement, confirm it passes.
  Run `.venv/Scripts/python -m pytest -q` and `.venv/Scripts/python -m ruff check src tests`.
- **Never guess** API field names, params, quotas, or library behavior — verify against a
  real captured fixture or official docs first. API field names funnel through
  `src/osint_mercado/schema.py`; nothing else hard-codes them.
- **Statistics:** the anomaly and peer engines (`scoring.py`, `peers.py`, `baseline.py`)
  use robust statistics — median / MAD / IQR and outlier detection — never mean/stddev,
  which are not robust to the contract-vs-unit outliers we hunt. When extending or
  reviewing this math, use the `statistical-analysis` skill (project-local under
  `.claude/skills/`; `.claude/` is gitignored, so if it is missing reinstall with
  `npx skills add anthropics/knowledge-work-plugins@statistical-analysis`).

## Secrets and TLS
- The ChileCompra API ticket lives only in a gitignored `.env` (key `CHILECOMPRA_API_TICKET`)
  locally, and a GitHub Actions secret of the same name in CI. Never commit it, print it, or
  put it in a fixture or a logged URL.
- **Deploy auth (Hostinger) is by SSH key, not password.** Hostinger rejects password SSH auth
  on this account (`u703383606`), so `build-deploy.yml` and `setup-refresh.yml` authenticate
  with a dedicated ed25519 key stored in the `SSH_KEY` GitHub Actions secret (private key only;
  its public key is in the server's `~/.ssh/authorized_keys`). `scripts/deploy.sh` writes
  `SSH_KEY` to a `chmod 600` temp file and passes `-i <key> -o IdentitiesOnly=yes` to rsync's
  ssh. Host/port/user/remote-path are non-secret Actions *variables* (`SSH_HOST`, `SSH_PORT`,
  `SSH_USER`, `SSH_REMOTE_PATH`). The old password path (`sshpass`, the `SSH_HOSTINGER` secret)
  was removed once key auth was verified (ADR 0025). Do not reintroduce password auth.
- Deploy is `workflow_dispatch`-only: `gh workflow run build-deploy.yml` (add
  `-f dry_run=true` to preview with `rsync -n` before a real publish). No push auto-publishes.
- This dev machine intercepts TLS with a self-signed cert. HTTP clients verify against the OS
  trust store via the `truststore` package (`truststore.inject_into_ssl()`). **Never disable
  certificate verification.**
