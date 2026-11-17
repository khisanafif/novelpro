#!/usr/bin/env bash
# ==============================================================================
# AI NOVEL STUDIO (LINUX MINT 8GB RAM EDITION) - START ORCHESTRATOR
# Menjalankan llama-server (IQ4_XS + Q4 KV Cache), FastAPI (1 Worker),
# serta Caddy / Cloudflared dengan prioritas CPU nice -n 10 agar GUI Mint mulus.
# ==============================================================================
set -euo pipefail

STUDIO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${STUDIO_ROOT}/backend"
VENV_DIR="${BACKEND_DIR}/.venv"
MODELS_DIR="${STUDIO_ROOT}/models"
BIN_DIR="${STUDIO_ROOT}/bin"
RUN_DIR="${STUDIO_ROOT}/.run"
LOG_DIR="${STUDIO_ROOT}/.logs"

FASTAPI_PORT="${FASTAPI_PORT:-8000}"
CADDY_PORT="${CADDY_PORT:-3000}"
LLAMA_PORT="${LLAMA_PORT:-8080}"

OPEN_BROWSER=1
ENABLE_TUNNEL=0
for arg in "$@"; do
    case "${arg}" in
        --no-browser) OPEN_BROWSER=0 ;;
        --tunnel) ENABLE_TUNNEL=1 ;;
    esac
done

mkdir -p "${RUN_DIR}" "${LOG_DIR}" "${MODELS_DIR}" "${BIN_DIR}"

GREEN='\033[0;32m'
AMBER='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}==============================================================================${NC}"
echo -e "${CYAN}   MENYALAKAN THE ZEN LITERARY STUDIO (LINUX MINT 8GB RAM EDITION)           ${NC}"
echo -e "${CYAN}==============================================================================${NC}"

# Pastikan venv & database sudah siap (jika belum, jalankan setup otomatis)
if [[ ! -d "${VENV_DIR}" ]] || [[ ! -f "${BACKEND_DIR}/novel_studio.db" ]]; then
    echo -e "${AMBER}→ Menjalankan inisialisasi awal (setup_mint_8gb.sh)...${NC}"
    bash "${STUDIO_ROOT}/setup_mint_8gb.sh"
fi

# Hitung jumlah thread CPU optimal (N-1 core agar Cinnamon/XFCE GUI tetap 60 FPS)
TOTAL_CORES="$(nproc 2>/dev/null || echo 4)"
if [[ "${TOTAL_CORES}" -gt 2 ]]; then
    AI_THREADS=$((TOTAL_CORES - 1))
else
    AI_THREADS=2
fi
AI_THREADS="${LLAMA_THREADS:-${AI_THREADS}}"

# ------------------------------------------------------------------------------
# 1. JALANKAN NATIVE C++ LLAMA-SERVER (PORT 8080, KV CACHE Q4_0, PARALLEL 1)
# ------------------------------------------------------------------------------
echo -e "\n${AMBER}[1/3] Memeriksa Mesin Inferensi C++ llama-server (Port ${LLAMA_PORT})...${NC}"

LLAMA_BIN=""
if [[ -n "${LLAMA_SERVER_BIN:-}" ]] && [[ -x "${LLAMA_SERVER_BIN}" ]]; then
    LLAMA_BIN="${LLAMA_SERVER_BIN}"
elif [[ -x "${BIN_DIR}/llama-server" ]]; then
    LLAMA_BIN="${BIN_DIR}/llama-server"
elif [[ -x "/opt/novel-studio/bin/llama-server" ]]; then
    LLAMA_BIN="/opt/novel-studio/bin/llama-server"
elif command -v llama-server >/dev/null 2>&1; then
    LLAMA_BIN="$(command -v llama-server)"
fi

MODEL_FILE="${LLAMA_MODEL_PATH:-}"
if [[ -z "${MODEL_FILE}" ]] || [[ ! -f "${MODEL_FILE}" ]]; then
    MODEL_FILE="$(find "${MODELS_DIR}" /opt/novel-studio/models -maxdepth 2 -name "*.gguf" 2>/dev/null | head -n 1 || true)"
