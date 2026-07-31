#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESTIC_ENV="${FUNDEVAL_RESTIC_ENV:-${HOME}/.config/fundeval/restic.env}"
RUNTIME_DIR="${FUNDEVAL_RUNTIME_DIR:-${PROJECT_DIR}/.runtime}"
LOG_DIR="${FUNDEVAL_LOG_DIR:-${PROJECT_DIR}/logs}"
LOG_FILE="${LOG_DIR}/restic_maintenance.log"

mkdir -p "${RUNTIME_DIR}" "${LOG_DIR}"
chmod 700 "${RUNTIME_DIR}" "${LOG_DIR}"
exec >>"${LOG_FILE}" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] maintenance start"
[[ -f "${RESTIC_ENV}" ]] || { echo "Missing ${RESTIC_ENV}"; exit 1; }
set -a
source "${RESTIC_ENV}"
set +a

exec 9>"${RUNTIME_DIR}/restic.lock"
if ! flock -n 9; then
    echo "Another Restic task is already running; skip"
    exit 0
fi

restic check
restic forget \
    --host fundeval-prod \
    --tag fundeval \
    --keep-daily 14 \
    --keep-weekly 8 \
    --keep-monthly 12 \
    --prune
echo "[$(date '+%Y-%m-%d %H:%M:%S')] maintenance complete"
