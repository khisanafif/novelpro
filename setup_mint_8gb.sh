#!/usr/bin/env bash
# ==============================================================================
# AI NOVEL STUDIO (LINUX MINT 8GB RAM EDITION) - AUTOMATED SETUP SCRIPT
# Mengacu pada Bagian 7, 9, dan 10 Master Blueprint Arsitektur
# ==============================================================================
set -euo pipefail

STUDIO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${STUDIO_ROOT}/backend"
FRONTEND_DIR="${STUDIO_ROOT}/frontend"
VENV_DIR="${BACKEND_DIR}/.venv"
DB_FILE="${BACKEND_DIR}/novel_studio.db"
MODELS_DIR="${STUDIO_ROOT}/models"
BIN_DIR="${STUDIO_ROOT}/bin"
RUN_DIR="${STUDIO_ROOT}/.run"
LOG_DIR="${STUDIO_ROOT}/.logs"

GREEN='\033[0;32m'
AMBER='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}==============================================================================${NC}"
echo -e "${CYAN}   INSTALASI & OPTIMASI OTOMATIS: THE ZEN LITERARY STUDIO (LINUX MINT 8GB)    ${NC}"
echo -e "${CYAN}==============================================================================${NC}"

mkdir -p "${MODELS_DIR}" "${BIN_DIR}" "${RUN_DIR}" "${LOG_DIR}"

# ------------------------------------------------------------------------------
# 1. KONFIGURASI ZRAM-TOOLS (ZSTD, 50% RAM, SWAPPINESS=100) JIKA BELUM AKTIF
# ------------------------------------------------------------------------------
echo -e "\n${AMBER}[1/4] Memeriksa konfigurasi ZRAM (ZSTD 50% RAM, swappiness=100)...${NC}"

configure_zram() {
    local zram_active=0
    if command -v swapon >/dev/null 2>&1 && swapon --show | grep -q "zram"; then
        zram_active=1
    fi

    if [[ "${zram_active}" -eq 1 ]]; then
        echo -e "${GREEN}✓ Perangkat ZRAM sudah aktif di sistem ini:${NC}"
        swapon --show | grep "zram" || true
    else
        echo -e "${AMBER}→ ZRAM belum aktif. Menyiapkan konfigurasi zram-tools (butuh akses sudo)...${NC}"
        if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null || [[ "${EUID}" -eq 0 ]]; then
            local SUDO_CMD=""
            [[ "${EUID}" -ne 0 ]] && SUDO_CMD="sudo"

            if ! dpkg -s zram-tools >/dev/null 2>&1; then
                ${SUDO_CMD} apt-get update -y
                ${SUDO_CMD} apt-get install -y zram-tools
            fi

            ${SUDO_CMD} tee /etc/default/zramswap >/dev/null << 'EOF'
ALGO=zstd
PERCENT=50
PRIORITY=100
EOF

            ${SUDO_CMD} tee /etc/sysctl.d/99-mint-ai-novel-studio.conf >/dev/null << 'EOF'
vm.swappiness=100
vm.vfs_cache_pressure=50
EOF

            ${SUDO_CMD} systemctl restart zramswap || true
            ${SUDO_CMD} sysctl --system >/dev/null 2>&1 || true
            echo -e "${GREEN}✓ ZRAM (ALGO=zstd, PERCENT=50, PRIORITY=100, vm.swappiness=100) berhasil diaktifkan!${NC}"
        else
            echo -e "${AMBER}ℹ Untuk mengaktifkan ZRAM secara permanen di Linux Mint, jalankan perintah ini dengan sudo:${NC}"
            echo -e "  sudo apt update && sudo apt install -y zram-tools"
            echo -e "  printf 'ALGO=zstd\\nPERCENT=50\\nPRIORITY=100\\n' | sudo tee /etc/default/zramswap"
            echo -e "  printf 'vm.swappiness=100\\nvm.vfs_cache_pressure=50\\n' | sudo tee /etc/sysctl.d/99-mint-ai.conf"
            echo -e "  sudo systemctl restart zramswap && sudo sysctl --system"
        fi
    fi
}

configure_zram

# ------------------------------------------------------------------------------
# 2. MEMBUAT PYTHON VIRTUAL ENVIRONMENT (.venv) & INSTALASI REQUIREMENTS.TXT
# ------------------------------------------------------------------------------
echo -e "\n${AMBER}[2/4] Menyiapkan Python Virtual Environment & menginstal pustaka ringan...${NC}"

if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${RED}✕ Error: python3 tidak ditemukan. Instal dengan: sudo apt install -y python3 python3-venv python3-pip${NC}"
    exit 1
fi

if [[ ! -d "${VENV_DIR}" ]]; then
    python3 -m venv "${VENV_DIR}"
    echo -e "${GREEN}✓ Virtual environment berhasil dibuat di: ${VENV_DIR}${NC}"
else
    echo -e "${GREEN}✓ Virtual environment sudah tersedia di: ${VENV_DIR}${NC}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