fi

if [[ -f "${RUN_DIR}/llama-server.pid" ]] && kill -0 "$(cat "${RUN_DIR}/llama-server.pid")" 2>/dev/null; then
    echo -e "${GREEN}✓ llama-server sudah berjalan (PID: $(cat "${RUN_DIR}/llama-server.pid")).${NC}"
elif [[ -n "${LLAMA_BIN}" ]] && [[ -n "${MODEL_FILE}" ]] && [[ -f "${MODEL_FILE}" ]]; then
    MODEL_SIZE_MB="$(du -m "${MODEL_FILE}" | awk '{print $1}')"
    KV_CACHE_TYPE="${LLAMA_KV_CACHE_TYPE:-}"
    if [[ -z "${KV_CACHE_TYPE}" ]]; then
        if [[ "${MODEL_SIZE_MB}" -le 2700 ]]; then
            KV_CACHE_TYPE="f16"
        else
            KV_CACHE_TYPE="q8_0"
        fi
    fi

    echo -e "${CYAN}  • Binary : ${LLAMA_BIN}${NC}"
    echo -e "${CYAN}  • Model  : $(basename "${MODEL_FILE}") (${MODEL_SIZE_MB} MB)${NC}"
    echo -e "${CYAN}  • Threads: ${AI_THREADS} dari ${TOTAL_CORES} core (nice -n 10) | KV Cache: ${KV_CACHE_TYPE}${NC}"

    export LD_LIBRARY_PATH="$(dirname "${LLAMA_BIN}"):${BIN_DIR}:${LD_LIBRARY_PATH:-}"
    LLAMA_HELP="$("${LLAMA_BIN}" --help 2>&1 || true)"
    EXTRA_LLAMA_FLAGS=()
    # Pakai pencocokan substring internal Bash agar bebas SIGPIPE pada `set -euo pipefail`
    if [[ "${LLAMA_HELP}" == *"--load-mode"* ]]; then
        EXTRA_LLAMA_FLAGS+=(--load-mode mmap)
    elif [[ "${LLAMA_HELP}" == *"--mmap"* ]]; then
        EXTRA_LLAMA_FLAGS+=(--mmap)
    fi
    if [[ "${LLAMA_HELP}" == *"--flash-attn ["* ]]; then
        EXTRA_LLAMA_FLAGS+=(--flash-attn auto)
    elif [[ "${LLAMA_HELP}" == *"--flash-attn"* ]]; then
        EXTRA_LLAMA_FLAGS+=(--flash-attn)
    fi
    if [[ "$(basename "${MODEL_FILE}" | tr '[:upper:]' '[:lower:]')" == *"qwen3"* ]]; then
        if [[ "${LLAMA_HELP}" == *"--reasoning ["* ]]; then
            EXTRA_LLAMA_FLAGS+=(--reasoning off)
        elif [[ "${LLAMA_HELP}" == *"--reasoning-budget"* ]]; then
            EXTRA_LLAMA_FLAGS+=(--reasoning-budget 0)
        fi
    fi

    nohup nice -n 10 "${LLAMA_BIN}" \
        --model "${MODEL_FILE}" \
        --host 127.0.0.1 \
        --port "${LLAMA_PORT}" \
        --ctx-size 8192 \
        --cache-type-k "${KV_CACHE_TYPE}" \
        --cache-type-v "${KV_CACHE_TYPE}" \
        --parallel 1 \
        --threads "${AI_THREADS}" \
        --batch-size 512 \
        --ubatch-size 256 \
        --cont-batching \
        "${EXTRA_LLAMA_FLAGS[@]}" \
        > "${LOG_DIR}/llama-server.log" 2>&1 &

    echo $! > "${RUN_DIR}/llama-server.pid"
    echo -e "${GREEN}✓ llama-server dijalankan di background (PID: $(cat "${RUN_DIR}/llama-server.pid")).${NC}"
