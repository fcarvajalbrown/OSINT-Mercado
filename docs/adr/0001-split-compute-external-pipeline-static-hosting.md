# 0001 — Split-compute architecture: external pipeline + static Hostinger site

**Status:** Accepted (Supersedes the local-daemon premise of `docs/OSINT_Mercado_PRD.pdf`)
**Date:** 2026-07-12
**Deciders:** Felipe Carvajal Brown

## Context

The deployment target is a webapp on **Hostinger Business shared hosting**. Shared hosting
provides no root access, kills persistent processes, and enforces strict RAM/CPU/execution
quotas. Verified fact: **Python is not supported on Hostinger shared hosting** (it needs
root). The heavy work — API ingestion, retail scraping, fuzzy matching, anomaly scoring —
cannot run on the host.

## Decision

Split the system into three planes:

1. **Pipeline (external compute).** The Python data pipeline runs on **GitHub Actions**
   (free scheduled compute), not on Hostinger.
2. **Store (versioned files).** Output is committed to the repo as versioned data files
   (see ADR 0004).
3. **Presentation (Hostinger static).** A static site serves the published dataset from
   `public_html`.

## Consequences

- The impressive analytical engine lives where it can actually run; Hostinger does only what
  shared hosting is good at — serving static files on the bought domain.
- Two environments to reason about (CI + host) and a deploy step between them (ADR 0003).
- Data freshness is tied to the scheduled job cadence (daily), which is ample for a
  procurement watchdog.
- The architecture is honest and defensible ("compute where compute belongs"), which also
  serves the secondary showcase goal.

## Alternatives considered

- **All-native LAMP on Hostinger (PHP + MySQL + cron).** Cheapest single environment, but
  weaker matching, loses the Python engine, and heavy jobs risk hitting shared quotas.
- **Force Python onto Hostinger via Passenger.** Fragile: dependency-compile pain and
  quota/OOM risk on the matching step; and Python is not supported on shared plans anyway.