python -m pip install --upgrade pip --quiet
python -m pip install -r "${BACKEND_DIR}/requirements.txt"
echo -e "${GREEN}✓ Seluruh dependensi (FastAPI, Uvicorn, HTTPX, Pydantic) berhasil terinstal!${NC}"

# ------------------------------------------------------------------------------
# 3. INISIALISASI DATABASE SQLITE (WAL + FTS5 BM25) & STARTER TEMPLATE PROYEK
# ------------------------------------------------------------------------------
echo -e "\n${AMBER}[3/4] Menginisialisasi Database SQLite (WAL + FTS5 BM25) & Starter Template Novel...${NC}"

NOVEL_STUDIO_DB="${DB_FILE}" python3 - << 'PYEOF'
import os
import sys

backend_dir = os.path.abspath("backend")
sys.path.insert(0, backend_dir)

import database
import engine

db_path = os.environ.get("NOVEL_STUDIO_DB", os.path.join(backend_dir, "novel_studio.db"))
database.init_db(db_path)

existing_projects = database.list_projects(db_path=db_path)
if existing_projects:
    proj = existing_projects[0]
    print(f"✓ Database sudah memiliki proyek aktif: '{proj['title']}' (ID: {proj['id']})")
else:
    proj = database.create_project(
        title="Senja di Pelabuhan Sunda (Starter Template)",
        genre="Historical Literary Mystery",
        logline="Seorang juru tulis pelabuhan menemukan manifes kapal yang sengaja dibakar untuk menutupi penyelundupan senjata kolonial tahun 1892.",
        main_objective="Mengungkap konspirasi sindikat dermaga tanpa kehilangan nyawa dan menyelamatkan buku sandi pembukuan.",
        pov_style="Third-Person Limited",
        tense_style="Lampau / Past Narrative",
        tone_style="Atmosferik, Imersif, Show Dont Tell, Puitis Tajam",
        style_sample="Lentera minyak di ujung dermaga berayun pelan, memantulkan kilau kuning pucat di atas genangan air asin yang berbau cengkeh basah dan karat besi.",
        total_planned_chapters=24,
        default_chapter_words=3200,
        rolling_global_summary="Arya Wiratmaja, juru tulis muda di Kantor Syahbandar Sunda Kelapa, baru saja menyadari adanya selisih berat muatan pada kapal uap Dejima yang bersandar tengah malam.",
        active_model_profile="Qwen2.5-3B-Instruct-Q4_K_M",
        seed_default_phases=True,
        db_path=db_path,
    )

    char_arya = database.create_codex_item(
        project_id=proj["id"],
        category="CHARACTER",
        name="Arya Wiratmaja",
        aliases_and_tags="Arya, Juru Tulis Syahbandar",
        keywords_csv="Arya, juru tulis, buku sandi, tinta, manifes, kacamata",
        is_pinned=1,
        core_description="Juru tulis muda di kantor syahbandar yang teliti, memiliki ingatan tajam terhadap angka manifes, namun menyimpan trauma masa lalu akibat tenggelamnya kapal ayahnya.",
        speech_style="Tenang, terukur, sopan secara formal namun menyimpan ironi tajam di balik kalimat pendek.",
        current_state={
            "location": "Ruang Arsip Kantor Syahbandar",
            "condition": "Sehat, ujung jari bernoda tinta hitam dan mantel basah oleh gerimis",
            "emotional_state": "Waspada dan curiga",
            "knowledge": "Mengetahui halaman 14 buku manifes kapal Dejima sengaja disobek sebelum diperiksa",
        },
        db_path=db_path,
    )

    char_kapten = database.create_codex_item(
        project_id=proj["id"],
        category="CHARACTER",
        name="Kapten Hendrick van Der Berg",
        aliases_and_tags="Kapten Hendrick, Komandan Patroli Dermaga",
        keywords_csv="Hendrick, kapten, patroli, pipa tembakau, pedang pori",
        is_pinned=1,
        core_description="Perwira pengawas bea pelabuhan bertubuh jangkung dengan bekas luka bakar di pelipis kiri. Selalu membawa jam saku perak dan pipa tembakau beraroma vanila pahit.",
        speech_style="Suara bariton rendah, sering menjeda kalimat untuk mengembuskan asap pipa, mengintimidasi secara halus.",
        current_state={
            "location": "Pos Penjagaan Dermaga Barat",
            "condition": "Sehat, siaga penuh",
            "emotional_state": "Dingin dan penuh perhitungan",
            "knowledge": "Mengetahui ada seseorang yang masih menyalakan lentera di ruang arsip lewat jam malam",
        },
        db_path=db_path,
    )

    loc_gudang = database.create_codex_item(
        project_id=proj["id"],
        category="LOCATION",
        name="Gudang Cengkeh Nomor 4",
        aliases_and_tags="Gudang 4, Dermaga Barat",
        keywords_csv="gudang, cengkeh, dermaga barat, gembok kuningan, peti kayu",
        is_pinned=1,
        core_description="Gudang kayu jati tua beratap seng berkarat di ujung Dermaga Barat. Udara di dalamnya pengap oleh aroma cengkeh lembap, minyak tanah, dan garam laut.",
        speech_style="",
        current_state={
            "location": "Ujung Dermaga Barat",
            "condition": "Digembok rantai kuningan dari luar saat jam malam",
            "emotional_state": "Gelap, hanya diterangi celah lampu kapal dari arah laut",
            "knowledge": "Menyimpan 12 peti kayu panjang bersegel merah tanpa nomor registrasi bea cukai",
        },
        db_path=db_path,
    )

    database.create_codex_item(
        project_id=proj["id"],
        category="WORLD_RULE",
        name="Aturan Jam Malam Lonceng Tiga (1892)",
        aliases_and_tags="Hukum Pelabuhan, Patroli Lentera Merah",
        keywords_csv="jam malam, lonceng tiga, lentera merah, surat jalan, segel lilin",
        is_pinned=1,
        core_description="Tepat pukul 22.00 lonceng menara syahbandar berdentang tiga kali. Seluruh lampu gudang wajib dipadamkan. Siapa pun yang tertangkap patroli Lentera Merah tanpa surat jalan bersegel lilin gubernur akan ditahan tanpa pengadilan.",
        db_path=db_path,
    )

    chapter_1 = database.create_chapter(
        project_id=proj["id"],
        chapter_number=1,
        title="Abu di Sela Buku Manifes",
        chapter_goal="Arya memeriksa buku manifes di ruang arsip saat hujan malam, menemukan abu kertas segel di tungku perapian, lalu menyelinap keluar menuju Gudang Cengkeh Nomor 4 tepat saat lonceng jam malam berbunyi.",
        target_word_count=2400,
        pacing_mode="SLOW_BURN",
        mix_world_building=65,
        mix_psychology=65,
        mix_sensory=80,
        mix_dialogue=40,
        mix_action=30,
        ending_hook_style="CLIFFHANGER",
        status="DRAFTING",
        db_path=db_path,
    )

    plan = engine.DeterministicPacingEngine.calculate_chapter_plan(
        target_words=2400,
        pacing_mode="SLOW_BURN",
        t_min=15,
        t_max=30,
    )
    starter_beats = engine.ContextAssembler.build_deterministic_fallback_beats(
        chapter=chapter_1,
        plan=plan,
        codex_items=[char_arya, char_kapten, loc_gudang],
    )
    database.replace_chapter_micro_beats(chapter_1["id"], starter_beats, db_path=db_path)
    print(f"✓ Starter Template Novel '{proj['title']}' berhasil dibuat lengkap dengan 6 Fase, 4 Codex FTS5, & {len(starter_beats)} Micro-Beats!")
