#!/usr/bin/env bash
# Deploy the built static site to Hostinger public_html over SSH.
#
# Auth is by SSH private key (Hostinger rejects password auth on this account).
# Required env:
#   SSH_HOST          Hostinger SSH host
#   SSH_USER          SSH username
#   SSH_REMOTE_PATH   remote target (e.g. public_html or domains/<site>/public_html)
#   SSH_KEY           the private key contents (map the SSH_KEY secret in CI)
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
: "${SSH_KEY:?SSH_KEY is required (the SSH private key)}"

if [[ ! -d "$SRC_DIR" ]]; then
  echo "source dir '$SRC_DIR' not found; build the site first (osint-build-site)" >&2
  exit 1
fi

# Write the key to a private temp file with strict perms; clean it up on exit.
KEY_FILE="$(mktemp)"
chmod 600 "$KEY_FILE"
cleanup() { rm -f "$KEY_FILE"; }
trap cleanup EXIT
printf '%s\n' "$SSH_KEY" > "$KEY_FILE"

echo "Deploying '$SRC_DIR/' -> ${SSH_USER}@${SSH_HOST}:${SSH_REMOTE_PATH}/ (port ${SSH_PORT})${DRY:+ [dry-run]}"

# --delete mirrors the source: files removed locally are removed on the remote.
# Scoped to SSH_REMOTE_PATH (public_html), never the account root.
# Excludes protect server-managed files this push must never touch:
#   gh_config.php     - holds the refresh.php token (created on the server)
#   data/             - flags.json is pulled by the Hostinger cron (refresh.php)
rsync ${DRY} ${VERBOSE} -az --delete \
  --exclude 'gh_config.php' --exclude 'data/' \
  -e "ssh -i '${KEY_FILE}' -p ${SSH_PORT} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new" \
  "${SRC_DIR}/" "${SSH_USER}@${SSH_HOST}:${SSH_REMOTE_PATH}/"

echo "Done."
