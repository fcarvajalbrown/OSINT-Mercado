# 0025 — SSH key auth for deploy (refines ADR 0015)

**Status:** Accepted (refines ADR 0015)
**Date:** 2026-07-18
**Deciders:** Felipe Carvajal Brown

## Context

ADR 0015 chose rsync-over-SSH from GitHub Actions, authenticating with the Hostinger SSH
password via `sshpass`, and explicitly noted key auth as "a cleaner follow-up ... deferred to
keep v1 setup minimal." The first real `build-deploy` run failed at the rsync step with
`Permission denied (publickey,password)`: Hostinger rejects password SSH auth on this account,
so `sshpass` could never succeed. Key auth is already proven against the same account (host
`147.79.84.110`, user `u703383606`) — it is how a sibling project deploys to it.

## Decision

Authenticate the deploy (and the `setup-refresh` one-shot) with an **SSH private key** instead
of the account password. A dedicated ed25519 keypair was generated for this repo; its public
key is appended to the account's `~/.ssh/authorized_keys`, and its private key is stored as the
GitHub Actions secret `SSH_KEY`. `scripts/deploy.sh` writes `SSH_KEY` to a `chmod 600` temp
file (removed via an `EXIT` trap) and passes it to rsync's ssh with
`-i <keyfile> -o IdentitiesOnly=yes`. Host, port, username, and remote path remain non-secret
Actions *variables*.

Everything else from ADR 0015 is unchanged: `workflow_dispatch`-only trigger, the
`vars.SSH_HOST != ''` guard, env validation before any network call, `--dry-run` support, and
`--delete` scoped to `SSH_REMOTE_PATH`.

## Consequences

- The deploy actually authenticates; the password path (`sshpass`, `SSHPASS`/`SSH_HOSTINGER`)
  is removed from `build-deploy.yml` and `setup-refresh.yml`. The `sshpass` package is no
  longer installed in CI.
- The `SSH_HOSTINGER` secret is now unused and can be deleted once this is confirmed working.
- The key is dedicated to this repo and isolated from other projects sharing the account; the
  private key lives only in the GitHub secret and the local keypair, never in git.
- Fulfils the key-auth migration ADR 0015 anticipated.

## Alternatives considered

- **Keep password auth / fix the password.** Rejected: Hostinger rejects password SSH auth on
  this account, so no password value works; the retries in the failed run confirm it.
- **Reuse the sibling project's existing deploy key.** Rejected: it would give this repo's CI
  write access across the whole shared account and couple two projects to one credential. A
  dedicated key keeps the blast radius per-repo.