PYEOF

# ------------------------------------------------------------------------------
# 4. PASANG LAUNCHER DESKTOP LINUX MINT & ATUR IZIN EKSEKUSI SKRIP
# ------------------------------------------------------------------------------
echo -e "\n${AMBER}[4/4] Mengatur izin eksekusi skrip & memasang peluncur aplikasi Linux Mint...${NC}"

chmod +x "${STUDIO_ROOT}/setup_mint_8gb.sh"
[[ -f "${STUDIO_ROOT}/start_studio.sh" ]] && chmod +x "${STUDIO_ROOT}/start_studio.sh"
[[ -f "${STUDIO_ROOT}/stop_studio.sh" ]] && chmod +x "${STUDIO_ROOT}/stop_studio.sh"

DESKTOP_TARGET_DIR="${HOME}/.local/share/applications"
if [[ -f "${STUDIO_ROOT}/NovelStudio.desktop" ]]; then
    mkdir -p "${DESKTOP_TARGET_DIR}"
    sed "s|__STUDIO_ROOT__|${STUDIO_ROOT}|g" "${STUDIO_ROOT}/NovelStudio.desktop" > "${DESKTOP_TARGET_DIR}/NovelStudio.desktop"
    chmod +x "${DESKTOP_TARGET_DIR}/NovelStudio.desktop"
    chmod +x "${STUDIO_ROOT}/NovelStudio.desktop"
    echo -e "${GREEN}✓ Shortcut Menu Linux Mint terpasang di: ${DESKTOP_TARGET_DIR}/NovelStudio.desktop${NC}"
fi

echo -e "\n${CYAN}==============================================================================${NC}"
echo -e "${GREEN}🎉 INSTALASI SELESAI! AI Novel Studio siap dijalankan.${NC}"
echo -e "   • Jalankan Studio : ${CYAN}./start_studio.sh${NC}"
echo -e "   • Hentikan Studio : ${CYAN}./stop_studio.sh${NC}"
echo -e "   • Letakkan file model .gguf Anda di folder: ${CYAN}${MODELS_DIR}/${NC}"
echo -e "${CYAN}==============================================================================${NC}"
