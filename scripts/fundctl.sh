#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${FUNDEVAL_RUNTIME_DIR:-${PROJECT_DIR}/.runtime}"
LOG_DIR="${FUNDEVAL_LOG_DIR:-${PROJECT_DIR}/cache/logs}"
PID_FILE="${RUNTIME_DIR}/fundeval.pid"
ACCESS_LOG="${LOG_DIR}/gunicorn_access.log"
ERROR_LOG="${LOG_DIR}/gunicorn_error.log"
PYTHON_BIN="${PYTHON_BIN:-${PROJECT_DIR}/.venv/bin/python}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
    PYTHON_BIN="${FUNDEVAL_PYTHON:-python3}"
fi

read_pid() {
    [[ -f "${PID_FILE}" ]] || return 1
    local pid
    pid="$(tr -d '[:space:]' < "${PID_FILE}")"
    [[ "${pid}" =~ ^[0-9]+$ ]] || return 1
    printf '%s' "${pid}"
}

is_running() {
    local pid
    pid="$(read_pid)" || return 1
    kill -0 "${pid}" 2>/dev/null
}

resolve_bind() {
    if [[ -n "${FUNDEVAL_BIND:-}" ]]; then
        printf '%s' "${FUNDEVAL_BIND}"
        return
    fi
    PYTHONPATH="${PROJECT_DIR}" "${PYTHON_BIN}" -c \
        'from src.config.yaml_config import get_server_config; c=get_server_config(); print("{}:{}".format(c.get("host", "0.0.0.0"), c.get("port", 8311)))'
}

is_ready() {
    local bind="$1"
    PYTHONPATH="${PROJECT_DIR}" "${PYTHON_BIN}" -c '
import socket, sys
host, port = sys.argv[1].rsplit(":", 1)
host = "127.0.0.1" if host in ("0.0.0.0", "::") else host.strip("[]")
try:
    with socket.create_connection((host, int(port)), timeout=0.2):
        pass
except OSError:
    raise SystemExit(1)
' "${bind}" >/dev/null 2>&1
}

bind_port() {
    local bind="$1"
    printf '%s' "${bind##*:}"
}

listener_pids() {
    local port
    port="$(bind_port "$1")"
    if command -v lsof >/dev/null 2>&1; then
        lsof -nP -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true
    elif command -v fuser >/dev/null 2>&1; then
        fuser -n tcp "${port}" 2>/dev/null | tr ' ' '\n' | sed '/^$/d'
    fi
}

process_cwd() {
    local pid="$1"
    if [[ -L "/proc/${pid}/cwd" ]]; then
        readlink -f "/proc/${pid}/cwd" 2>/dev/null || true
    elif command -v lsof >/dev/null 2>&1; then
        lsof -a -p "${pid}" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1
    fi
}

stop_project_listeners() {
    local bind="$1"
    local found=0
    local foreign=0
    local pid
    for pid in $(listener_pids "${bind}"); do
        if [[ "$(process_cwd "${pid}")" == "${PROJECT_DIR}" ]]; then
            echo "停止未纳入 PID 文件的 FundEval 进程，PID=${pid}"
            if ! kill -TERM "${pid}"; then
                echo "无法停止 PID=${pid}，请检查当前用户权限" >&2
                return 3
            fi
            found=1
        else
            foreign=1
        fi
    done
    if (( foreign == 1 )); then
        echo "端口 $(bind_port "${bind}") 被其他目录的进程占用，未执行停止" >&2
        return 2
    fi
    return "$(( found == 1 ? 0 : 1 ))"
}

