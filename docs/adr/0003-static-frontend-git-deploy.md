# 0003 — Static web frontend + native Git deploy; Dear PyGui dropped

**Status:** Accepted (Supersedes ADR 002 of `docs/OSINT_Mercado_PRD.pdf`)
**Date:** 2026-07-12
**Deciders:** Felipe Carvajal Brown

## Context

The original PRD specified **Dear PyGui**, a desktop immediate-mode GUI, for a local daemon.
The target is a webapp, so a desktop GUI is inapplicable. The presentation plane must be
served by Hostinger shared hosting (static files) and show the published, curated dataset.

Verified Hostinger facts: the **native Git integration** connects a GitHub repo via OAuth,
deploys a chosen branch to `public_html`, and auto-redeploys on push (webhook). It works for
static HTML/JS on both Premium and Business plans. The separate "Deploy Web App" (Node.js)
tile is Business/Cloud only; the account here is **Business**, so it is available but not
required.

## Decision

Build a **static HTML/CSS/JS dashboard** with **client-side filtering** over a small
published JSON dataset. Build the frontend in GitHub Actions, commit the built static output,
and let **Hostinger's native Git integration** auto-deploy it to `public_html`.

Do **not** depend on Hostinger's own build environment (the Node "Deploy Web App" build),
even though Business unlocks it — keep deploy plan-agnostic and reproducible in CI.

## Consequences

- Zero server-side code on Hostinger; nothing to patch or scale on the host.
- The frontend build is reproducible in CI and independent of the host's toolchain.
- Client-side filtering is viable because the published dataset is only *confirmed flags* for
  a tight basket — small by construction.
- Framework choice (vanilla vs Alpine vs a small static-export framework) is left to the
  frontend phase; the constraint is "emits static output."

## Alternatives considered

- **Dear PyGui / desktop GUI.** Rejected: not a webapp technology.
- **Hostinger Node "Deploy Web App" build.** Available on Business, but ties deploys to the
  host's build environment; rejected as the default in favor of pre-built static output.
- **PHP + MySQL server-rendered dashboard.** Rejected for v1: more infra and the fiddly
  problem of getting CI data into shared-hosting MySQL. Reconsider only if server-side search
  over full history is needed later.
