# 0015 — Deploy transport: SSH + rsync (supersedes the transport of ADR 0003)

**Status:** Accepted (supersedes the deploy transport of ADR 0003)
**Date:** 2026-07-12
**Deciders:** Felipe Carvajal Brown

## Context

ADR 0003 chose a static frontend deployed via **Hostinger's native Git integration** (OAuth
connect a repo, auto-redeploy a branch to `public_html` on push). That decision bundled two
things: the presentation model (static HTML/CSS/JS with client-side filtering — still correct)
and the *transport* (native Git). In Phase 5 the transport is revisited: the native Git
integration couples publishing to a Hostinger-side pull of a specific branch and a committed
build output, which is awkward when the site is generated from `confirmed_flags.json` in CI
and should not be committed. A push-based transport from the same GitHub Actions run that
builds the site is simpler and keeps the built `dist/` out of git.

## Decision

Deploy by **rsync over SSH** from GitHub Actions to Hostinger `public_html`. The build job runs
`osint-build-site` to produce `dist/`; the deploy job mirrors it with
`rsync -az --delete` over `ssh`, authenticating non-interactively with the Hostinger SSH
password via `sshpass` (`scripts/deploy.sh`). Host, port, username, and remote path are
non-secret GitHub Actions *variables*; the password is the only secret (`SSH_HOSTINGER`,
mapped to `SSHPASS`), stored in a gitignored `.env` locally and a GitHub Actions secret in CI.

Safety properties:
- The workflow triggers on `workflow_dispatch` only — no push silently publishes.
- The deploy job runs only when `SSH_HOSTINGER` is configured.
- `deploy.sh` validates all required env before any network call and supports `--dry-run`
  (`rsync -n`) for a no-op preview.
- `--delete` is scoped to `SSH_REMOTE_PATH` (`public_html`), never the account root.

The built `dist/` is generated in CI and gitignored (ADR 0004's versioned store covers the
input datasets, not the derived site).

Migrating from a password to an SSH key later is a cleaner follow-up (more secure, no
`sshpass`); deferred to keep v1 setup minimal on the Hostinger side.

## Consequences

- Publishing is a single CI run: build the site, then push it — no committed build artifact,
  no Hostinger-side branch pull.
- The transport is explicit and testable (env validation + dry-run) rather than an opaque
  host integration.
- A password in CI is a modest secret-management cost; the key-auth migration path is noted.
- ADR 0003's static-frontend/client-side-filtering decision is unchanged and still in force;
  only its transport is replaced.

## Alternatives considered

- **Keep Hostinger native Git integration (ADR 0003).** Rejected as the transport: requires
  committing the built site or pointing the integration at a build the host performs, and
  couples publish timing to a host-side webhook rather than the CI run that produced the site.
- **SSH key auth now instead of password.** Preferred long-term but deferred: password auth is
  the minimal setup to get a first real deploy working; key migration is a clean follow-up.
- **FTP/FTPS deploy.** Rejected: rsync over SSH is faster (delta transfer), supports
  `--delete` mirroring, and is more secure than plain FTP.
