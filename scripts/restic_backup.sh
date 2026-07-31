#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESTIC_ENV="${FUNDEVAL_RESTIC_ENV:-${HOME}/.config/fundeval/restic.env}"
RUNTIME_DIR="${FUNDEVAL_RUNTIME_DIR:-${PROJECT_DIR}/.runtime}"
STAGING_DIR="${PROJECT_DIR}/cache/backup-staging"
SOURCE_DB="${PROJECT_DIR}/cache/fund_data.db"
SNAPSHOT_DB="${STAGING_DIR}/fund_data.db"
LOG_DIR="${FUNDEVAL_LOG_DIR:-${PROJECT_DIR}/logs}"
LOG_FILE="${LOG_DIR}/restic_backup.log"
ENV_NAME="${FUNDEVAL_ENV_NAME:-finance}"

mkdir -p "${RUNTIME_DIR}" "${STAGING_DIR}" "${LOG_DIR}"
chmod 700 "${RUNTIME_DIR}" "${STAGING_DIR}" "${LOG_DIR}"
exec >>"${LOG_FILE}" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] backup start"
[[ -f "${RESTIC_ENV}" ]] || { echo "Missing ${RESTIC_ENV}"; exit 1; }
[[ -f "${SOURCE_DB}" ]] || { echo "Missing ${SOURCE_DB}"; exit 1; }

set -a
source "${RESTIC_ENV}"
set +a

exec 9>"${RUNTIME_DIR}/restic.lock"
if ! flock -n 9; then
    echo "Another Restic task is already running; skip"
    exit 0
fi

resolve_python() {
    local candidate
    if [[ -n "${PYTHON_BIN:-}" ]]; then
        command -v "${PYTHON_BIN}" 2>/dev/null || printf '%s' "${PYTHON_BIN}"
        return
    fi
    for candidate in \
        "${HOME}/miniforge3/envs/${ENV_NAME}/bin/python" \
        "${HOME}/mambaforge/envs/${ENV_NAME}/bin/python" \
        "${HOME}/.conda/envs/${ENV_NAME}/bin/python" \
        "${PROJECT_DIR}/.venv/bin/python"; do
        if [[ -x "${candidate}" ]]; then
            printf '%s' "${candidate}"
            return
        fi
    done
    command -v python3
}

PYTHON="$(resolve_python)"
TEMP_DB="${SNAPSHOT_DB}.tmp"
cleanup() {
    rm -f "${TEMP_DB}" "${SNAPSHOT_DB}"
}
trap cleanup EXIT

"${PYTHON}" - "${SOURCE_DB}" "${TEMP_DB}" <<'PY'
import os
import sqlite3
import sys

source_path, target_path = sys.argv[1:3]
if os.path.exists(target_path):
    os.unlink(target_path)
with sqlite3.connect(source_path) as source, sqlite3.connect(target_path) as target:
    source.backup(target)
    integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_keys = target.execute("PRAGMA foreign_key_check").fetchall()
    if integrity != "ok" or foreign_keys:
        raise SystemExit(
            f"Snapshot validation failed: integrity={integrity}, foreign_keys={foreign_keys}"
        )
os.chmod(target_path, 0o600)
PY

mv "${TEMP_DB}" "${SNAPSHOT_DB}"
BACKUP_PATHS=("${SNAPSHOT_DB}")
[[ -f "${PROJECT_DIR}/.env" ]] && BACKUP_PATHS+=("${PROJECT_DIR}/.env")

restic backup "${BACKUP_PATHS[@]}" --host fundeval-prod --tag fundeval
restic snapshots --host fundeval-prod --tag fundeval --latest 1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] backup complete"