else
    echo -e "${AMBER}ℹ Catatan: Binary llama-server atau file model .gguf belum ditemukan di ${MODELS_DIR}/.${NC}"
    echo -e "${AMBER}  Backend akan tetap berjalan dengan Deterministic Pacing Fallback Engine.${NC}"
fi

# ------------------------------------------------------------------------------
# 2. JALANKAN FASTAPI ORCHESTRATOR (UVICORN 1 WORKER, NICE -N 10, PORT 8000)
# ------------------------------------------------------------------------------
echo -e "\n${AMBER}[2/3] Menjalankan FastAPI Orchestrator & Static Web UI (Port ${FASTAPI_PORT})...${NC}"

FASTAPI_HOST="${FASTAPI_HOST:-0.0.0.0}"
if [[ -f "${BACKEND_DIR}/.env.security" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${BACKEND_DIR}/.env.security"
    set +a
    if [[ "${NOVEL_SECURITY_MODE:-}" == "STRICT_CLOUDFLARE" ]] || [[ "${NOVEL_SECURITY_MODE:-}" == "CF_OR_LOCALHOST" ]]; then
        FASTAPI_HOST="127.0.0.1"
    fi
fi

if [[ -f "${RUN_DIR}/fastapi.pid" ]] && kill -0 "$(cat "${RUN_DIR}/fastapi.pid")" 2>/dev/null; then
    echo -e "${GREEN}✓ FastAPI sudah berjalan (PID: $(cat "${RUN_DIR}/fastapi.pid")).${NC}"
else
    (
        cd "${BACKEND_DIR}"
        PYTHONUNBUFFERED=1 nohup nice -n 10 "${VENV_DIR}/bin/uvicorn" main:app \
            --host "${FASTAPI_HOST}" \
            --port "${FASTAPI_PORT}" \
            --workers 1 \
            --no-access-log \
            > "${LOG_DIR}/fastapi.log" 2>&1 &
        echo $! > "${RUN_DIR}/fastapi.pid"
    )
    sleep 1
    if [[ -f "${RUN_DIR}/fastapi.pid" ]] && kill -0 "$(cat "${RUN_DIR}/fastapi.pid")" 2>/dev/null; then
        echo -e "${GREEN}✓ FastAPI (1 Worker) aktif di port ${FASTAPI_PORT} (PID: $(cat "${RUN_DIR}/fastapi.pid")).${NC}"
    else
        echo -e "${RED}✕ Gagal menjalankan FastAPI. Periksa log di: ${LOG_DIR}/fastapi.log${NC}"
        cat "${LOG_DIR}/fastapi.log" || true
        exit 1
    fi
fi

# ------------------------------------------------------------------------------
# 3. JALANKAN CADDY WEB SERVER & CLOUDFLARED TUNNEL (OPSIONAL JIKA TERINSTAL)
# ------------------------------------------------------------------------------
echo -e "\n${AMBER}[3/3] Memeriksa Layanan Reverse Proxy Caddy & Cloudflared...${NC}"

ACTIVE_WEB_PORT="${FASTAPI_PORT}"

if command -v caddy >/dev/null 2>&1 && [[ -f "${STUDIO_ROOT}/Caddyfile" ]]; then
    if [[ -f "${RUN_DIR}/caddy.pid" ]] && kill -0 "$(cat "${RUN_DIR}/caddy.pid")" 2>/dev/null; then
        echo -e "${GREEN}✓ Caddy Web Server sudah berjalan (PID: $(cat "${RUN_DIR}/caddy.pid")).${NC}"
        ACTIVE_WEB_PORT="${CADDY_PORT}"
    else
        nohup nice -n 10 caddy run --config "${STUDIO_ROOT}/Caddyfile" --adapter caddyfile \
            > "${LOG_DIR}/caddy.log" 2>&1 &
        echo $! > "${RUN_DIR}/caddy.pid"
        sleep 0.5
        if kill -0 "$(cat "${RUN_DIR}/caddy.pid")" 2>/dev/null; then
            echo -e "${GREEN}✓ Caddy Web Server aktif di port ${CADDY_PORT} (PID: $(cat "${RUN_DIR}/caddy.pid")).${NC}"
            ACTIVE_WEB_PORT="${CADDY_PORT}"
        fi
    fi
else
    echo -e "${GREEN}✓ FastAPI menyajikan langsung antarmuka Web Statis di port ${FASTAPI_PORT} (0 MB Overhead Tambahan).${NC}"
fi

if [[ "${ENABLE_TUNNEL}" -eq 1 ]] || [[ -n "${CLOUDFLARED_TUNNEL_TOKEN:-}" ]]; then
    if command -v cloudflared >/dev/null 2>&1; then
        if [[ -f "${RUN_DIR}/cloudflared.pid" ]] && kill -0 "$(cat "${RUN_DIR}/cloudflared.pid")" 2>/dev/null; then
            echo -e "${GREEN}✓ Cloudflared Tunnel sudah berjalan (PID: $(cat "${RUN_DIR}/cloudflared.pid")).${NC}"
        else
            if [[ -n "${CLOUDFLARED_TUNNEL_TOKEN:-}" ]]; then
                nohup nice -n 10 cloudflared tunnel run --token "${CLOUDFLARED_TUNNEL_TOKEN}" \
                    > "${LOG_DIR}/cloudflared.log" 2>&1 &
            else
                nohup nice -n 10 cloudflared tunnel --url "http://127.0.0.1:${ACTIVE_WEB_PORT}" \
                    > "${LOG_DIR}/cloudflared.log" 2>&1 &
            fi
            echo $! > "${RUN_DIR}/cloudflared.pid"
            echo -e "${GREEN}✓ Cloudflared Tunnel dijalankan (PID: $(cat "${RUN_DIR}/cloudflared.pid")).${NC}"
        fi
    fi
fi

# ------------------------------------------------------------------------------
# DETEKSI IP LAN WI-FI LOKAL & TAMPILKAN INFORMASI AKSES
# ------------------------------------------------------------------------------
LAN_IP="$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}' | head -n 1)"
if [[ -z "${LAN_IP}" ]]; then
    LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
fi
LAN_IP="${LAN_IP:-127.0.0.1}"

RAM_USED_MB="$(free -m | awk '/^Mem:/ {print $3}')"
RAM_TOTAL_MB="$(free -m | awk '/^Mem:/ {print $2}')"

echo -e "\n${CYAN}==============================================================================${NC}"
echo -e "${GREEN}✨ THE ZEN LITERARY STUDIO AKTIF & SIAP DIGUNAKAN!${NC}"
echo -e "${CYAN}------------------------------------------------------------------------------${NC}"
echo -e "  🖥️  Akses Lokal (Linux Mint) : ${GREEN}http://localhost:${FASTAPI_PORT}${NC}"
echo -e "  📱  Akses HP/Tablet (Wi-Fi)  : ${GREEN}http://${LAN_IP}:${FASTAPI_PORT}${NC}"
if [[ "${ACTIVE_WEB_PORT}" != "${FASTAPI_PORT}" ]]; then
    echo -e "  🌐  Akses via Caddy Proxy    : ${GREEN}http://${LAN_IP}:${CADDY_PORT}${NC}"
fi
echo -e "  🧠  Endpoint Mesin AI C++    : http://127.0.0.1:${LLAMA_PORT}"
echo -e "  📊  Pemakaian RAM Saat Ini   : ${AMBER}${RAM_USED_MB} MB / ${RAM_TOTAL_MB} MB${NC}"
echo -e "  🛑  Untuk Mematikan Studio   : ${CYAN}./stop_studio.sh${NC}"
echo -e "${CYAN}==============================================================================${NC}"

if [[ "${OPEN_BROWSER}" -eq 1 ]] && [[ -n "${DISPLAY:-}" ]] && command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://localhost:${ACTIVE_WEB_PORT}" >/dev/null 2>&1 &
fi
