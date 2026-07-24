#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "${PROJECT_DIR}/.env" ]]; then
    set -a
    source "${PROJECT_DIR}/.env"
    set +a
fi
LOG_DIR="${FUNDEVAL_LOG_DIR:-${PROJECT_DIR}/logs}"
RUNTIME_DIR="${FUNDEVAL_RUNTIME_DIR:-${PROJECT_DIR}/.runtime}"
PID_FILE="${RUNTIME_DIR}/fundeval.pid"
RETENTION_DAYS="${FUNDEVAL_LOG_RETENTION_DAYS:-14}"
TIMESTAMP="$(date '+%Y-%m-%d_%H%M%S')"

if [[ ! "${RETENTION_DAYS}" =~ ^[0-9]+$ ]] || (( RETENTION_DAYS < 1 )); then
    echo "FUNDEVAL_LOG_RETENTION_DAYS 必须是正整数" >&2
    exit 2
fi

mkdir -p "${LOG_DIR}"

rotate_file() {
    local source_file="$1"
    [[ -s "${source_file}" ]] || return 0
    local archived_file="${source_file}.${TIMESTAMP}"
    mv "${source_file}" "${archived_file}"
    gzip -f "${archived_file}"
    echo "已归档: ${archived_file}.gz"
}

rotate_file "${LOG_DIR}/gunicorn_access.log"
rotate_file "${LOG_DIR}/gunicorn_error.log"
rotate_file "${LOG_DIR}/transaction_import.log"

if [[ -f "${PID_FILE}" ]]; then
    pid="$(tr -d '[:space:]' < "${PID_FILE}")"
    if [[ "${pid}" =~ ^[0-9]+$ ]] && kill -0 "${pid}" 2>/dev/null; then
        kill -USR1 "${pid}"
    fi
fi

find "${LOG_DIR}" -type f \
    \( -name 'gunicorn_access.log.*.gz' \
       -o -name 'gunicorn_error.log.*.gz' \
       -o -name 'transaction_import.log.*.gz' \
       -o -name 'fund_server.*.log.gz' \) \
    -mtime "+${RETENTION_DAYS}" -delete

echo "日志轮转完成，归档保留 ${RETENTION_DAYS} 天"
