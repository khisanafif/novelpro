# The Zen Literary Studio — AI Novel Writing Studio (Lintas-OS Edition)

Aplikasi web penulisan novel panjang (*long-form fiction*) yang berjalan **100% lokal, privat, dan ringan** di **Linux (Mint / Ubuntu / Debian / Arch / Fedora)**, **Windows 10/11**, **macOS (Apple Silicon & Intel)**, maupun **Android (Termux ARM64)** menggunakan orkestrator **FastAPI (1 Worker)**, **SQLite (WAL + FTS5 BM25 <1 ms)**, dan mesin inferensi native C++ **`llama-server` (`llama.cpp`)**.

Dirancang khusus agar tetap ringan dan mulus di perangkat RAM 8 GB (`nice -n 10` di Linux), hemat memori, bebas *summary moralistik AI*, konsisten antar-bab melalui **4-Tier Memory**, dan dapat diakses dari laptop maupun HP/Tablet lewat Wi-Fi LAN atau Cloudflare Tunnel.

---

## Daftar Isi
1. [Arsitektur, Prasyarat, & Struktur Folder](#1-arsitektur-prasyarat--struktur-folder)
2. [Panduan Instalasi & Menjalankan Studio di Semua OS](#2-panduan-instalasi--menjalankan-studio-di-semua-os)
   - [2A. Linux (Linux Mint / Ubuntu / Debian, serta Arch / Fedora / ARM64)](#2a-linux-linux-mint--ubuntu--debian-serta-arch--fedora--arm64)
   - [2B. Windows 10 / 11 (x64 & ARM64 — PowerShell)](#2b-windows-10--11-x64--arm64--powershell)
   - [2C. macOS (Apple Silicon M1–M4 & Intel x64 — Terminal)](#2c-macos-apple-silicon-m1m4--intel-x64--terminal)
   - [2D. Android (Termux ARM64 — Portable Offline)](#2d-android-termux-arm64--portable-offline)
   - [2E. Referensi Cepat Binary Resmi llama.cpp (`b12428`) Lintas OS](#2e-referensi-cepat-binary-resmi-llamacpp-b12428-lintas-os)
3. [Panduan Lengkap Cara Pakai Studio](#3-panduan-lengkap-cara-pakai-studio)
4. [Kurasi Model AI GGUF: Spesifikasi, Plus/Minus, & Rekomendasi](#4-kurasi-model-ai-gguf-spesifikasi-plusminus--rekomendasi)
5. [Cara Download, Menambah Model Kustom, & Ganti Model (Switch RAM)](#5-cara-download-menambah-model-kustom--ganti-model-switch-ram)
6. [Menggunakan API Model AI Online & Sumber Lain (Gemini, OpenRouter, Groq, OpenAI, Claude, Ollama)](#6-menggunakan-api-model-ai-online--sumber-lain-gemini-openrouter-groq-openai-claude-ollama)
7. [Pengamanan Cloudflare Tunnel (Akses Internet Aman)](#7-pengamanan-cloudflare-tunnel-akses-internet-aman)
8. [Optimasi ZRAM (Linux) & Troubleshooting Lintas OS](#8-optimasi-zram-linux--troubleshooting-lintas-os)

---

## 1. Arsitektur, Prasyarat, & Struktur Folder

- **Python:** Python `3.10` – `3.12` (disarankan `3.12`).
- **RAM:** Minimal `4 GB` (atau jauh lebih ringan lagi jika memakai **Mode API Online**); direkomendasikan `8–16 GB` untuk model lokal 3B–8B, serta 12B pada RAM 16 GB+.
- **Mesin AI:** Mendukung mesin lokal [`ggml-org/llama.cpp` (`b12428`)](https://github.com/ggml-org/llama.cpp/releases/tag/b12428) (`bin/llama-server` / `llama-server.exe`) **maupun** API eksternal kompatibel OpenAI/Anthropic (Gemini, OpenRouter, Groq, OpenAI, DeepSeek, Mistral, Claude, Ollama, LM Studio).
- **Aset UI Offline:** Frontend bekerja 100% tanpa CDN internet (`alpine.min.js` + `studio-utilities.css` terpasang lokal).

```text
novelpro/
├── backend/
│   ├── main.py             # API FastAPI + SingleWorkerInferenceQueue + pemantau RAM lintas OS
│   ├── ai_provider.py      # Adapter Multi-Provider AI (Lokal llama-server, OpenAI-Compat, Anthropic)
│   ├── database.py         # SQLite WAL + FTS5 BM25 (codex_fts & episodic_memory_fts)
│   ├── engine.py           # DeterministicPacingEngine + 3 Persona Prompt + Anti-Summary Filter
│   ├── memory_manager.py   # 4-Tier Memory Assembler (400 kata tail + FTS5 <1ms) & State Extractor
│   ├── model_manager.py    # Model Switcher Lintas-OS, Katalog Kurasi, & Custom GGUF Downloader
│   ├── exporter.py         # Compiler naskah standar penerbit (.EPUB via EbookLib & .MD)
│   ├── security_config.py  # Middleware Validasi Header Cloudflare Tunnel & Generator UFW
│   ├── requirements.txt    # Dependensi Python minimal
│   ├── .venv/              # Python virtual environment lokal
│   └── novel_studio.db     # Database naskah & Story Bible (otomatis dibuat saat start)
├── frontend/
│   ├── vendor/             # Aset offline lokal (alpine.min.js + studio-utilities.css zero-JIT)
│   ├── index.html          # UI The Zen Literary Studio (Warm Parchment & Obsidian Ink)
│   ├── styles.css          # Tipografi Literata & layout responsif Desktop/HP (mobile drawer)
│   └── app.js              # Controller Alpine.js + Auto-Save + SSE real-time streaming
├── bin/
│   └── llama-server        # Binary C++ llama.cpp (atau llama-server.exe di Windows) + library (.so/.dylib/.dll)
├── models/
│   └── Qwen2.5-3B-Instruct-Q4_K_M.gguf  # Model awal terpasang (1.8 GB)
├── Caddyfile               # Reverse proxy statis opsional port 3000 (Linux/macOS/Windows)
├── setup_mint_8gb.sh       # Installer otomatis Linux Mint / Ubuntu / Debian
├── start_studio.sh         # Menyalakan llama-server + FastAPI + info IP LAN (Linux)
├── stop_studio.sh          # Mematikan semua layanan & WAL checkpoint SQLite bersih (Linux)
└── NovelStudio.desktop     # Launcher 1-klik di Application Menu Linux Mint / Desktop Linux
```

---

## 2. Panduan Instalasi & Menjalankan Studio di Semua OS

Pilih panduan sesuai sistem operasi perangkat Anda. Setelah server berjalan dan halaman web terbuka, cara pemakaian UI di browser **sama persis** di seluruh sistem operasi.

---

### 2A. Linux (Linux Mint / Ubuntu / Debian, serta Arch / Fedora / ARM64)

#### 1) Instalasi Otomatis (Linux Mint / Ubuntu / Debian — Disarankan)
Jika memakai Linux Mint, Ubuntu, atau Debian di laptop ini maupun hasil clone baru:
```bash
cd /path/to/novelpro
chmod +x setup_mint_8gb.sh start_studio.sh stop_studio.sh
./setup_mint_8gb.sh
```
Skrip ini otomatis:
- Membuat `backend/.venv` dan menginstal `backend/requirements.txt`,
- Menginisialisasi SQLite FTS5 (`backend/novel_studio.db`) beserta 1 proyek awal **Starter Template**,
- Mendaftarkan `NovelStudio.desktop` ke Application Menu (`~/.local/share/applications/`),
- Menampilkan petunjuk aktivasi ZRAM (jika ingin memakai `sudo`).

*(Catatan untuk workspace ini: `.venv`, `bin/llama-server`, dan `models/Qwen2.5-3B-Instruct-Q4_K_M.gguf` sudah terpasang siap pakai.)*

#### 2) Untuk Distro Arch Linux / Fedora / Linux ARM64 (Setup Baru)
```bash
# Arch Linux / Manjaro / EndeavourOS
sudo pacman -S --needed python python-pip curl sqlite tar

# Fedora
sudo dnf install -y python3 python3-pip curl sqlite tar

# Buat venv, instal dependensi, & buat database starter
cd /path/to/novelpro
python3 -m venv backend/.venv
backend/.venv/bin/pip install --upgrade pip
backend/.venv/bin/pip install -r backend/requirements.txt
backend/.venv/bin/python -c "import sys; sys.path.insert(0, 'backend'); import database; database.init_db()"
```

#### 3) Memasang / Meng-upgrade `llama-server` di `bin/` (Jika Belum Ada)
Pilih varian rilis resmi `llama.cpp` `b12428` sesuai hardware Linux Anda:
- **CPU x64 Umum (Intel Celeron/Core, AMD Ryzen):** `llama-b12428-bin-ubuntu-x64.tar.gz` (`22.4 MB`)
- **GPU Intel/AMD/NVIDIA via Vulkan x64:** `llama-b12428-bin-ubuntu-vulkan-x64.tar.gz` (`34.7 MB`)
- **GPU NVIDIA CUDA 12.8 x64:** `llama-b12428-bin-ubuntu-cuda-12.8-x64.tar.gz` (`190.8 MB`)
- **GPU AMD ROCm 10.0 x64:** `llama-b12428-bin-ubuntu-rocm-10.0-x64.tar.gz` (`260.2 MB`)
- **Linux ARM64 (Raspberry Pi 5 / Server ARM):** `llama-b12428-bin-ubuntu-arm64.tar.gz` (`18.2 MB`)

Contoh pemasangan CPU x64 ke folder `bin/`:
```bash
mkdir -p bin models /tmp/llama-linux
curl -L "https://github.com/ggml-org/llama.cpp/releases/download/b12428/llama-b12428-bin-ubuntu-x64.tar.gz" -o /tmp/llama-linux.tar.gz
tar -xzf /tmp/llama-linux.tar.gz -C /tmp/llama-linux
find /tmp/llama-linux -type f \( -name "llama-server" -o -name "*.so*" \) -exec cp -P {} bin/ \;
chmod +x bin/llama-server
```

#### 4) Menyalakan & Mematikan Studio (Linux)
```bash
cd /path/to/novelpro
./start_studio.sh               # Menyalakan llama-server + FastAPI + buka browser
# Opsi lain:
./start_studio.sh --no-browser  # Menyalakan server tanpa membuka browser otomatis
./start_studio.sh --tunnel      # Sekaligus menyalakan cloudflared (jika sudah setup)
```
Atau klik ikon **The Zen Literary Studio** di **Menu Aplikasi Linux Mint $\rightarrow$ *Office***.

Untuk mematikan seluruh layanan secara bersih dan mengamankan database (`WAL checkpoint`):
```bash
cd /path/to/novelpro
./stop_studio.sh
```
*(Jika hanya ingin memutus sementara model AI di RAM tanpa menutup aplikasi web, klik badge status AI di pojok kanan atas UI lalu tekan **🛑 Matikan AI (Bebaskan RAM)**).*

#### 5) Buka Port LAN 8000 (Jika Ingin Menulis dari HP lewat Wi-Fi)
```bash
sudo ufw allow from 192.168.0.0/16 to any port 8000 proto tcp
sudo ufw allow from 10.0.0.0/8 to any port 8000 proto tcp
```
Lalu buka **`http://<IP-LAN-LAPTOP>:8000`** yang dicetak oleh `./start_studio.sh` di browser HP Anda.

---

### 2B. Windows 10 / 11 (x64 & ARM64 — PowerShell)

#### 1) Prasyarat
1. Pasang **Python 3.10–3.12** dari [python.org/downloads](https://www.python.org/downloads/) *(**WAJIB** centang kotak **"Add python.exe to PATH"** saat instalasi)*, atau jalankan di PowerShell:
   ```powershell
   winget install -e --id Python.Python.3.12
   ```
2. Pasang Git (opsional, jika clone repo): `winget install -e --id Git.Git`.

#### 2) Buat Virtual Environment & Instal Dependensi
Buka **Windows PowerShell**, masuk ke folder proyek `novelpro`:
```powershell
cd C:\path\to\novelpro
python -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install --upgrade pip
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```
*(Dengan memanggil `.\backend\.venv\Scripts\python.exe` langsung, Anda tidak akan terblokir oleh aturan ExecutionPolicy PowerShell.)*

#### 3) Download & Ekstrak Mesin AI `llama-server.exe` ke `bin\`
Pilih versi resmi `b12428` sesuai hardware Windows Anda:
- **CPU x64 Standar (Semua laptop Intel/AMD):** `llama-b12428-bin-win-cpu-x64.zip` (`24.0 MB`)
- **GPU Vulkan (Intel Arc, iGPU AMD Radeon, atau NVIDIA):** `llama-b12428-bin-win-vulkan-x64.zip` (`36.5 MB`)
- **GPU NVIDIA RTX/GTX (CUDA 12.4):** `llama-b12428-bin-win-cuda-12.4-x64.zip` (`305.3 MB`) **+** wajib unduh juga `cudart-llama-bin-win-cuda-12.4-x64.zip` (`373.3 MB`) ke folder `bin\` yang sama!
- **Windows 11 ARM64 (Snapdragon X):** `llama-b12428-bin-win-cpu-arm64.zip` (`12.9 MB`)

Jalankan di PowerShell (contoh CPU x64):
```powershell
New-Item -ItemType Directory -Force -Path bin, models, "$env:TEMP\llama-win" | Out-Null
Invoke-WebRequest -Uri "https://github.com/ggml-org/llama.cpp/releases/download/b12428/llama-b12428-bin-win-cpu-x64.zip" -OutFile "$env:TEMP\llama-win.zip"
Expand-Archive -Path "$env:TEMP\llama-win.zip" -DestinationPath "$env:TEMP\llama-win" -Force
Get-ChildItem -Path "$env:TEMP\llama-win" -Recurse -Include "llama-server.exe","*.dll" | Copy-Item -Destination "bin\" -Force
```
Pastikan file `bin\llama-server.exe` beserta file `*.dll` berada langsung di dalam folder `bin\`.

#### 4) Download Model Awal `.gguf` ke `models\`
*(Anda juga bisa mengunduh langsung lewat Web UI setelah server menyala, atau lewat PowerShell `curl.exe` yang mendukung resume `-C -`):*
```powershell
curl.exe -L -C - "https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q4_K_M.gguf" -o models\Qwen2.5-3B-Instruct-Q4_K_M.gguf
```

#### 5) Menyalakan & Mematikan Studio di Windows
- **Cara Paling Praktis (1 Terminal PowerShell — AI Dinyalakan lewat Web UI):**
  ```powershell
  .\backend\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 0.0.0.0 --port 8000 --workers 1
  ```
  1. Buka browser ke **`http://localhost:8000`** *(file `backend\novel_studio.db` otomatis dibuat saat start).*
  2. Klik badge status AI di pojok kanan atas layar $\rightarrow$ tab **`💾 Model Lokal`** $\rightarrow$ klik **`🔄 Switch & Muat`**. Studio otomatis menyalakan `bin\llama-server.exe` secara latar belakang dan mengatur `PATH` DLL-nya.
- **Cara Manual (2 Terminal PowerShell — bila ingin memantau log `llama-server.exe` secara langsung):**
  - **PowerShell 1 (AI Engine):**
    ```powershell
    .\bin\llama-server.exe -m .\models\Qwen2.5-3B-Instruct-Q4_K_M.gguf --host 127.0.0.1 --port 8080 --ctx-size 8192 --parallel 1 --cache-type-k f16 --cache-type-v f16 --load-mode mmap --flash-attn auto
    ```
    *(Tips GPU: tambahkan `-ngl 99` di akhir perintah jika Anda memakai binary **Vulkan** atau **CUDA**!)*
  - **PowerShell 2 (Web Studio):**
    ```powershell
    .\backend\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 0.0.0.0 --port 8000 --workers 1
    ```
- **Cara Mematikan:** Klik tombol **`🛑 Matikan AI (Bebaskan RAM)`** di Web UI (Backend memakai `taskkill` ke `llama-server.exe`), lalu tekan **`Ctrl+C`** pada jendela PowerShell FastAPI.

#### 6) Akses dari HP via Wi-Fi LAN & Firewall Windows
1. Cek IP lokal Windows di PowerShell dengan `ipconfig` (lihat bagian *Wireless LAN adapter Wi-Fi* $\rightarrow$ `IPv4 Address`, misal `192.168.1.24`).
2. Buka PowerShell **Run as Administrator** sekali saja untuk mengizinkan port `8000` di jaringan rumah (*Private*):
   ```powershell
   New-NetFirewallRule -DisplayName "Zen Literary Studio LAN 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Profile Private -Action Allow
   ```
3. Buka `http://192.168.1.24:8000` di Chrome/Safari HP Anda.

---

### 2C. macOS (Apple Silicon M1–M4 & Intel x64 — Terminal)

#### 1) Prasyarat & Setup Virtual Environment
Pasang [Homebrew](https://brew.sh) jika belum ada, lalu instal Python `3.12`:
```zsh
brew install python@3.12
cd /path/to/novelpro
python3.12 -m venv backend/.venv
backend/.venv/bin/pip install --upgrade pip
backend/.venv/bin/pip install -r backend/requirements.txt
```

#### 2) Pasang `llama-server` ke `bin/` (Metal GPU Otomatis di Apple Silicon)
- **Opsi A — Binary Resmi `llama.cpp` `b12428` (Direkomendasikan agar terisolasi di `bin/`):**
  - Apple Silicon (`M1 / M2 / M3 / M4`, akselerasi **Metal GPU** aktif otomatis): `llama-b12428-bin-macos-arm64.tar.gz` (`16.2 MB`)
  - Mac Intel (`x64`): `llama-b12428-bin-macos-x64.tar.gz` (`12.2 MB`)
  ```zsh
  mkdir -p bin models /tmp/llama-mac
  # Untuk Mac Intel x64, ganti "macos-arm64" menjadi "macos-x64"
  curl -L "https://github.com/ggml-org/llama.cpp/releases/download/b12428/llama-b12428-bin-macos-arm64.tar.gz" -o /tmp/llama-mac.tar.gz
  tar -xzf /tmp/llama-mac.tar.gz -C /tmp/llama-mac
  find /tmp/llama-mac -type f \( -name "llama-server" -o -name "*.dylib" -o -name "*.metallib" \) -exec cp -P {} bin/ \;
  chmod +x bin/llama-server
  # Wajib untuk macOS Gatekeeper agar binary tidak diblokir sebagai "unidentified developer"
  xattr -dr com.apple.quarantine bin/
  ```
- **Opsi B — Alternatif via Homebrew:**
  ```zsh
  brew install llama.cpp
  ```
  *(Studio otomatis mendeteksi `llama-server` di `/opt/homebrew/bin/llama-server` lewat `PATH`.)*

#### 3) Download Model Awal `.gguf` ke `models/`
```zsh
curl -L -C - "https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q4_K_M.gguf" -o models/Qwen2.5-3B-Instruct-Q4_K_M.gguf
```
*(Tips Mac M1–M4 RAM 16 GB+: dengan akselerasi Metal GPU terpadu, model **Tier 2/3/4** seperti `Qwen_Qwen3-4B`, `EVA-Qwen2.5-7B`, bahkan `MN-12B-Celeste` terasa sangat responsif!)*

#### 4) Menyalakan & Mematikan Studio di macOS
- **1 Terminal (AI Dinyalakan Otomatis lewat Web UI):**
  ```zsh
  backend/.venv/bin/python -m uvicorn main:app --app-dir backend --host 0.0.0.0 --port 8000 --workers 1
  ```
  Buka `http://localhost:8000`, klik badge AI di pojok kanan atas $\rightarrow$ **`🔄 Switch & Muat`**. Backend otomatis menyetel `DYLD_LIBRARY_PATH` untuk `bin/` dan membaca pemakaian RAM dari `sysctl` + `vm_stat`.
- **Atau Manual di Terminal terpisah (`-ngl 99` untuk penuh di Metal GPU):**
  ```zsh
  ./bin/llama-server -m models/Qwen2.5-3B-Instruct-Q4_K_M.gguf --host 127.0.0.1 --port 8080 --ctx-size 8192 --parallel 1 --cache-type-k f16 --cache-type-v f16 --load-mode mmap --flash-attn auto -ngl 99
  ```
- **Mematikan:** Klik **`🛑 Matikan AI (Bebaskan RAM)`** di Web UI, lalu tekan `Ctrl+C` di Terminal FastAPI.
- **Akses Wi-Fi LAN:** Cek IP Wi-Fi dengan `ipconfig getifaddr en0`, lalu buka `http://<IP-MAC>:8000` dari iPhone/iPad/Android. Jika macOS Firewall aktif (*System Settings* $\rightarrow$ *Network* $\rightarrow$ *Firewall*), izinkan koneksi masuk untuk `Python`.

---

### 2D. Android (Termux ARM64 — Portable Offline)

Anda bisa menjalankan seluruh server + AI lokal **langsung di HP/Tablet Android (disarankan RAM 6–8 GB+)** tanpa PC/Laptop!

#### 1) Prasyarat & Instalasi Paket Termux
Gunakan **Termux** versi terbaru dari **F-Droid** atau **GitHub Releases** *(hindari versi Play Store karena usang)*:
```bash
pkg update && pkg upgrade -y
pkg install -y git python python-pip python-lxml python-pydantic curl tar libandroid-spawn
```
*(Memasang `python-lxml` dan `python-pydantic` lewat `pkg` sangat penting di Android agar wheel C/Rust native langsung tersedia tanpa kompilasi berjam-jam.)*

#### 2) Setup Environment Python
```bash
cd ~/novelpro
# Wajib --system-site-packages agar lxml & pydantic native dari pkg langsung terbaca
python -m venv --system-site-packages backend/.venv
backend/.venv/bin/pip install fastapi==0.115.5 uvicorn==0.32.1 httpx==0.28.0 EbookLib==0.18 six==1.16.0
```

#### 3) Pasang `llama-server` Android ARM64 (`b12428`) ke `bin/`
- **Semua HP/Tablet Android ARM64 (MediaTek, Exynos, Tensor, Snapdragon):** `llama-b12428-bin-android-arm64.tar.gz` (`75.8 MB`)
- **Khusus SoC Qualcomm Snapdragon (akselerasi Adreno OpenCL):** `llama-b12428-bin-android-arm64-snapdragon.tar.gz` (`63.4 MB`)
```bash
mkdir -p bin models /tmp/llama-and
curl -L "https://github.com/ggml-org/llama.cpp/releases/download/b12428/llama-b12428-bin-android-arm64.tar.gz" -o /tmp/llama-and.tar.gz
tar -xzf /tmp/llama-and.tar.gz -C /tmp/llama-and
find /tmp/llama-and -type f \( -name "llama-server" -o -name "*.so*" \) -exec cp -P {} bin/ \;
chmod +x bin/llama-server
```

#### 4) Download Model Ringan untuk HP
Untuk HP RAM 6–8 GB, **`Qwen3-1.7B-Q4_K_M.gguf` (`1.03 GB`)** atau **`Qwen2.5-3B-Instruct-Q4_K_M.gguf` (`1.80 GB`)** adalah pilihan paling seimbang:
```bash
curl -L -C - "https://huggingface.co/unsloth/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q4_K_M.gguf" -o models/Qwen3-1.7B-Q4_K_M.gguf
```

#### 5) Menyalakan & Mematikan di Android Termux
```bash
# Aktifkan wake-lock agar Android tidak menghentikan server saat Anda pindah ke Chrome
termux-wake-lock 2>/dev/null || true
backend/.venv/bin/python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
```
Buka browser Chrome di HP ke **`http://127.0.0.1:8000`**, ketuk badge status AI di kanan atas $\rightarrow$ **`🔄 Switch & Muat`**. Saat selesai menulis, ketuk **`🛑 Matikan AI`** di UI, tekan `Ctrl+C` di Termux, dan jalankan `termux-wake-unlock`.

---

### 2E. Referensi Cepat Binary Resmi `llama.cpp` (`b12428`) Lintas OS

Semua file berasal dari halaman rilis resmi [ggml-org/llama.cpp `b12428`](https://github.com/ggml-org/llama.cpp/releases/tag/b12428):

| Sistem Operasi & Akselerasi | Nama Asset Rilis (`b12428`) | Ukuran | Catatan |
| :--- | :--- | :---: | :--- |
| **Linux x64 (CPU)** *(Terpasang)* | `llama-b12428-bin-ubuntu-x64.tar.gz` | 22.4 MB | Bawaan paling stabil untuk semua PC/laptop Linux x64. |
| **Linux x64 (Vulkan GPU)** | `llama-b12428-bin-ubuntu-vulkan-x64.tar.gz` | 34.7 MB | GPU Intel/AMD/NVIDIA modern via Vulkan. |
| **Linux x64 (NVIDIA CUDA 12.8)** | `llama-b12428-bin-ubuntu-cuda-12.8-x64.tar.gz` | 190.8 MB | Khusus NVIDIA GeForce RTX/GTX driver CUDA 12.x+. |
| **Linux x64 (AMD ROCm 10.0)** | `llama-b12428-bin-ubuntu-rocm-10.0-x64.tar.gz` | 260.2 MB | Khusus GPU AMD Radeon dengan stack ROCm terpasang. |
| **Linux ARM64 (CPU)** | `llama-b12428-bin-ubuntu-arm64.tar.gz` | 18.2 MB | Raspberry Pi 5, Orange Pi, SBC, atau VM ARM64. |
| **Windows x64 (CPU)** | `llama-b12428-bin-win-cpu-x64.zip` | 24.0 MB | Semua laptop/PC Windows 10/11 Intel & AMD. |
| **Windows x64 (Vulkan GPU)** | `llama-b12428-bin-win-vulkan-x64.zip` | 36.5 MB | Intel Arc, Radeon iGPU/dGPU, NVIDIA tanpa install CUDA Toolkit. |
| **Windows x64 (NVIDIA CUDA 12.4)** | `llama-b12428-bin-win-cuda-12.4-x64.zip` | 305.3 MB | **Wajib** disertai `cudart-llama-bin-win-cuda-12.4-x64.zip` (`373.3 MB`). |
| **Windows ARM64 (CPU)** | `llama-b12428-bin-win-cpu-arm64.zip` | 12.9 MB | Laptop Windows Snapdragon ARM64. |
| **macOS Apple Silicon (Metal GPU)** | `llama-b12428-bin-macos-arm64.tar.gz` | 16.2 MB | Mac M1/M2/M3/M4 (Metal GPU otomatis aktif; jalankan `xattr -dr com.apple.quarantine bin/`). |
| **macOS Intel (CPU x64)** | `llama-b12428-bin-macos-x64.tar.gz` | 12.2 MB | Mac Intel (x86_64). |
| **Android Termux ARM64** | `llama-b12428-bin-android-arm64.tar.gz` | 75.8 MB | Semua HP/Tablet Android ARM64. |
| **Android Snapdragon (OpenCL)** | `llama-b12428-bin-android-arm64-snapdragon.tar.gz` | 63.4 MB | Khusus SoC Qualcomm Snapdragon. |

> **Catatan Flag Modern `llama-server` (`b12428+`):** Studio secara otomatis menguji `--help` milik `llama-server` yang terpasang untuk memilih flag terbaru yang kompatibel (`--load-mode mmap`, `--flash-attn auto`, serta `--reasoning off` / `--reasoning-budget 0` khusus seri Qwen3).

---

## 3. Panduan Lengkap Cara Pakai Studio

Studio sudah dilengkapi 1 proyek contoh siap uji (**"Senja di Pelabuhan Sunda (Starter Template)"**). Berikut alur kerja standar untuk menulis novel baru atau melanjutkan bab:

### Langkah 1 — Buat Proyek & Isi *Core Compass* (Panel Kiri)
1. Klik **`+ Novel`** di pojok kiri atas (atau pilih proyek aktif di dropdown).
2. Buka tab **`Compass`** di panel kiri untuk menentukan **Tier-1 Pinned Core**:
   - **Judul & Nama Penulis / Nama Pena** (otomatis masuk ke metadata sampul `.EPUB`, halaman cetak PDF, dan frontmatter `.MD`).
   - **Premis / Logline** dan **Main Objective (North Star)**: kompas utama dari Bab 1 sampai Tamat.
   - **Sudut Pandang (POV)**, **Tone & Atmosfer**, serta **Contoh Gaya Bahasa Acuan (*Style Sample*)**: tempelkan 2–3 kalimat acuan ritme prosa yang ingin ditiru AI.
   - **Negative Constraints / Banned Phrases**: daftar frasa klise AI yang otomatis diblokir di prompt dan dipotong bila muncul di ekor paragraf.
   - **Profil Model GGUF**: pilih model aktif proyek Anda (klik **`⚡ Switch RAM`** untuk langsung memuatnya ke `llama-server`).
   - **Cadangan & Pemulihan (`.json`)**: klik **`📦 Backup`** untuk mengunduh snapshot penuh proyek, atau **`📥 Restore`** untuk memulihkan berkas backup `.json` menjadi proyek utuh.

### Langkah 2 — Atur *Interactive Phase-Range Timeline* (Pita Atas)
Pita di bagian atas membagi novel menjadi fase-fase terstruktur (misal *Bab 1–4 Opening*, *Bab 5–12 Early Development*, *Bab 13–15 Midpoint Twist*, dst.):
- Klik salah satu kartu fase untuk melihat atau mengubah rentang bab, target **Tension Min–Max (%)**, **Fokus Pembangunan**, dan **Strict Phase Guardrails** (aturan pengunci agar AI tidak membocorkan rahasia akhir cerita atau memunculkan klimaks terlalu dini).

### Langkah 3 — Isi *Codex / Lorebook* (Panel Kiri $\rightarrow$ Tab `Codex`)
Simpan entitas **CHARACTER**, **LOCATION**, **WORLD_RULE**, **ITEM**, atau **LORE**:
- Centang **Pinned (`📌`)** pada tokoh utama dan aturan dunia mutlak agar selalu masuk ke *Static Prefix*.
- Entitas non-pinned tetap otomatis muncul di prompt hanya saat relevan berkat pencarian **SQLite FTS5 BM25 (`<1 ms`, 0 MB RAM)** berdasarkan kata kunci di adegan yang sedang ditulis.
- Untuk karakter, pantau kolom **`Current State`** (`location`, `condition`, `emotional_state`, `inventory`, dan `knowledge`).

### Langkah 4 — Atur Target Kata & *Narrative Mix* di *Mixing Console* (Panel Kanan)
1. Pilih atau buat bab baru di tab **`Bab`** (panel kiri — lengkap dengan pelacak **Total Kata Seluruh Novel** & **Target Kata Harian** yang dapat diklik untuk disesuaikan).
2. Di **Panel Kanan (*Chapter Mixing Console*)**, atur:
   - **Target Kata Bab** (misal `2400` atau `3200` kata $\rightarrow$ sistem otomatis menghitung jumlah *Micro-Beats* yang presisi sekitar ±400 kata per beat).
   - **Mode Pacing**:
     - `SLOW_BURN` *(1 peristiwa besar per 3 beat — cocok untuk atmosfer & pembangunan batin)*
     - `BALANCED` *(1 peristiwa besar per 2 beat)*
     - `FAST_PACED` *(1 peristiwa besar tiap beat)*
     - `FRENETIC_ACTION` *(tempo kejar-kejaran/pertarungan tinggi)*
   - **5 Slider Komposisi Narrative Mix (`0–100%`)**: *World-Building Density*, *Internal Monologue*, *Sensory Atmosphere*, *Dialogue Ratio*, dan *Action Intensity*.
   - **Ending Hook Style**: gaya penutup bab (*Cliffhanger*, *Emotional Echo*, *Revelation*, dll.).
3. Jangan lupa klik **`💾 Simpan Pengaturan Bab`**.

### Langkah 5 — Rancang Micro-Beats (`Generate Beat Plan`)
Di area tengah (*Center Stage*), klik **`⚡ Generate Beat Plan`**:
- AI *Plot Architect* (atau fallback engine deterministik bila `llama-server` sedang mati) akan memecah tujuan bab menjadi kartu-kartu **Micro-Beat** berurutan dengan target kata, kurva ketegangan (*Tension Curve*), jangkar panca indra (*Sensory Anchor*), fokus konflik, dan **Titik Berhenti Beat (*Stopping Point*)**.
- Anda dapat memindahkan urutan beat (`▲` / `▼`), mengubah status penyuntingan (`Rencana` / `Draf Selesai` / `Final`), serta menyunting instruksi tiap kartu beat sebelum mulai menulis.

### Langkah 6 — Tulis Naskah Real-Time (`Write Beat`), Revisi, Cari & Ganti, & `Extract State`
1. Klik **`▶️ Write Beat`** pada kartu Micro-Beat pertama secara berurutan:
   - Sistem merakit prompt **4-Tier Memory**: *Tier 1 (Core & Guardrails)* $\rightarrow$ *Tier 2 (Active Codex & Character State)* $\rightarrow$ *Tier 3 (Rolling Summary + 400 kata verbatim terakhir + hasil FTS5 BM25)* $\rightarrow$ *Tier 4 (Tugas Beat & 5 Slider)*.
   - Jika Beat sudah berisi teks sebelumnya, sistem otomatis membuat **Auto-Snapshot Revisi** sebelum menimpa naskah (*Rewrite*) sehingga naskah lama tetap aman di **`🕒 Riwayat Versi`**.
   - Prosa mengalir kata demi kata (**SSE Streaming**) ke editor, sementara *Anti-Summary Tail Trimming* otomatis membersihkan kalimat ceramah moral klise di akhir adegan.
2. Setelah selesai menulis atau menyunting satu beat:
   - **Auto-Save Otomatis:** Setiap suntingan manual di kotak teks beat otomatis tersimpan setelah 1,5 detik (`✓ Tersimpan`), dan posisi novel & bab terakhir otomatis diingat saat browser dimuat ulang.
   - **Cari & Ganti (`🔎 Cari & Ganti` / `Alt+F`):** Ubah nama tokoh, tempat, atau istilah secara serentak di seluruh Beat dalam bab (snapshot riwayat otomatis tersimpan sebelum penggantian massal).
   - Klik **`🧠 Extract State & Update Codex`** (opsi bawaan **⚡ Cepat <1ms** menjaga KV Cache Slot 0 tetap utuh di CPU 2-Core; atau pilih **🧠 AI Extractor Penuh** di panel kanan) agar ringkasan fakta, inventaris/lokasi karakter, serta `rolling_global_summary` diperbarui di SQLite FTS5.
   - Klik **`🔍 Memori`** pada kartu beat untuk menginspeksi prompt 4-Tier & latensi FTS5 BM25 (`<1–4 ms`), atau tambah/hapus beat satu per satu (`+ Tambah 1 Micro-Beat` / `🗑️`).
3. Gunakan **`📖 Mode Baca Utuh` (`Alt+R`)** untuk meninjau keseluruhan bab seperti halaman novel cetak lengkap dengan pengatur ukuran huruf (`A- / A / A+`), navigasi antabab, dan **`📋 Salin Bab`**, **`🧘 Zen Mode` (`Alt+Z`)**, serta tema **☀️ Parchment / 🌙 Obsidian**.

### Langkah 7 — Kompilasi & Unduh Novel (`.EPUB`, Cetak PDF, `.MD`)
Klik **`📤 Ekspor`** di header kanan atas (tersedia di Desktop maupun HP) untuk memilih format:
- **`📘 Ebook (.EPUB)`**: Menggabungkan seluruh bab dan adegan menjadi berkas `.epub` standar penerbit (lengkap dengan metadata judul, nama penulis, halaman judul, sinopsis, tipografi buku cetak, pemisah adegan `* * *`, dan Daftar Isi otomatis).
- **`🖨️ Cetak / Save PDF`**: Membuka tata letak buku A5 siap cetak untuk langsung dicetak atau disimpan menjadi `.pdf` lewat dialog Print browser (`Ctrl+P`).
- **`📄 Novel Penuh (.MD)`** & **`📝 Bab Aktif (.MD)`**: Mengompilasi naskah lengkap beserta YAML Frontmatter, Daftar Isi, dan lampiran Story Bible menjadi berkas Markdown rapi.

---

## 4. Kurasi Model AI GGUF: Spesifikasi, Plus/Minus, & Rekomendasi

> **Penting untuk Hardware CPU-Only vs RAM 8–12 GB:**
> - **Kecepatan di CPU 2-Core (seperti Intel Celeron 4305U):** kecepatan generasi sangat bergantung pada ukuran file `.gguf` dan bandwidth RAM. Model **1.7B–3B** jauh lebih nyaman untuk menulis interaktif harian; model **7B–8B** menghasilkan prosa lebih matang tetapi butuh waktu tunggu jauh lebih lama per beat di CPU 2-Core (lebih cocok di CPU 4–8 Core atau GPU).
> - **KV Cache Cerdas Otomatis:** Keluarga Qwen sangat sensitif terhadap kuantisasi KV Cache `q4_0`. Studio secara otomatis memakai **`f16` KV Cache** untuk model ringan $\le 2.6\text{ GB}$ dan **`q8_0` KV Cache** untuk model 7B+ agar tata bahasa Indonesia tetap 100% jernih dan bebas kata rusak.

### Daftar Model Rekomendasi (Semua URL Publik Terverifikasi Bebas Login)

#### Tier 1 — Ultra-Ringan & Cepat (Optimal untuk CPU 2-Core & RAM 4–8 GB)

| Model (File `.gguf`) | Ukuran File | Min. RAM / CPU | Kelebihan (+) | Kekurangan (-) | Cocok Untuk |
| :--- | :---: | :---: | :--- | :--- | :--- |
| **`Qwen2.5-3B-Instruct-Q4_K_M.gguf`** *(Terpasang Default)* | **1.80 GB** (`1840.5 MB`) | **RAM 4 GB+**<br>CPU 2 Core+ | • Titik seimbang terbaik CPU 2-Core.<br>• Bahasa Indonesia baku alami.<br>• Sangat patuh JSON *Plot Architect* & *State Extractor*. | • Metafora sastra tidak sedalam model *fine-tune* novel 7B/12B. | **Penggunaan harian utama** di laptop Celeron / RAM 8 GB. |
| **`Qwen2.5-3B-Instruct-Q5_K_M.gguf`** | **2.07 GB** (`2121.7 MB`) | **RAM 6 GB+**<br>CPU 2 Core+ | • Presisi diksi dan struktur kalimat lebih tajam daripada Q4_K_M.<br>• Tetap enteng di RAM. | • ~15% lebih lambat di CPU Celeron dibanding versi Q4_K_M. | Menulis prosa Bahasa Indonesia di CPU 2–4 Core dengan kualitas lebih rapi. |
| **`Qwen3-1.7B-Q4_K_M.gguf`** | **1.03 GB** (`1056.1 MB`) | **RAM 4 GB+**<br>CPU 2 Core+ | • Ukuran super kecil (~1 GB), sangat cepat di CPU lambat.<br>• Ringan saat membuka banyak aplikasi. | • Kosa kata, variasi gaya bahasa, & pemahaman lore panjang masih terbatas. | *Brainstorming* cepat, merancang beat awal, atau laptop RAM 4 GB. |
| **`gemma-2-2b-it-Q4_K_M.gguf`** | **1.59 GB** (`1629.4 MB`) | **RAM 4 GB+**<br>CPU 2 Core+ | • Gaya kalimat khas Google Gemma terasa hangat, luwes, & ekspresif.<br>• Cepat di CPU 2-Core. | • Penguasaan idiom Bahasa Indonesia & kepatuhan JSON ketat kalah dari Qwen 2.5 3B. | Novel fiksi ringan, narasi personal, atau tulisan berbahasa Inggris. |
| **`Llama-3.2-3B-Instruct-Q4_K_M.gguf`** | **1.88 GB** (`1925.8 MB`) | **RAM 6 GB+**<br>CPU 2 Core+ | • Dialog berbahasa **Inggris** terasa hidup, ringkas, & berirama cepat. | • Untuk prosa **Bahasa Indonesia**, tata bahasa masih sering terasa seperti terjemahan. | Penulis novel berbahasa **Inggris**. |

#### Tier 2 — Menengah Modern ("Upgrade Terbaik untuk RAM 8–12 GB")

| Model (File `.gguf`) | Ukuran File | Min. RAM / CPU | Kelebihan (+) | Kekurangan (-) | Cocok Untuk |
| :--- | :---: | :---: | :--- | :--- | :--- |
| **`Qwen_Qwen3-4B-Q4_K_M.gguf`** | **2.33 GB** (`2381.6 MB`) | **RAM 8 GB+**<br>CPU 2–4 Core+ | • Lompatan kecerdasan nalar adegan, subteks karakter, & Bahasa Indonesia jauh di atas 3B.<br>• Studio otomatis menonaktifkan mode `<think>` (`--reasoning off`) sehingga langsung menulis prosa. | • ~25–35% lebih lambat di CPU Celeron 2-Core dibanding Qwen2.5-3B. | Upgrade kualitas prosa & logika plot yang masih nyaman di RAM 8–12 GB. |

#### Tier 3 — Kelas Sastra & Kreatif Profesional (7B–8B, Ideal CPU 4–8 Core / GPU)

| Model (File `.gguf`) | Ukuran File | Min. RAM / CPU | Kelebihan (+) | Kekurangan (-) | Cocok Untuk |
| :--- | :---: | :---: | :--- | :--- | :--- |
| **`EVA-Qwen2.5-7B-v0.1-IQ4_XS.gguf`** | **3.93 GB** (`4023.0 MB`) | **RAM 8 GB+**<br>CPU 4+ Core / GPU | • **Raja Prosa Kreatif Indonesia/Inggris.** *Fine-tuned* khusus penulisan cerita.<br>• Deskripsi panca indra (*Show Don't Tell*), emosi, & metafora kaya, jauh dari kesan robot. | • Di CPU Celeron 2-Core terasa lambat (butuh beberapa menit per beat 400 kata). | Menulis bab klimaks / polesan sastra akhir, atau jika berjalan di Core i5/Ryzen/GPU. |
| **`Qwen2.5-7B-Instruct-IQ4_XS.gguf`** | **3.93 GB** (`4023.0 MB`) | **RAM 8 GB+**<br>CPU 4+ Core / GPU | • Paling disiplin mematuhi *Phase Guardrails*, aturan dunia kompleks, dan target struktur bab. | • Nada kalimat sedikit lebih formal dibanding EVA-Qwen2.5-7B; lambat di CPU 2-Core. | Novel misteri detektif, *hard sci-fi*, atau fantasi dengan aturan dunia ketat. |
| **`L3-8B-Stheno-v3.2-IQ4_XS.gguf`** | **4.14 GB** (`4241.6 MB`) | **RAM 8 GB+**<br>CPU 4+ Core / GPU | • Spesialis dialog tajam, konflik interpersonal gelap/intens, & adegan aksi/thriller. | • Kurang optimal untuk Bahasa Indonesia murni (lebih bersinar di Bahasa Inggris); lambat di 2-Core. | Novel thriller/aksi/gelap (terutama Bahasa Inggris). |
| **`Qwen_Qwen3-8B-IQ4_XS.gguf`** | **4.25 GB** (`4350.5 MB`) | **RAM 10 GB+**<br>CPU 4+ Core / GPU | • Nalar sebab-akibat antarkarakter paling tajam di kelas 8B & Bahasa Indonesia sangat matang. | • Berat di CPU Celeron 2-Core; butuh RAM luang ~5.3 GB saat aktif. | Penulisan serius jangka panjang di perangkat 4–8 Core atau GPU. |

#### Tier 4 — Kelas Workstation Sastra (12B, Khusus RAM >= 12–16 GB / GPU)

| Model (File `.gguf`) | Ukuran File | Min. RAM / CPU | Kelebihan (+) | Kekurangan (-) | Cocok Untuk |
| :--- | :---: | :---: | :--- | :--- | :--- |
| **`MN-12B-Celeste-V1.9-IQ4_XS.gguf`** | **6.28 GB** (`6430.3 MB`) | **RAM 12–16 GB+**<br>CPU 6+ Core / GPU | • *Creative writing fine-tune* berkelas di atas Mistral Nemo 12B — diksi puitis kaya dan nyaris tanpa klise AI. | • Memakan **~7.6 GB RAM** (terlalu mepet jika membuka browser berat di 12 GB RAM, tidak muat di 8 GB RAM) & sangat lambat tanpa GPU. | PC/Laptop RAM 16 GB+ dengan GPU atau CPU modern cepat. |

---

## 5. Cara Download, Menambah Model Kustom, & Ganti Model (Switch RAM)

Studio menyediakan **3 cara mudah** untuk menambah dan mengganti model AI tanpa pernah mengedit skrip:

### Cara A — Lewat Tombol Pengelola Sumber AI & Model di Web UI (Paling Mudah)
1. Klik badge status AI di pojok kanan atas layar (bertuliskan **`AI: ...`**, **`🌐 API: ...`**, atau **`Model AI OFFLINE • Pilih`**).
2. Di jendela **Pengelola Sumber AI**, Anda memiliki 4 tab:
   - **💾 Model Lokal**: Memilih model `.gguf` lokal (`🔄 Switch & Muat`) atau mengimpor dari folder `Downloads`.
   - **🌐 API Online & Sumber Lain**: Hubungkan Studio ke model online atau server kompatibel lain tanpa membebani CPU/RAM lokal — mendukung preset **OpenRouter** (banyak model & tier gratis `:free`), **Google Gemini** (`AI Studio API`), **Groq**, **OpenAI**, **DeepSeek**, **Mistral AI**, **Anthropic Claude**, serta server lokal/LAN **Ollama**, **LM Studio**, **KoboldCpp**, atau **vLLM**. Dilengkapi pengambil daftar model otomatis (**`🔍 Ambil Daftar Model`**), penguji koneksi (**`⚡ Uji Koneksi API`**), penyimpanan API key lokal terproteksi (`0600` di `backend/.ai_provider_config.json`), serta tombol **`↩️ Kembali ke Mode Lokal`**.
   - **📚 Katalog GGUF**: Lihat daftar lengkap 11 model beserta *RAM minimal*, *Kelebihan (+)*, dan *Kekurangan (-)*, lalu klik **`⬇️ Unduh GGUF`**. Progres unduhan tampil real-time dan dapat dilanjutkan (**`Lanjutkan`**) kapan saja bila koneksi terputus.
   - **➕ Unduh GGUF Kustom**: Tempel **URL HTTPS `.gguf`** (link `/blob/main/` otomatis dikonversi ke `/resolve/main/`) **atau** **Repo ID** HuggingFace + nama file `.gguf`, lalu klik **`⬇️ Verifikasi & Unduh ke Studio`**.

### Cara B — Impor File `.gguf` Hasil Download Manual (Browser / Folder `Downloads`)
Jika Anda mengunduh berkas `.gguf` memakai browser (Chrome/Firefox/Safari) atau IDM ke folder `Downloads` (Linux `~/Downloads/`, Windows `%USERPROFILE%\Downloads\`, macOS `~/Downloads/`):
1. Buka modal Pengelola Model $\rightarrow$ tab **💾 Model Lokal** $\rightarrow$ klik **`🔄 Pindai Disk`**.
2. File `.gguf` yang berada di folder `Downloads` akan terdeteksi di bagian **"📂 File .GGUF Ditemukan di Folder Downloads"**.
3. Klik **`📥 Pindahkan ke Studio (models/)`**, lalu klik **`🔄 Switch & Muat`**.

*(Atau salin langsung secara manual lewat File Manager / Explorer / Finder ke folder `models/` di dalam direktori `novelpro`.)*

### Cara C — Lewat Terminal (`curl` Resumable) atau API Switching Langsung
Contoh mengunduh **Qwen 3 4B (`2.33 GB`)** dengan fitur resume `-C -` di Linux / macOS / Termux (dan `curl.exe` di Windows PowerShell):

**Linux / macOS / Android Termux:**
```bash
cd /path/to/novelpro
curl -L -C - "https://huggingface.co/bartowski/Qwen_Qwen3-4B-GGUF/resolve/main/Qwen_Qwen3-4B-Q4_K_M.gguf" \
  -o models/Qwen_Qwen3-4B-Q4_K_M.gguf.part && \
  mv models/Qwen_Qwen3-4B-Q4_K_M.gguf.part models/Qwen_Qwen3-4B-Q4_K_M.gguf
```

**Windows PowerShell:**
```powershell
cd C:\path\to\novelpro
curl.exe -L -C - "https://huggingface.co/bartowski/Qwen_Qwen3-4B-GGUF/resolve/main/Qwen_Qwen3-4B-Q4_K_M.gguf" -o models\Qwen_Qwen3-4B-Q4_K_M.gguf.part
Move-Item -Force models\Qwen_Qwen3-4B-Q4_K_M.gguf.part models\Qwen_Qwen3-4B-Q4_K_M.gguf
```

Contoh memanggil **API Model Switcher** secara terprogram (Linux/macOS/Windows WSL/PowerShell):
```bash
# Lihat model lokal, progres download, & katalog
curl -s http://127.0.0.1:8000/api/models

# Ganti model aktif di RAM secara otomatis
curl -X POST http://127.0.0.1:8000/api/models/switch \
  -H "Content-Type: application/json" \
  -d '{"model_identifier": "Qwen_Qwen3-4B-Q4_K_M.gguf"}'

# Matikan llama-server untuk membebaskan RAM
curl -X POST http://127.0.0.1:8000/api/models/stop
```

---

## 6. Menggunakan API Model AI Online & Sumber Lain (Gemini, OpenRouter, Groq, OpenAI, Claude, Ollama)

Jika Anda memakai laptop hemat daya (seperti CPU 2-Core), ingin langsung mencoba model raksasa (DeepSeek, Gemini 2.5, Qwen 72B, Claude, GPT-4o), atau ingin menyambung ke server GPU lain (**Ollama / LM Studio / vLLM**), Anda dapat menjalankan seluruh Studio **tanpa perlu mengunduh file `.gguf` atau menyalakan `llama-server` lokal**.

Adapter di [backend/ai_provider.py](backend/ai_provider.py) otomatis mengarahkan ketiga proses AI (**Write Beat Streaming SSE**, **AI Plot Architect / Generate Beats**, dan **Post-Beat State Extractor**) ke provider aktif yang Anda pilih.

### Daftar Preset & Sumber Kompatibel Bawaan

| Provider / Sumber | Protokol | Base URL Bawaan | Contoh Model ID | API Key |
| :--- | :--- | :--- | :--- | :---: |
| **OpenRouter** | `openai_compatible` | `https://openrouter.ai/api/v1` | `deepseek/deepseek-chat-v3-0324:free`, `qwen/qwen-2.5-72b-instruct` | Wajib |
| **Google Gemini** | `openai_compatible` | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.5-flash`, `gemini-2.5-pro` | Wajib |
| **Groq Cloud** | `openai_compatible` | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile`, `qwen-qwq-32b` | Wajib |
| **OpenAI** | `openai_compatible` | `https://api.openai.com/v1` | `gpt-4o-mini`, `gpt-4.1` | Wajib |
| **DeepSeek API** | `openai_compatible` | `https://api.deepseek.com/v1` | `deepseek-chat`, `deepseek-reasoner` | Wajib |
| **Mistral AI** | `openai_compatible` | `https://api.mistral.ai/v1` | `mistral-small-latest`, `mistral-large-latest` | Wajib |
| **Anthropic Claude** | `anthropic` | `https://api.anthropic.com/v1` | `claude-3-5-sonnet-latest`, `claude-3-7-sonnet-latest` | Wajib |
| **Ollama (Lokal / LAN)** | `openai_compatible` | `http://127.0.0.1:11434/v1` | `qwen2.5:7b`, `gemma2:9b` | Opsional |
| **LM Studio / KoboldCpp / vLLM** | `openai_compatible` | `http://127.0.0.1:1234/v1` *(atau URL kustom)* | Sesuai model yang dimuat di server | Opsional |

### Cara Mengaktifkan Lewat Web UI (Paling Praktis)
1. Klik badge status AI di pojok kanan atas layar (bertuliskan **`AI: ...`**, **`🌐 API: ...`**, atau **`Model AI OFFLINE • Pilih`**).
2. Pilih tab **`🌐 API Online & Sumber Lain`**.
3. Klik salah satu kartu **Preset Sumber AI** *(misal Google Gemini, OpenRouter, Groq, DeepSeek, Anthropic, atau Ollama)* untuk mengisi **Protokol** dan **Base URL** secara otomatis.
4. Isi **Nama / ID Model**, atau klik **`🔍 Ambil Daftar Model`** agar Studio mengambil daftar model langsung dari server (`/v1/models`).
5. Tempel **API Key** Anda *(kosongkan jika memakai Ollama/LM Studio lokal tanpa autentikasi)*. Key disimpan secara lokal saja di `backend/.ai_provider_config.json` dengan izin `0600` (sudah dikecualikan di `.gitignore`).
6. *(Opsional)* Biarkan centang **Matikan `llama-server` lokal otomatis** aktif agar RAM ±2 GB langsung dibebaskan saat beralih ke mode online.
7. Klik **`⚡ Uji Koneksi API`** untuk memastikan respon dan latensi berjalan normal, lalu klik **`✅ Simpan & Aktifkan Sumber AI Ini`**.
8. Kapan pun ingin kembali ke model `.gguf` offline lokal, klik **`↩️ Kembali ke Mode Lokal`** atau pilih model di tab **`💾 Model Lokal`**.

### Opsi Konfigurasi via Environment Variables (Headless / CLI)
Jika ingin langsung mengarahkan Studio ke API eksternal saat menyalakan `uvicorn` atau `./start_studio.sh`:
```bash
export NOVEL_AI_PROVIDER="openai_compatible" # atau "anthropic" / "local_llama"
export NOVEL_AI_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai"
export NOVEL_AI_MODEL="gemini-2.5-flash"
export NOVEL_AI_API_KEY="AIzaSy..."
./start_studio.sh
```

### Contoh Pengaturan Provider via REST API (`curl`)
```bash
# Cek status provider aktif (API key tersamar)
curl -s http://127.0.0.1:8000/api/ai/provider

# Aktifkan API Online (contoh: Google Gemini AI Studio)
curl -X POST http://127.0.0.1:8000/api/ai/provider \
  -H "Content-Type: application/json" \
  -d '{
    "provider_type": "openai_compatible",
    "preset_id": "gemini",
    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
    "model_name": "gemini-2.5-flash",
    "api_key": "API_KEY_ANDA",
    "stop_local_llama": true
  }'

# Kembali ke mode lokal llama-server GGUF
curl -X POST http://127.0.0.1:8000/api/ai/provider \
  -H "Content-Type: application/json" \
  -d '{"provider_type": "local_llama", "preset_id": "local_llama"}'
```

---

## 7. Pengamanan Cloudflare Tunnel (Akses Internet Aman)

Jika Anda ingin menulis dari HP/laptop lain di luar rumah via Internet **tanpa membuka port router** (berlaku di Linux, Windows, maupun macOS), gunakan modul keamanan bawaan [backend/security_config.py](backend/security_config.py):

1. **Generate bundel konfigurasi keamanan (sekali saja):**
   - **Linux / macOS:**
     ```bash
     cd /path/to/novelpro
     backend/.venv/bin/python backend/security_config.py --init \
       --domain novel.domain-anda.com \
       --team-domain nama-tim.cloudflareaccess.com \
       --email email-anda@domain.com
     ```
   - **Windows PowerShell:**
     ```powershell
     cd C:\path\to\novelpro
     .\backend\.venv\Scripts\python.exe backend\security_config.py --init `
       --domain novel.domain-anda.com `
       --team-domain nama-tim.cloudflareaccess.com `
       --email email-anda@domain.com
     ```
   Perintah ini membuat:
   - `backend/.env.security` (izin file `0600` berisi token rahasia 256-bit `NOVEL_TUNNEL_SECRET` & `CF_ACCESS_SIGNATURE_SECRET`),
   - `deploy/cloudflared-config.yml`,
   - `deploy/Caddyfile.cloudflare`,
   - `deploy/setup_ufw_cloudflare.sh`, dan panduan lengkap `deploy/PANDUAN_CLOUDFLARE_TUNNEL.md`.

2. **Tutup akses IP langsung & jalankan `cloudflared`:**
   - **Linux:** Jalankan `sudo bash deploy/setup_ufw_cloudflare.sh`. Saat `NOVEL_SECURITY_MODE=STRICT_CLOUDFLARE` aktif di `backend/.env.security`, `start_studio.sh` otomatis mengikat FastAPI hanya pada `127.0.0.1:8000`.
   - **Windows / macOS:** Pasang binary [`cloudflared`](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) (`winget install Cloudflare.cloudflared` di Windows atau `brew install cloudflared` di macOS), pastikan `uvicorn` berjalan dengan `--host 127.0.0.1`, lalu ikuti langkah login & run tunnel di `deploy/PANDUAN_CLOUDFLARE_TUNNEL.md`.
   - FastAPI menolak setiap request tanpa validasi header Cloudflare Tunnel (`X-Novel-Tunnel-Token`, `CF-Access-Client-Signature` HMAC-SHA256, Service Token, atau `Cf-Access-Jwt-Assertion`) dengan respons `403 Forbidden`.

---

## 8. Optimasi ZRAM (Linux) & Troubleshooting Lintas OS

### Aktifkan ZRAM di Linux (Sangat Disarankan di RAM 8 GB)
Jika di Linux Mint / Ubuntu / Debian saat instalasi awal belum menjalankan `sudo` untuk ZRAM, jalankan satu kali di terminal:
```bash
sudo apt update && sudo apt install -y zram-tools
printf "ALGO=zstd\nPERCENT=50\nPRIORITY=100\n" | sudo tee /etc/default/zramswap
printf "vm.swappiness=100\nvm.vfs_cache_pressure=50\n" | sudo tee /etc/sysctl.d/99-mint-ai.conf
sudo systemctl restart zramswap && sudo sysctl --system
```
*(Di **Fedora**, ZRAM umumnya sudah aktif bawaan lewat `systemd-zram-generator`. Di **Arch Linux**, pasang `zram-generator`.)*

### Troubleshooting Lengkap Lintas OS

#### Umum (Semua OS)
- **Teks Bahasa Indonesia keluar kata acak / aneh:**
  Pastikan *KV Cache* tidak memakai `q4_0` pada model kecil (2B–4B) serta `XTC Probability` disetel `0.0` dan `Temperature` di rentang `0.70–0.85` pada **Chapter Mixing Console**. Studio sudah menyetel `f16` otomatis untuk model $\le 2.6\text{ GB}$ dan `q8_0` untuk model `7B+`.
- **Generasi terasa lambat di CPU 2-Core:**
  Gunakan `Qwen2.5-3B-Instruct-Q4_K_M.gguf` atau `Qwen3-1.7B-Q4_K_M.gguf`, tutup tab browser berat lain, dan kurangi target kata per beat ke `300–400` kata.
- **Model Qwen3 mengeluarkan tag `<think>...</think>`:**
  Studio otomatis menambahkan flag `--reasoning off` (atau `--reasoning-budget 0`) pada `llama-server` ketika memuat model bernama `*qwen3*`.
- **Error `401 Unauthorized` saat mengunduh model kustom HuggingFace:**
  Model yang Anda pilih adalah repositori *gated* (memerlukan persetujuan lisensi & token HF). Gunakan rilisan publik dari repositori komunitas seperti **`bartowski/*-GGUF`** atau **`unsloth/*-GGUF`**.
- **Cek log mesin AI & FastAPI secara langsung:**
  - Log `llama-server`: `.logs/llama-server.log`
  - Log `FastAPI` (saat dijalankan lewat `start_studio.sh`): `.logs/fastapi.log`
- **Error saat memakai API AI Online (`HTTP 401` / `404` / `429`):**
  - `401 Unauthorized` / `403`: API Key salah, kadaluarsa, atau belum aktif untuk model tersebut.
  - `404` / `model_not_found`: pastikan ID model sesuai dengan daftar milik provider (klik tombol **`🔍 Ambil Daftar Model`** di tab **`🌐 API Online`**).
  - `429 Too Many Requests`: kuota/rate limit tier gratis provider tercapai sementara — tunggu sebentar atau beralih ke model lain/mode lokal.
  - Menyambung ke **Ollama di PC lain dalam Wi-Fi LAN**: jalankan `OLLAMA_HOST=0.0.0.0 ollama serve` pada PC GPU Anda, lalu isi `Base URL` di Studio dengan `http://<IP-PC-GPU>:11434/v1`.

#### Khusus Windows 10 / 11
- **`llama-server.exe` gagal start / error hilang `llama.dll` atau `ggml.dll`:**
  Pastikan seluruh file `.dll` hasil ekstrak `.zip` berada di folder `bin\` yang sama dengan `llama-server.exe`. Jika Anda memakai versi NVIDIA CUDA, wajib mengekstrak juga `cudart-llama-bin-win-cuda-12.4-x64.zip` ke folder `bin\`.
- **`Activate.ps1 cannot be loaded because running scripts is disabled`:**
  Tidak perlu menjalankan `Activate.ps1`! Gunakan perintah lengkap `.\backend\.venv\Scripts\python.exe -m ...` sebagaimana dicontohkan di Bagian 2B.
- **HP tidak bisa membuka `http://<IP-WINDOWS>:8000`:**
  Periksa apakah profil jaringan Wi-Fi Windows Anda bertipe *Public* (ubah ke *Private* di *Settings* $\rightarrow$ *Network & internet* $\rightarrow$ *Wi-Fi* $\rightarrow$ *Private network*), dan pastikan aturan Windows Defender Firewall (`New-NetFirewallRule`) sudah dijalankan sebagai Administrator.

#### Khusus macOS (Apple Silicon / Intel)
- **Popup `"llama-server" cannot be opened because the developer cannot be verified`:**
  Jalankan `xattr -dr com.apple.quarantine bin/` dari direktori `novelpro`.
- **`dyld: Library not loaded` saat menjalankan `llama-server` manual:**
  Pastikan semua file `.dylib` (dan `.metallib`) hasil ekstrak berada di folder `bin/` bersama `llama-server`, lalu jalankan lewat tombol **Switch & Muat** di Web UI atau ekspor `DYLD_LIBRARY_PATH="$(pwd)/bin:$DYLD_LIBRARY_PATH"`.

#### Khusus Android Termux
- **`pip install` gagal mengompilasi `lxml` atau `pydantic-core`:**
  Jangan instal dari source! Gunakan paket native Termux `pkg install -y python-lxml python-pydantic`, lalu buat venv memakai flag `--system-site-packages` (lihat Bagian 2D).
- **Server mati tiba-tiba saat layar HP mati / pindah ke browser:**
  Jalankan `termux-wake-lock` sebelum menyalakan `uvicorn`, dan matikan *Battery Optimization* untuk aplikasi Termux di *Settings* Android.
