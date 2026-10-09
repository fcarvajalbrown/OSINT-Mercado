# 0026 — Anchor published flags on the Stellar ledger

**Status:** Accepted
**Date:** 2026-10-09
**Deciders:** Felipe Carvajal Brown

## Context

Every published flag already carries a provenance link to its official purchase order
(ADR 0007), and every curation decision is a git diff (ADR 0006). Neither proves to an outside
reader that the dataset they see today is the one that was published: the site, the repo and
its history are all controlled by the publisher, so a flag could be edited or removed quietly.
For a public-interest audit of municipalities that is the weak point, and it is the one a
municipality would attack ("the site changed the numbers").

The project is also entering the Find Your Way hackathon (Tellus Cooperative, Stellar), which
requires building on Stellar.

## Decision

Anchor each publication of the flag dataset on the **Stellar testnet**, with a new
`osint-anchor` CLI (`src/osint_mercado/anchor.py`) and an in-browser verifier.

- **Leaf per flag.** Each published flag (the exact rows `build_site.build_flags` emits) is
  serialised canonically: keys sorted, compact separators, UTF-8, and floats with an integral
  value written as integers, so Python and the browser's `JSON.stringify` produce identical
  bytes. The leaf is the SHA-256 of those bytes.
- **Batch digest.** The digest is the SHA-256 of the sorted leaves, concatenated as raw bytes.
  One transaction per publication carries the 32-byte digest as a `MEMO_HASH` and in a
  `manage_data` entry named `osint-mercado`, so the account also holds the latest digest as
  state.
- **Record.** The CLI writes `data/anchors.json` (digest, leaves, flag ids, transaction hash,
  ledger, network). `osint-build-site` ships it next to `flags.json`.
- **Verification in the browser.** The dashboard fetches the transaction from the public
  Horizon testnet server, recomputes every leaf and the digest with `crypto.subtle`, and marks
  each row as anchored or not. No JavaScript dependency is added.
- **Key.** The anchoring account's secret lives only in the gitignored `.env` as
  `STELLAR_ANCHOR_SECRET`; the testnet account is funded by Friendbot.

## Consequences

- Any reader can check, without trusting the site, that a flag shown today is the one anchored
  at a given ledger time; a silent edit turns its row red.
- New Python dependency: `stellar-sdk` (py-stellar-base, Apache-2.0).
- Testnet is reset periodically by the Stellar Development Foundation, so anchors there are a
  demonstration, not a permanent record. Moving to mainnet is a later decision and a new ADR.
- Per-flag verification needs the whole leaf list. That is fine at the current size (single
  digits to hundreds of flags); a Merkle tree with per-flag proofs is the upgrade path if the
  dataset grows.

## Alternatives considered

- **Per-flag Merkle proofs.** Rejected for now: stronger, but about an hour more work than the
  hackathon session allows, and not needed at this dataset size.
- **A Soroban contract registry of digests.** Rejected for now: a richer use of Stellar, but
  not deliverable in the same session. Remains a candidate for a later ADR.
- **Hash the raw `flags.json` file.** Rejected: it proves the file but cannot say which row
  changed, which is the point of the dashboard check.