start_server() {
    if is_running; then
        echo "FundEval 已在运行，PID=$(read_pid)"
        return 0
    fi
    rm -f "${PID_FILE}"
    mkdir -p "${RUNTIME_DIR}" "${LOG_DIR}"

    if ! PYTHONPATH="${PROJECT_DIR}" "${PYTHON_BIN}" -c 'import gunicorn' >/dev/null 2>&1; then
        echo "未安装 gunicorn，请先执行: ${PYTHON_BIN} -m pip install -r requirements.txt" >&2
        return 1
    fi

    local bind
    bind="$(resolve_bind)"
    (
        cd "${PROJECT_DIR}"
        FUNDEVAL_START_BACKGROUND_TASKS=1 PYTHONPATH="${PROJECT_DIR}" \
            "${PYTHON_BIN}" -m gunicorn run:app \
            --daemon \
            --bind "${bind}" \
            --workers "${FUNDEVAL_WORKERS:-1}" \
            --worker-class gthread \
            --threads "${FUNDEVAL_THREADS:-8}" \
            --timeout "${FUNDEVAL_TIMEOUT:-120}" \
            --pid "${PID_FILE}" \
            --access-logfile "${ACCESS_LOG}" \
            --error-logfile "${ERROR_LOG}" \
            --capture-output
    )

    for _ in {1..100}; do
        if is_running && is_ready "${bind}"; then
            echo "FundEval 启动成功，PID=$(read_pid)，监听 ${bind}"
            return 0
        fi
        sleep 0.1
    done
    if ! is_running; then
        rm -f "${PID_FILE}"
    fi
    echo "FundEval 启动失败，请检查 ${ERROR_LOG}" >&2
    return 1
}

stop_server() {
    local bind
    bind="$(resolve_bind)"
    if ! is_running; then
        rm -f "${PID_FILE}"
        if stop_project_listeners "${bind}"; then
            for _ in {1..100}; do
                local remaining_pids
                remaining_pids="$(listener_pids "${bind}")"
                if [[ -z "${remaining_pids}" ]]; then
                    echo "FundEval 已停止"
                    return 0
                fi
                local listener_pid
                for listener_pid in ${remaining_pids}; do
                    if [[ "$(process_cwd "${listener_pid}")" == "${PROJECT_DIR}" ]]; then
                        kill -TERM "${listener_pid}" 2>/dev/null || true
                    else
                        echo "端口 $(bind_port "${bind}") 被其他目录的进程占用" >&2
                        return 1
                    fi
                done
                sleep 0.1
            done
            echo "停止超时，端口 $(bind_port "${bind}") 仍可连接" >&2
            return 1
        fi
        local result=$?
        if (( result == 2 || result == 3 )); then
            return 1
        fi
        echo "FundEval 未运行"
        return 0
    fi

    local pid
    pid="$(read_pid)"
    kill -TERM "${pid}"
    for _ in {1..300}; do
        if ! kill -0 "${pid}" 2>/dev/null; then
            rm -f "${PID_FILE}"
            echo "FundEval 已停止"
            return 0
        fi
        sleep 0.1
    done
    echo "停止超时，进程 PID=${pid} 仍在运行" >&2
    return 1
}

status_server() {
    if is_running; then
        echo "FundEval 正在运行，PID=$(read_pid)，监听 $(resolve_bind)"
        return 0
    fi
    local bind
    bind="$(resolve_bind)"
    local pid
    for pid in $(listener_pids "${bind}"); do
        if [[ "$(process_cwd "${pid}")" == "${PROJECT_DIR}" ]]; then
            echo "FundEval 正在运行但未纳入 PID 文件，PID=${pid}，监听 ${bind}"
            return 0
        fi
    done
    echo "FundEval 未运行"
    return 1
}

case "${1:-}" in
    start) start_server ;;
    stop) stop_server ;;
    restart) stop_server; start_server ;;
    status) status_server ;;
    rotate-logs) "${PROJECT_DIR}/scripts/rotate_logs.sh" ;;
    logs) tail -n "${FUNDEVAL_LOG_LINES:-100}" -f "${ERROR_LOG}" ;;
    *) echo "用法: $0 {start|stop|restart|status|rotate-logs|logs}" >&2; exit 2 ;;
esac
