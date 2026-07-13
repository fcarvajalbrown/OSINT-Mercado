#!/usr/bin/env bash
# Deploy the built static site to Hostinger public_html over SSH.
#
# Password auth is non-interactive via sshpass (the password is the only secret).
# Required env:
#   SSH_HOST          Hostinger SSH host
#   SSH_USER          SSH username
#   SSH_REMOTE_PATH   remote target (e.g. public_html or domains/<site>/public_html)
#   SSHPASS           the SSH password (map SSH_HOSTINGER -> SSHPASS in CI)
# Optional env:
#   SSH_PORT          SSH port (default 22)
#   SRC_DIR           built site dir (default dist)
#
# Pass --dry-run to preview with rsync -n (no remote changes). The env checks run
# before any network call, so validation is testable without a live host.
set -euo pipefail

SRC_DIR="${SRC_DIR:-dist}"
SSH_PORT="${SSH_PORT:-22}"

DRY=""
VERBOSE=""
if [[ "${1:-}" == "--dry-run" ]]; then DRY="-n"; VERBOSE="-vi"; fi  # itemize changes on dry-run

: "${SSH_HOST:?SSH_HOST is required}"
: "${SSH_USER:?SSH_USER is required}"
: "${SSH_REMOTE_PATH:?SSH_REMOTE_PATH is required}"
: "${SSHPASS:?SSHPASS is required (the SSH password)}"

if [[ ! -d "$SRC_DIR" ]]; then
  echo "source dir '$SRC_DIR' not found; build the site first (osint-build-site)" >&2
  exit 1
fi

echo "Deploying '$SRC_DIR/' -> ${SSH_USER}@${SSH_HOST}:${SSH_REMOTE_PATH}/ (port ${SSH_PORT})${DRY:+ [dry-run]}"

# --delete mirrors the source: files removed locally are removed on the remote.
# Scoped to SSH_REMOTE_PATH (public_html), never the account root.
# Excludes protect server-managed files this push must never touch:
#   gh_config.php     - holds the refresh.php token (created on the server)
#   data/             - flags.json is pulled by the Hostinger cron (refresh.php)
sshpass -e rsync ${DRY} ${VERBOSE} -az --delete \
  --exclude 'gh_config.php' --exclude 'data/' \
  -e "ssh -p ${SSH_PORT} -o StrictHostKeyChecking=accept-new" \
  "${SRC_DIR}/" "${SSH_USER}@${SSH_HOST}:${SSH_REMOTE_PATH}/"

echo "Done."
