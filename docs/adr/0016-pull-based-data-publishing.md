# 0016 — Pull-based data publishing via Hostinger cron (refines ADR 0015)

**Status:** Accepted (refines ADR 0015)
**Date:** 2026-07-12
**Deciders:** Felipe Carvajal Brown

## Context

ADR 0015 established rsync-over-SSH from GitHub Actions as the deploy transport. That works
for the whole site, but it couples every data update to a `workflow_dispatch` push and would
mean either manual deploys after each curation or an auto-deploy that commits/pushes on a
schedule (repo churn). The auditor already runs a proven pattern on the same Hostinger account
(`refresh.php` + a Hostinger cron that pulls fresh data from a private GitHub repo) and
prefers it here. The dashboard splits cleanly into two update cadences: the **frontend**
(HTML/CSS/JS) changes rarely, while the **data** (`flags.json`) changes whenever the auditor
confirms flags.

## Decision

Split publishing by cadence:

- **Frontend** (`index.html`, `app.js`, `styles.css`, `refresh.php`, `gh_config.sample.php`)
  continues to deploy via the ADR 0015 rsync push — occasional, manual `workflow_dispatch`.
  The rsync now **excludes** `gh_config.php` (server-only secret) and `data/` (cron-managed),
  so a frontend deploy never clobbers them.
- **Data** publishes pull-based. CI builds `published/flags.json` from `confirmed_flags.json`
  (workflow `publish-data.yml`, triggered when the confirmed set changes) and commits it. A
  Hostinger cron calls `refresh.php`, which fetches `published/flags.json` from the private
  repo via the GitHub Contents API (read-only fine-grained token in server-only
  `gh_config.php`) and writes it atomically to `data/flags.json`.

Only human-confirmed flags ever reach `published/flags.json`, so the pull path never bypasses
the curation gate (ADR 0006). `refresh.php` validates JSON before writing, writes via a
temp-file rename, and supports an optional `?key=` shared secret so it cannot be spammed.

## Consequences

- Data updates require no rsync and no scheduled push to `master`; the site refreshes itself
  on the auditor's chosen cron interval after a confirm+push.
- The GitHub token lives only on the server in `gh_config.php` (gitignored); the sample
  template ships in the repo. The token is read-only and scoped to this repo.
- Two publishing paths now exist (frontend rsync, data cron-pull); the rsync excludes keep
  them from fighting over `data/` and `gh_config.php`.
- The auditor must, one time: create the read-only token, place `gh_config.php` on the
  server, and configure the Hostinger cron. Ongoing publishing is then automatic within the
  cron interval of each confirm+push.
- Because the source data (Mercado Público) is a daily batch, a cron interval of hours (or
  daily) is ample; sub-minute polling would only re-pull identical data.

## Alternatives considered

- **Auto-deploy via rsync on every confirmed change (ADR 0015 as-is).** Works, but pushes to
  `master` / dispatches on a schedule and does not match the auditor's established cron-pull
  workflow.
- **Enrich `flags.json` in PHP on the server** (join `confirmed_flags.json` + `basket.json`).
  Rejected: duplicates `build_flags` logic in a second language; building once in CI keeps a
  single source of truth.
- **Make the published data a public gist / public repo.** Rejected: unnecessary given the
  token-based pull already used on this account; keeps everything in one private repo.
