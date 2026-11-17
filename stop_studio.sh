#!/usr/bin/env bash
# ==============================================================================
# AI NOVEL STUDIO (LINUX MINT 8GB RAM EDITION) - GRACEFUL SHUTDOWN SCRIPT
# Menghentikan llama-server, FastAPI, Caddy, dan Cloudflared secara bersih
# serta melakukan checkpoint WAL SQLite agar naskah novel tersimpan aman.
# ==============================================================================
set -euo pipefail

STUDIO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${STUDIO_ROOT}/backend"
RUN_DIR="${STUDIO_ROOT}/.run"
DB_FILE="${BACKEND_DIR}/novel_studio.db"

GREEN='\033[0;32m'
AMBER='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}==============================================================================${NC}"
echo -e "${CYAN}   MEMATIKAN THE ZEN LITERARY STUDIO & MEMBEBASKAN RAM LINUX MINT            ${NC}"
echo -e "${CYAN}==============================================================================${NC}"

stop_pid_file() {
    local name="$1"
    local pid_file="${RUN_DIR}/${name}.pid"

    if [[ -f "${pid_file}" ]]; then
        local pid
        pid="$(cat "${pid_file}" 2>/dev/null || true)"
        if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
            echo -e "${AMBER}→ Menghentikan ${name} (PID: ${pid})...${NC}"
            kill -TERM "${pid}" 2>/dev/null || true
            for _ in {1..15}; do
                if ! kill -0 "${pid}" 2>/dev/null; then
                    break
                fi
                sleep 0.2
            done
            if kill -0 "${pid}" 2>/dev/null; then
                kill -KILL "${pid}" 2>/dev/null || true
            fi
            echo -e "${GREEN}✓ ${name} berhasil dihentikan.${NC}"
        else
            echo -e "${GREEN}✓ ${name} sudah tidak aktif.${NC}"
        fi
        rm -f "${pid_file}"
    else
        echo -e "${GREEN}✓ Tidak ada PID aktif untuk ${name}.${NC}"
    fi
}

stop_pid_file "cloudflared"
stop_pid_file "caddy"
stop_pid_file "fastapi"
stop_pid_file "llama-server"

# Checkpoint SQLite WAL ke file database utama agar bersih 100%
if [[ -f "${DB_FILE}" ]] && command -v python3 >/dev/null 2>&1; then
    python3 - "${DB_FILE}" << 'PYEOF'
import sqlite3
import sys

db_path = sys.argv[1]
try:
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    conn.close()
    print("✓ SQLite WAL Checkpoint (TRUNCATE) selesai — seluruh naskah aman di disk.")
except Exception as exc:
    print(f"ℹ Info SQLite Checkpoint: {exc}")
PYEOF
fi

RAM_USED_MB="$(free -m | awk '/^Mem:/ {print $3}')"
RAM_AVAIL_MB="$(free -m | awk '/^Mem:/ {print $7}')"

echo -e "${CYAN}------------------------------------------------------------------------------${NC}"
echo -e "${GREEN}✓ Seluruh layanan AI Novel Studio telah dimatikan.${NC}"
echo -e "  📊 Memori Linux Mint Sekarang: Terpakai ${RAM_USED_MB} MB | Tersedia ${RAM_AVAIL_MB} MB"
echo -e "${CYAN}==============================================================================${NC}"
