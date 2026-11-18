# The Zen Literary Studio — AI Novel Writing Studio

Aplikasi web penulisan novel panjang (*long-form fiction*) yang dirancang agar **ringan, konsisten menjaga alur cerita antar-bab, bebas klise moralistik AI, dan fleksibel**: bisa dibuka **langsung di browser via GitHub Pages tanpa instalasi**, dijalankan **100% offline di perangkat sendiri** (`llama-server`), maupun tersambung ke **API AI Online / server eksternal** (*Google Gemini, OpenRouter, Groq, OpenAI, DeepSeek, Mistral, Anthropic Claude, Ollama, atau LM Studio*).

> 🌐 **Langsung Pakai Online (GitHub Pages — Tanpa Install):** **[https://khisanafif.github.io/novelpro/](https://khisanafif.github.io/novelpro/)**
> *(Setelah halaman GitHub Pages diaktifkan dari Settings repo, siapa pun dapat langsung menulis novel di browser HP/laptop menggunakan API Key sendiri, dengan penyimpanan browser otomatis & ekspor `.EPUB` / `.MD` / Backup `.JSON`.)*

Tersedia juga versi instalasi lokal untuk **Linux (Mint / Ubuntu / Debian / Arch / Fedora)**, **Windows 10/11**, **macOS (Apple Silicon & Intel)**, serta **Android (Termux)** dengan dukungan `llama-server` offline.

---

## Daftar Isi

### Bagian I — Penjelasan & Pengenalan Konsep *(Baca Ini Dulu)*
1. [Apa Itu The Zen Literary Studio?](#1-apa-itu-the-zen-literary-studio)
2. [Mengenal Konsep & Istilah Penting di Studio](#2-mengenal-konsep--istilah-penting-di-studio)
3. [Arsitektur, Spesifikasi Perangkat, & Struktur Folder](#3-arsitektur-spesifikasi-perangkat--struktur-folder)

### Bagian II — Tutorial Lengkap Langkah Demi Langkah
4. [Tutorial 1 — Instalasi & Menjalankan Studio di Semua OS](#4-tutorial-1--instalasi--menjalankan-studio-di-semua-os)
   - [4A. Linux (Linux Mint / Ubuntu / Debian, serta Arch / Fedora / ARM64)](#4a-linux-linux-mint--ubuntu--debian-serta-arch--fedora--arm64)
   - [4B. Windows 10 / 11 (x64 & ARM64 — PowerShell)](#4b-windows-10--11-x64--arm64--powershell)
   - [4C. macOS (Apple Silicon M1–M4 & Intel x64 — Terminal)](#4c-macos-apple-silicon-m1m4--intel-x64--terminal)
   - [4D. Android (Termux ARM64 — Langsung di HP/Tablet)](#4d-android-termux-arm64--langsung-di-hptablet)
   - [4E. Daftar Binary Resmi llama.cpp (`b12428`) Lintas OS](#4e-daftar-binary-resmi-llamacpp-b12428-lintas-os)
5. [Tutorial 2 — Memilih & Menghubungkan Sumber AI (Online API atau Offline GGUF)](#5-tutorial-2--memilih--menghubungkan-sumber-ai-online-api-atau-offline-gguf)
   - [5A. Cara Pakai API Model AI Online / Server Eksternal](#5a-cara-pakai-api-model-ai-online--server-eksternal)
   - [5B. Cara Memilih, Mengunduh, & Mengganti Model Lokal (`.GGUF`)](#5b-cara-memilih-mengunduh--mengganti-model-lokal-gguf)
6. [Tutorial 3 — Panduan Menulis Novel dari Awal sampai Ekspor](#6-tutorial-3--panduan-menulis-novel-dari-awal-sampai-ekspor)
7. [Tutorial Lanjutan — Akses Internet Aman via Cloudflare Tunnel (Opsional)](#7-tutorial-lanjutan--akses-internet-aman-via-cloudflare-tunnel-opsional)
8. [Lampiran — Optimasi ZRAM (Linux) & Troubleshooting Cepat](#8-lampiran--optimasi-zram-linux--troubleshooting-cepat)

---

# Bagian I — Penjelasan & Pengenalan Konsep

## 1. Apa Itu The Zen Literary Studio?

Saat menulis novel panjang dengan AI chat biasa, penulis hampir selalu menghadapi tiga masalah: **AI cepat lupa kejadian bab-bab awal**, **alur cerita suka meloncat terlalu cepat ke klimaks**, dan **gaya tulisannya penuh kalimat klise** (*"tanpa mereka sadari..."*, *"waktu seakan berhenti..."*).

**The Zen Literary Studio** memecahkan masalah tersebut dengan memisahkan penyusunan struktur cerita, ingatan dunia novel, dan penulisan prosa per adegan kecil (*Micro-Beat*) di dalam satu ruang kerja editorial yang rapi dan hemat RAM.

### Dua Cara Menggunakan AI (Pilih yang Paling Cocok)

| Jalur AI | Cara Kerja | Cocok Untuk Siapa? | Perlu Install / Download `.gguf`? |
| :--- | :--- | :--- | :---: |
| **🌍 Versi Web GitHub Pages (Browser Murni)** | Buka langsung di browser, tempel API Key (*OpenRouter, Google Gemini, Groq, OpenAI, Mistral, Claude*), naskah disimpan di `localStorage` browser & bisa diekspor `.EPUB` / `.MD` / `.JSON`. | Siapa saja yang ingin **langsung mencoba atau menulis dari HP/laptop/Chromebook tanpa terminal**. | **Tidak perlu sama sekali** |
| **🌐 Studio Lokal + API Online / Server Lain** | FastAPI lokal terhubung ke Google Gemini, OpenRouter, Groq, ChatGPT, DeepSeek, Claude, atau Ollama/LM Studio LAN + database SQLite FTS5. | Penulis yang ingin database SQLite lokal permanen sekaligus kecepatan cloud. | **Tidak perlu `.gguf`** *(cukup Python)* |
| **🖥️ Mode Lokal Offline (`.GGUF`)** | AI berjalan penuh di komputer/HP Anda memakai `llama-server` (`llama.cpp`). | Penulis yang mengutamakan **privasi 100% offline**, bebas kuota API, atau punya GPU/Apple Silicon. | **Ya** *(panduan lengkap di Tutorial 1 & 2B)* |

> Anda bisa berpindah antara Mode Online dan Mode Offline **kapan saja dari Web UI** tanpa kehilangan naskah.

---

## 2. Mengenal Konsep & Istilah Penting di Studio

Sebelum mengikuti tutorial instalasi, pahami terlebih dahulu 6 komponen inti yang akan Anda temui di antarmuka Studio:

1. **🧭 Core Compass (Story Bible — Tier 1):**
   Kompas induk novel Anda: judul, nama penulis/pena, genre, premis, tujuan besar cerita (*North Star*), sudut pandang (POV), contoh ritme prosa (*Style Sample*), serta daftar frasa klise terlarang (*Banned Phrases*).
2. **📈 Phase-Range Timeline & Guardrails:**
   Pita di bagian atas layar yang membagi novel menjadi rentang bab (misalnya *Bab 1–3 Opening*, *Bab 4–9 Rising Action*, hingga *Ending*). Setiap fase punya **Guardrails** (aturan pengunci agar AI tidak membocorkan akhir cerita atau menyelesaikan konflik sebelum waktunya).
3. **📚 Codex / Lorebook & SQLite FTS5 BM25 (`<1 ms`):**
   Basis data berisi kartu **Karakter**, **Lokasi**, **Aturan Dunia**, **Item**, dan **Lore**:
   - Entitas yang diberi pin (**📌**) selalu diingat AI di setiap adegan.
   - Entitas lainnya otomatis dipanggil dalam `<1 milidetik` oleh mesin pencari teks SQLite FTS5 BM25 hanya ketika kata kuncinya relevan dengan adegan yang sedang ditulis — tanpa memakan RAM tambahan seperti *Vector DB*.
   - Setiap karakter memiliki **`Current State`** (lokasi terkini, kondisi fisik, emosi, inventaris, dan apa yang baru ia ketahui).
4. **🎬 Micro-Beats & 5 Slider Narrative Mix:**
   Satu bab tidak ditulis sekaligus dalam satu kali tekan (yang sering melantur), melainkan dipecah menjadi kartu **Micro-Beat** (±350–400 kata per adegan). Setiap bab diatur lewat 5 slider (**World-Building**, **Psikologi**, **Sensorik**, **Dialog**, dan **Aksi**) serta tiap beat memiliki **Titik Berhenti Mutlak (*Stopping Point*)**.
5. **🧠 Memori 4-Tier:**
   Setiap kali Anda menekan **`▶️ Write Beat`**, backend merakit konteks secara terstruktur:
   - *Tier 1:* Kompas Novel, *Guardrails* fase aktif, & aturan dunia *pinned*.
   - *Tier 2:* Kondisi terkini karakter & lokasi adegan dari *Codex*.
   - *Tier 3:* Ringkasan cerita lintas-bab, memori episodik FTS5 BM25, + **400 kata terakhir** persis sebelum beat ini agar sambungan kalimat mulus.
   - *Tier 4:* Target kata, setelan 5 slider, instruksi kejadian, & titik berhenti beat.
6. **🔄 Extract State:**
   Setelah satu beat selesai ditulis, tekan **`🧠 Extract State & Update Codex`** untuk memperbarui ringkasan kejadian dan kondisi karakter ke SQLite secara otomatis (tersedia mode **⚡ Cepat `<1ms`** yang hemat CPU 2-Core dan **🧠 AI Extractor Penuh**).

---

## 3. Arsitektur, Spesifikasi Perangkat, & Struktur Folder

### Spesifikasi Minimal
- **Python:** versi `3.10` – `3.12` (disarankan `3.12`).
- **RAM:**
  - *Mode API Online:* sangat ringan (**< 300 MB RAM** untuk FastAPI + browser).
  - *Mode Lokal GGUF:* minimal **4 GB** (model 1.7B–3B), disarankan **8–16 GB** (3B–8B, atau 12B di RAM 16 GB+).
- **Koneksi Internet:** Tidak wajib saat memakai Mode Lokal (seluruh aset UI seperti `alpine.min.js` dan CSS sudah tersimpan offline di `frontend/vendor/`). Wajib hanya saat memakai API Online atau mengunduh model baru.

### Struktur Folder Proyek
```text
novelpro/
├── backend/
│   ├── main.py                # Server API FastAPI + Antrean 1-Slot + pemantau RAM lintas OS
│   ├── ai_provider.py         # Adapter Multi-Provider AI (Lokal llama-server, OpenAI-Compat, Claude)
│   ├── database.py            # SQLite WAL + FTS5 BM25 + migrasi skema + Backup/Restore JSON
│   ├── engine.py              # Perencana Micro-Beats, 5 Slider Mix, & Filter Anti-Klise
│   ├── memory_manager.py      # Perakit Memori 4-Tier (<1ms FTS5) & Post-Beat State Extractor
│   ├── model_manager.py       # Pengelola model lokal .GGUF, switcher RAM, & downloader HuggingFace
│   ├── exporter.py            # Compiler naskah (.EPUB standar penerbit, HTML siap cetak/PDF, & .MD)
│   ├── security_config.py     # Pengaman Cloudflare Tunnel Zero Trust & generator UFW
│   ├── requirements.txt       # Daftar paket Python
│   ├── .venv/                 # Environment Python lokal (dibuat saat setup)
│   └── novel_studio.db        # Database naskah & Story Bible (otomatis dibuat saat start)
├── frontend/
│   ├── vendor/                # Aset offline (alpine.min.js + studio-utilities.css)
│   ├── web_runtime.js         # Runtime serverless murni browser (localStorage, CORS AI, EPUB ZIP)
│   ├── index.html             # Antarmuka The Zen Literary Studio
│   ├── styles.css             # Tipografi buku cetak & tata letak responsif Desktop/HP
│   └── app.js                 # Logika UI, deteksi mode FastAPI vs Browser, SSE, Cari & Ganti
├── docs/                      # Output build statis siap host di GitHub Pages (+ .nojekyll)
├── scripts/
│   └── sync_github_pages.py   # Menyinkronkan frontend/ -> docs/ secara identik
├── .github/workflows/
│   └── pages.yml              # GitHub Actions otomatis deploy GitHub Pages saat push ke main
├── bin/                       # Tempat binary llama-server (.so/.dylib/.dll) untuk mode offline
├── models/                    # Tempat file model .gguf untuk mode offline
├── Caddyfile                  # Reverse proxy statis opsional (port 3000)
├── setup_mint_8gb.sh          # Installer otomatis untuk Linux Mint / Ubuntu / Debian
├── start_studio.sh            # Menyalakan Studio & menampilkan alamat akses Desktop + HP (Linux)
├── stop_studio.sh             # Mematikan Studio & menyimpan database bersih (Linux)
└── NovelStudio.desktop        # Ikon peluncur 1-klik di Menu Aplikasi Linux
```

---

# Bagian II — Tutorial Lengkap Langkah Demi Langkah

## 4. Tutorial 1 — Instalasi & Menjalankan Studio di Semua OS

> **Tips Memilih Langkah untuk Pemula:**
> - **Tanpa Instalasi (Paling Praktis):** Gunakan **Versi Web GitHub Pages** di bawah — cukup buka browser dan masukkan API Key.
> - **Jika ingin database SQLite di komputer + API Online:** selesaikan langkah **Install Python/Environment** dan **Menyalakan Studio**, lalu lanjut ke **[Bagian 5A](#5a-cara-pakai-api-model-ai-online--server-eksternal)**.
> - **Jika ingin 100% Offline Lokal:** ikuti semua sub-langkah termasuk menyalin `llama-server` ke `bin/` dan model `.gguf` ke `models/`.

---

### Versi Instan — Langsung Pakai di GitHub Pages (Tanpa Install)

Pengguna dapat langsung membuka Studio dari HP, tablet, atau laptop tanpa Python maupun server apa pun:

1. **Buka alamat Web Studio:** `https://khisanafif.github.io/novelpro/`
2. Klik badge AI di pojok kanan atas (**`🌐 Pilih AI & API Key`**).
3. **Tempel API Key apa saja** (*Google Gemini, OpenRouter, Groq, OpenAI, Mistral, Anthropic Claude, xAI, atau HuggingFace* — tidak perlu memilih provider satu per satu; key hanya tersimpan di browser perangkat tersebut).
4. Klik **`🚀 Auto-Detect & Langsung Jalankan AI`** — Studio otomatis mengenali provider Anda, memilih model aktif generasi terbaru langsung dari server API, menguji koneksi, dan siap dipakai menulis.
5. **Penyimpanan & Pindah Perangkat:** Seluruh novel, Codex, Phase, dan riwayat revisi tersimpan otomatis di `localStorage` browser dan dapat diekspor menjadi **`.EPUB`**, **`.MD`**, **HTML Siap Cetak/PDF**, maupun **Backup `.JSON`** (format `.JSON` 100% kompatibel dengan Studio versi Python/Desktop!).

<details>
<summary>Untuk Pemilik Repo: Cara Mengaktifkan GitHub Pages di Repositori Anda</summary>

1. Pastikan folder `docs/` dan workflow `.github/workflows/pages.yml` sudah di-push ke branch `main`. *(Setiap kali mengedit `frontend/`, jalankan `python3 scripts/sync_github_pages.py` sebelum commit).*
2. Buka repositori GitHub Anda $\rightarrow$ **Settings** $\rightarrow$ **Pages**.
3. Di bagian **Build and deployment**, pilih salah satu:
   - **GitHub Actions** *(otomatis ter-deploy setiap `git push` ke `main` via `.github/workflows/pages.yml`)*, **ATAU**
   - **Deploy from a branch** $\rightarrow$ Branch **`main`**, folder **`/docs`** $\rightarrow$ **Save**.
4. Tunggu ±1 menit, lalu akses **`https://<username>.github.io/<repo>/`**.

</details>

---

### 4A. Linux (Linux Mint / Ubuntu / Debian, serta Arch / Fedora / ARM64)

#### Langkah 1 — Instalasi Environment Python & Database
- **Linux Mint / Ubuntu / Debian (Otomatis dengan 1 skrip):**
  ```bash
  cd /path/to/novelpro
  chmod +x setup_mint_8gb.sh start_studio.sh stop_studio.sh
  ./setup_mint_8gb.sh
  ```
  Skrip ini otomatis membuat `backend/.venv`, menginstal `backend/requirements.txt`, membuat database awal lengkap dengan 1 proyek contoh (*Starter Template*), dan mendaftarkan ikon ke Menu Aplikasi (`NovelStudio.desktop`).
- **Arch Linux / Fedora / Distro Lain:**
  ```bash
  # Arch / Manjaro:
  sudo pacman -S --needed python python-pip curl sqlite tar
  # Fedora:
  sudo dnf install -y python3 python3-pip curl sqlite tar

  cd /path/to/novelpro
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install --upgrade pip
  backend/.venv/bin/pip install -r backend/requirements.txt
  ```

#### Langkah 2 — *(Khusus Mode Offline Lokal)* Pasang `llama-server` ke `bin/`
Jika belum ada `bin/llama-server` *(untuk contoh CPU x64 standar)*:
```bash
mkdir -p bin models /tmp/llama-linux
curl -L "https://github.com/ggml-org/llama.cpp/releases/download/b12428/llama-b12428-bin-ubuntu-x64.tar.gz" -o /tmp/llama-linux.tar.gz
tar -xzf /tmp/llama-linux.tar.gz -C /tmp/llama-linux
find /tmp/llama-linux -type f \( -name "llama-server" -o -name "*.so*" \) -exec cp -P {} bin/ \;
chmod +x bin/llama-server
```
*(Untuk GPU Vulkan / NVIDIA CUDA / AMD ROCm / ARM64, ganti nama file `.tar.gz` sesuai tabel di [Bagian 4E](#4e-daftar-binary-resmi-llamacpp-b12428-lintas-os).)*

#### Langkah 3 — Menyalakan & Mematikan Studio
- **Menyalakan:**
  ```bash
  cd /path/to/novelpro
  ./start_studio.sh
  ```
  *(Opsi tambahan: `./start_studio.sh --no-browser` tanpa membuka browser, atau `./start_studio.sh --tunnel` bersama `cloudflared`. Bisa juga klik ikon **The Zen Literary Studio** di Start Menu $\rightarrow$ Office).*
- **Membuka di Browser:** `http://localhost:8000` (atau buka alamat IP Wi-Fi yang tercetak di terminal dari HP Anda; jika UFW aktif, buka port LAN sekali saja: `sudo ufw allow from 192.168.0.0/16 to any port 8000 proto tcp`).
- **Mematikan:**
  ```bash
  cd /path/to/novelpro
  ./stop_studio.sh
  ```

---

### 4B. Windows 10 / 11 (x64 & ARM64 — PowerShell)

#### Langkah 1 — Pasang Python & Paket Studio
1. Instal **Python 3.10–3.12** dari [python.org/downloads](https://www.python.org/downloads/) *(**WAJIB centang "Add python.exe to PATH"** saat instalasi)*, atau via PowerShell:
   ```powershell
   winget install -e --id Python.Python.3.12
   ```
2. Buka **Windows PowerShell** di dalam folder proyek `novelpro`, lalu buat environment Python:
   ```powershell
   cd C:\path\to\novelpro
   python -m venv backend\.venv
   .\backend\.venv\Scripts\python.exe -m pip install --upgrade pip
   .\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
   ```
   *(Memanggil `.\backend\.venv\Scripts\python.exe` langsung menghindari masalah `ExecutionPolicy` pada PowerShell.)*

#### Langkah 2 — *(Khusus Mode Offline Lokal)* Pasang `llama-server.exe` & Model Awal
1. Unduh & ekstrak binary `llama-server.exe` ke folder `bin\` *(contoh CPU x64; lihat [Bagian 4E](#4e-daftar-binary-resmi-llamacpp-b12428-lintas-os) untuk Vulkan GPU / NVIDIA CUDA / ARM64)*:
   ```powershell
   New-Item -ItemType Directory -Force -Path bin, models, "$env:TEMP\llama-win" | Out-Null
   Invoke-WebRequest -Uri "https://github.com/ggml-org/llama.cpp/releases/download/b12428/llama-b12428-bin-win-cpu-x64.zip" -OutFile "$env:TEMP\llama-win.zip"
   Expand-Archive -Path "$env:TEMP\llama-win.zip" -DestinationPath "$env:TEMP\llama-win" -Force
   Get-ChildItem -Path "$env:TEMP\llama-win" -Recurse -Include "llama-server.exe","*.dll" | Copy-Item -Destination "bin\" -Force
   ```
   *(Jika memakai versi CUDA GPU, ekstrak juga `cudart-llama-bin-win-cuda-12.4-x64.zip` ke folder `bin\` yang sama.)*
2. *(Opsional lewat terminal — bisa juga lewat Web UI nanti)* Unduh model awal ke `models\`:
   ```powershell
   curl.exe -L -C - "https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q4_K_M.gguf" -o models\Qwen2.5-3B-Instruct-Q4_K_M.gguf
   ```

#### Langkah 3 — Menyalakan, Mengakses dari HP, & Mematikan
1. **Jalankan Studio (1 terminal saja):**
   ```powershell
   .\backend\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 0.0.0.0 --port 8000 --workers 1
   ```
2. Buka **`http://localhost:8000`** di Chrome/Edge.
   - Jika memakai **Mode Lokal**: klik badge status AI di pojok kanan atas $\rightarrow$ tab **`💾 Model Lokal`** $\rightarrow$ klik **`🔄 Switch & Muat`**.
   - Jika memakai **API Online**: buka tab **`🌐 API Online & Sumber Lain`** ([Bagian 5A](#5a-cara-pakai-api-model-ai-online--server-eksternal)).
   - *(Opsional cara manual 2 terminal untuk memantau log AI langsung: jalankan `.\bin\llama-server.exe -m .\models\Qwen2.5-3B-Instruct-Q4_K_M.gguf --host 127.0.0.1 --port 8080 --ctx-size 8192 --parallel 1 --cache-type-k f16 --cache-type-v f16 --load-mode mmap --flash-attn auto` — tambahkan `-ngl 99` untuk GPU Vulkan/CUDA).*
3. **Akses dari HP lewat Wi-Fi:** cek IP via `ipconfig` (`IPv4 Address`, misal `192.168.1.24`), lalu jalankan sekali di PowerShell *Run as Administrator*:
   ```powershell
   New-NetFirewallRule -DisplayName "Zen Literary Studio LAN 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Profile Private -Action Allow
   ```
4. **Mematikan:** klik **`🛑 Matikan AI Lokal (Bebaskan RAM)`** di Web UI (jika memakai model lokal), lalu tekan **`Ctrl+C`** di PowerShell.

---

### 4C. macOS (Apple Silicon M1–M4 & Intel x64 — Terminal)

#### Langkah 1 — Pasang Python & Environment Studio
```zsh
brew install python@3.12
cd /path/to/novelpro
python3.12 -m venv backend/.venv
backend/.venv/bin/pip install --upgrade pip
backend/.venv/bin/pip install -r backend/requirements.txt
```

#### Langkah 2 — *(Khusus Mode Offline Lokal)* Pasang `llama-server`
- **Cara A (Binary Resmi ke `bin/` — Metal GPU aktif otomatis di Mac M1–M4):**
  ```zsh
  mkdir -p bin models /tmp/llama-mac
  # Untuk Mac Intel x64, ganti "macos-arm64" menjadi "macos-x64"
  curl -L "https://github.com/ggml-org/llama.cpp/releases/download/b12428/llama-b12428-bin-macos-arm64.tar.gz" -o /tmp/llama-mac.tar.gz
  tar -xzf /tmp/llama-mac.tar.gz -C /tmp/llama-mac
  find /tmp/llama-mac -type f \( -name "llama-server" -o -name "*.dylib" -o -name "*.metallib" \) -exec cp -P {} bin/ \;
  chmod +x bin/llama-server
  # Wajib agar macOS Gatekeeper mengizinkan binary berjalan tanpa popup blokir
  xattr -dr com.apple.quarantine bin/
  ```
- **Cara B (Alternatif Homebrew):** `brew install llama.cpp`.
- *(Opsional unduh model awal via terminal)*:
  ```zsh
  curl -L -C - "https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q4_K_M.gguf" -o models/Qwen2.5-3B-Instruct-Q4_K_M.gguf
  ```

#### Langkah 3 — Menyalakan & Mematikan Studio
```zsh
backend/.venv/bin/python -m uvicorn main:app --app-dir backend --host 0.0.0.0 --port 8000 --workers 1
```
Buka **`http://localhost:8000`**, lalu aktifkan model lewat badge AI di pojok kanan atas (**Mode Lokal** maupun **API Online**). Untuk akses Wi-Fi dari iPhone/iPad/Android, cek IP via `ipconfig getifaddr en0` lalu buka `http://<IP-MAC>:8000`. Untuk mematikan, klik **`🛑 Matikan AI Lokal`** di UI lalu tekan `Ctrl+C` di Terminal.

---

### 4D. Android (Termux ARM64 — Langsung di HP/Tablet)

Anda dapat menulis langsung dari HP Android secara offline (`Qwen3-1.7B`) maupun memakai **API Online** (jauh lebih hemat baterai!).

1. **Pasang paket di Termux** *(gunakan aplikasi Termux versi F-Droid atau GitHub Releases, bukan Play Store)*:
   ```bash
   pkg update && pkg upgrade -y
   pkg install -y git python python-pip python-lxml python-pydantic curl tar libandroid-spawn
   ```
   *(Paket `python-lxml` dan `python-pydantic` dari `pkg` mencegah gagal kompilasi C/Rust di Android.)*
2. **Setup Environment Python:**
   ```bash
   cd ~/novelpro
   python -m venv --system-site-packages backend/.venv
   backend/.venv/bin/pip install fastapi==0.115.5 uvicorn==0.32.1 httpx==0.28.0 EbookLib==0.18 six==1.16.0
   ```
3. ***(Khusus Mode Offline Lokal di HP)* Pasang `llama-server` & model ringan (`1.03 GB`):**
   ```bash
   mkdir -p bin models /tmp/llama-and
   # Khusus Snapdragon GPU Adreno bisa memakai llama-b12428-bin-android-arm64-snapdragon.tar.gz
   curl -L "https://github.com/ggml-org/llama.cpp/releases/download/b12428/llama-b12428-bin-android-arm64.tar.gz" -o /tmp/llama-and.tar.gz
   tar -xzf /tmp/llama-and.tar.gz -C /tmp/llama-and
   find /tmp/llama-and -type f \( -name "llama-server" -o -name "*.so*" \) -exec cp -P {} bin/ \;
   chmod +x bin/llama-server
   curl -L -C - "https://huggingface.co/unsloth/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q4_K_M.gguf" -o models/Qwen3-1.7B-Q4_K_M.gguf
   ```
4. **Menyalakan & Mematikan:**
   ```bash
   termux-wake-lock 2>/dev/null || true
   backend/.venv/bin/python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
   ```
   Buka Chrome Android ke **`http://127.0.0.1:8000`**, lalu pilih API Online atau model lokal di kanan atas. Saat selesai: klik **`🛑 Matikan AI Lokal`** $\rightarrow$ `Ctrl+C` di Termux $\rightarrow$ `termux-wake-unlock`.

---

### 4E. Daftar Binary Resmi `llama.cpp` (`b12428`) Lintas OS

Seluruh arsip berasal dari rilis resmi [ggml-org/llama.cpp `b12428`](https://github.com/ggml-org/llama.cpp/releases/tag/b12428):

| Sistem Operasi & Hardware | Nama File Asset (`b12428`) | Ukuran | Catatan |
| :--- | :--- | :---: | :--- |
| **Linux x64 (CPU)** | `llama-b12428-bin-ubuntu-x64.tar.gz` | 22.4 MB | Bawaan paling stabil untuk semua laptop/PC Linux x64. |
| **Linux x64 (Vulkan GPU)** | `llama-b12428-bin-ubuntu-vulkan-x64.tar.gz` | 34.7 MB | GPU Intel/AMD/NVIDIA modern via Vulkan. |
| **Linux x64 (NVIDIA CUDA 12.8)** | `llama-b12428-bin-ubuntu-cuda-12.8-x64.tar.gz` | 190.8 MB | NVIDIA GeForce RTX/GTX driver CUDA 12.x+. |
| **Linux x64 (AMD ROCm 10.0)** | `llama-b12428-bin-ubuntu-rocm-10.0-x64.tar.gz` | 260.2 MB | GPU AMD Radeon dengan stack ROCm. |
| **Linux ARM64 (CPU)** | `llama-b12428-bin-ubuntu-arm64.tar.gz` | 18.2 MB | Raspberry Pi 5 / SBC / server ARM64. |
| **Windows x64 (CPU)** | `llama-b12428-bin-win-cpu-x64.zip` | 24.0 MB | Semua Windows 10/11 Intel & AMD. |
| **Windows x64 (Vulkan GPU)** | `llama-b12428-bin-win-vulkan-x64.zip` | 36.5 MB | Intel Arc, Radeon iGPU/dGPU, atau NVIDIA tanpa CUDA Toolkit. |
| **Windows x64 (NVIDIA CUDA 12.4)** | `llama-b12428-bin-win-cuda-12.4-x64.zip` | 305.3 MB | **Wajib** disertai `cudart-llama-bin-win-cuda-12.4-x64.zip` (`373.3 MB`). |
| **Windows ARM64 (CPU)** | `llama-b12428-bin-win-cpu-arm64.zip` | 12.9 MB | Windows 11 Snapdragon ARM64. |
| **macOS Apple Silicon (Metal)** | `llama-b12428-bin-macos-arm64.tar.gz` | 16.2 MB | M1/M2/M3/M4 (Metal GPU otomatis aktif). |
| **macOS Intel (CPU x64)** | `llama-b12428-bin-macos-x64.tar.gz` | 12.2 MB | Mac Intel x86_64. |
| **Android Termux ARM64** | `llama-b12428-bin-android-arm64.tar.gz` | 75.8 MB | Semua HP/Tablet Android ARM64. |
| **Android Snapdragon (OpenCL)** | `llama-b12428-bin-android-arm64-snapdragon.tar.gz` | 63.4 MB | Khusus SoC Qualcomm Snapdragon. |

---

## 5. Tutorial 2 — Memilih & Menghubungkan Sumber AI (Online API atau Offline GGUF)

### 5A. Cara Pakai API Model AI Online / Server Eksternal

Dengan adapter [backend/ai_provider.py](backend/ai_provider.py), seluruh proses AI (**Write Beat Streaming**, **Generate Beat Plan**, dan **AI State Extractor**) langsung berjalan lewat provider pilihan Anda dengan kecepatan cloud atau server GPU lokal lain.

#### Daftar Sumber yang Didukung Auto-Detect Otomatis
| Provider / Sumber | Format Key / Deteksi Otomatis | Endpoint Otomatis | Pemilihan Model |
| :--- | :--- | :--- | :--- |
| **Google Gemini** *(AI Studio)* | Awalan `AIza...` | `https://generativelanguage.googleapis.com/v1beta/openai` | Live dari `/v1beta/models` (versi aktif terbaru otomatis) |
| **OpenRouter** | Awalan `sk-or-...` | `https://openrouter.ai/api/v1` | Prioritas `:free` / `openrouter/free` aktif |
| **Groq Cloud** | Awalan `gsk_...` | `https://api.groq.com/openai/v1` | Live dari `/models` |
| **Anthropic Claude** | Awalan `sk-ant-...` | `https://api.anthropic.com/v1` | Live dari `/v1/models` terbaru |
| **OpenAI & DeepSeek** | Awalan `sk-proj-...` / `sk-...` | Auto-probe OpenAI / DeepSeek / OpenRouter | Live dari `/models` |
| **Mistral AI / xAI / HuggingFace** | `xai-`, `hf_`, atau probe key umum | Endpoint resmi masing-masing | Live dari `/models` |
| **Ollama / LM Studio** *(Lokal/LAN)* | Scan tanpa key / `Opsi Lanjutan` | `http://127.0.0.1:11434/v1` / `1234/v1` | Model lokal yang termuat |

#### Langkah Mengaktifkan Lewat Web UI (Cukup Tempel API Key Apa Saja)
1. Klik badge status AI di pojok kanan atas layar (`AI: ...` / `🌐 Pilih AI & API Key`).
2. Buka tab **`🌐 API Online (Auto-Detect Key)`**.
3. **Tempel API Key AI Anda** di satu kolom yang tersedia *(Google Gemini, OpenRouter, Groq, OpenAI, Claude, DeepSeek, Mistral, xAI, atau HuggingFace — tidak perlu memilih kartu provider secara terpisah)*.
4. Klik **`🚀 Auto-Detect & Langsung Jalankan AI`**. Studio langsung mengenali sumber API Key Anda, membaca daftar model terbaru yang aktif di akun Anda, memverifikasi respons chat hingga `200 OK`, lalu langsung siap menulis.
5. *(Opsional)* Buka **`▸ Pengaturan Lanjutan`** hanya jika Anda ingin menghubungkan Ollama/LM Studio lokal, mengganti Base URL kustom, atau memilih ID model secara manual.
6. Untuk kembali ke mode lokal `.gguf` (pada Studio Desktop/Termux), klik **`↩️ Kembali ke Mode Lokal`**.

<details>
<summary>Opsional: Cara Mengatur API Online via Environment Variables atau REST API (curl)</summary>

**Via Environment Variables sebelum menyalakan Studio:**
```bash
export NOVEL_AI_PROVIDER="openai_compatible" # atau "anthropic" / "local_llama"
export NOVEL_AI_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai"
export NOVEL_AI_MODEL="gemini-3.8-flash" # opsional; jika dikosongkan memilih model aktif terbaru otomatis
export NOVEL_AI_API_KEY="API_KEY_ANDA"
./start_studio.sh
```

**Via REST API (`curl` — sumber & model terbaru dideteksi otomatis hanya dari API Key):**
```bash
# Cukup kirim api_key dengan provider_type "auto" — backend auto-detect sumber & model aktif!
curl -X POST http://127.0.0.1:8000/api/ai/provider \
  -H "Content-Type: application/json" \
  -d '{
    "provider_type": "auto",
    "api_key": "API_KEY_ANDA",
    "stop_local_llama": true
  }'

# Kembali ke Mode Lokal llama-server
curl -X POST http://127.0.0.1:8000/api/ai/provider \
  -H "Content-Type: application/json" \
  -d '{"provider_type": "local_llama", "preset_id": "local_llama"}'
```

</details>

---

### 5B. Cara Memilih, Mengunduh, & Mengganti Model Lokal (`.GGUF`)

> **Catatan CPU 2-Core vs RAM 8–16 GB:**
> - Di **CPU 2-Core** (mis. Intel Celeron), model **1.7B–3B** jauh lebih nyaman (`Qwen3-1.7B` ±2x lebih cepat daripada `3B`). Model **7B–12B** lebih cocok di **CPU 4–8 Core**, **Apple Silicon**, atau **GPU Vulkan/CUDA**.
> - Studio otomatis menyetel *KV Cache* **`f16`** untuk model $\le 2.6\text{ GB}$ (mencegah bahasa Indonesia menjadi rusak/acak pada seri Qwen) dan **`q8_0`** untuk model `7B+`, serta menambahkan `--reasoning off` pada model Qwen3.

#### Katalog 11 Model Rekomendasi (Bebas Login HuggingFace)

| Kelompok | Nama File `.gguf` | Ukuran | Min. RAM / CPU | Kelebihan (+) | Kekurangan (-) |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **Tier 1 (Ringan CPU 2-Core)** | **`Qwen2.5-3B-Instruct-Q4_K_M.gguf`** *(Default)* | 1.80 GB | 4 GB+ / 2 Core | Titik seimbang terbaik CPU 2-Core, Bahasa Indonesia rapi, patuh JSON. | Metafora sastra kalah dalam dibanding 7B/12B. |
| **Tier 1 (Ringan Presisi)** | **`Qwen2.5-3B-Instruct-Q5_K_M.gguf`** | 2.07 GB | 6 GB+ / 2 Core | Diksi & struktur kalimat lebih presisi daripada Q4_K_M. | ~15% lebih lambat di CPU Celeron. |
| **Tier 1 (Super Kilat / HP)** | **`Qwen3-1.7B-Q4_K_M.gguf`** | 1.03 GB | 4 GB+ / 2 Core | Sangat enteng & cepat di CPU lambat / HP Android Termux. | Kosa kata sastra & lore panjang terbatas. |
| **Tier 1 (Prosa Mengalir)** | **`gemma-2-2b-it-Q4_K_M.gguf`** | 1.59 GB | 4 GB+ / 2 Core | Gaya kalimat luwes & hangat khas Gemma. | Idiom Indonesia & JSON ketat kalah dari Qwen 2.5 3B. |
| **Tier 1 (Khusus B. Inggris)** | **`Llama-3.2-3B-Instruct-Q4_K_M.gguf`** | 1.88 GB | 6 GB+ / 2 Core | Dialog Bahasa Inggris ringkas dan hidup. | Bahasa Indonesia sering terasa kaku seperti terjemahan. |
| **Tier 2 (Upgrade 8–12 GB)** | **`Qwen_Qwen3-4B-Q4_K_M.gguf`** | 2.33 GB | 8 GB+ / 2–4 Core | Lompatan besar nalar subteks karakter & Bahasa Indonesia. | ~25–35% lebih lambat di Celeron 2-Core vs 3B. |
| **Tier 3 (Sastra 7B–8B)** | **`EVA-Qwen2.5-7B-v0.1-IQ4_XS.gguf`** | 3.93 GB | 8 GB+ / 4+ Core atau GPU | *Fine-tune* khusus cerita kreatif; *Show, Don't Tell* sangat kaya. | Lambat jika dijalankan hanya pada CPU 2-Core. |
| **Tier 3 (Disiplin Plot)** | **`Qwen2.5-7B-Instruct-IQ4_XS.gguf`** | 3.93 GB | 8 GB+ / 4+ Core atau GPU | Sangat disiplin mematuhi *Phase Guardrails* & dunia kompleks. | Nada sedikit lebih formal dibanding EVA-Qwen2.5-7B. |
| **Tier 3 (Aksi / Thriller)** | **`L3-8B-Stheno-v3.2-IQ4_XS.gguf`** | 4.14 GB | 8 GB+ / 4+ Core atau GPU | Dialog tajam, intensitas konflik gelap & aksi kuat. | Bersinar di Bahasa Inggris; kurang optimal untuk Indonesia murni. |
| **Tier 3 (Nalar Tajam 8B)** | **`Qwen_Qwen3-8B-IQ4_XS.gguf`** | 4.25 GB | 10 GB+ / 4+ Core atau GPU | Nalar sebab-akibat antarkarakter paling tajam di kelas 8B. | Berat di RAM ~5.3 GB saat aktif. |
| **Tier 4 (Workstation 12B)** | **`MN-12B-Celeste-V1.9-IQ4_XS.gguf`** | 6.28 GB | 12–16 GB+ / GPU | Prosa sastra puitis tingkat lanjut, nyaris tanpa klise AI. | Memakai ~7.6 GB RAM; tidak cocok untuk laptop RAM 8 GB. |

#### 3 Cara Menambah & Mengganti Model Lokal
1. **Lewat Web UI (Paling Mudah):**
   Klik badge status AI di pojok kanan atas $\rightarrow$ pilih tab **`📚 Katalog GGUF`** untuk mengunduh model rekomendasi (atau **`➕ Unduh GGUF Kustom`** dengan menempel URL `.gguf` / Repo ID HuggingFace dari `bartowski/*`, `unsloth/*`, atau `mradermacher/*`). Setelah selesai, buka tab **`💾 Model Lokal`** $\rightarrow$ klik **`🔄 Switch & Muat`**.
2. **Impor dari Folder `Downloads`:**
   Bila mengunduh `.gguf` lewat browser/IDM ke folder `Downloads`, buka tab **`💾 Model Lokal`** $\rightarrow$ klik **`🔄 Refresh Status`** $\rightarrow$ klik **`📥 Pindahkan ke Studio (models/)`** $\rightarrow$ **`🔄 Switch & Muat`**.
3. **Lewat Terminal (`curl` dengan resume `-C -`):**
   ```bash
   # Contoh: mengunduh Qwen 3 4B (2.33 GB)
   curl -L -C - "https://huggingface.co/bartowski/Qwen_Qwen3-4B-GGUF/resolve/main/Qwen_Qwen3-4B-Q4_K_M.gguf" \
     -o models/Qwen_Qwen3-4B-Q4_K_M.gguf.part && \
     mv models/Qwen_Qwen3-4B-Q4_K_M.gguf.part models/Qwen_Qwen3-4B-Q4_K_M.gguf
   ```

---

## 6. Tutorial 3 — Panduan Menulis Novel dari Awal sampai Ekspor

Studio menyertakan 1 proyek contoh (**"Senja di Pelabuhan Sunda"**) agar Anda langsung bisa mencoba alur penulisannya:

1. **Langkah 1 — Buat Novel & Isi Core Compass (Panel Kiri $\rightarrow$ Tab `Compass`):**
   - Klik **`+ Novel`** di pojok kiri atas (atau ubah proyek aktif).
   - Lengkapi **Judul**, **Nama Penulis / Pena**, **Premis**, **North Star**, **POV**, **Contoh Gaya Bahasa (*Style Sample*)**, dan **Banned Phrases**.
   - Gunakan **`📦 Backup`** kapan saja untuk mengunduh cadangan penuh proyek (`.json`), dan **`📥 Restore`** untuk memulihkan berkas `.json` tersebut menjadi proyek baru yang utuh.
2. **Langkah 2 — Atur Phase-Range Timeline (Pita Atas):**
   - Klik kartu fase (*Bab 1–3 Opening*, dst.) untuk menyesuaikan target ketegangan (**Tension Min–Max %**) dan **Strict Phase Guardrails** agar AI menjaga batas konflik bab.
3. **Langkah 3 — Isi Codex / Lorebook (Panel Kiri $\rightarrow$ Tab `Codex`):**
   - Tambahkan **CHARACTER**, **LOCATION**, **WORLD_RULE**, **ITEM**, atau **LORE**. Centang **📌 Pin** untuk elemen mutlak utama; sisanya tetap otomatis terbaca oleh pencarian **FTS5 BM25 (`<1 ms`)**.
4. **Langkah 4 — Atur Target Kata & Narrative Mix (Panel Kanan):**
   - Di tab **`Bab`**, pantau progres **Total Naskah** seluruh novel serta **Target Kata Harian** (klik angka target harian untuk menyesuaikannya).
   - Pilih bab di sebelah kiri, atur **Target Kata Bab**, **Mode Pacing** (`SLOW_BURN` / `BALANCED` / `FAST_PACED` / `FRENETIC_ACTION`), dan **5 Slider Narrative Mix** di panel kanan, lalu klik **`💾 Simpan Pengaturan Bab`**.
5. **Langkah 5 — Rancang Micro-Beats (`⚡ Generate Beat Plan`):**
   - Klik **`⚡ Generate Beat Plan`** untuk memecah tujuan bab menjadi kartu adegan terurut. Anda bebas menyunting instruksi, menggeser urutan beat (`▲` / `▼`), menambah/menghapus beat, dan memilih status penyuntingan (**`Rencana`** / **`Draf Selesai`** / **`Final / Sunting`**).
6. **Langkah 6 — Menulis, Menyunting, & Extract State:**
   - Klik **`▶️ Write Beat`** untuk mengalirkan prosa secara *real-time* (bila beat sudah berisi teks, sistem otomatis membuat **Auto-Snapshot** di `🕒 Riwayat Versi` sebelum menimpanya).
   - **Auto-Save:** Suntingan manual otomatis tersimpan setelah 1,5 detik (`✓ Tersimpan`), dan studio mengingat novel serta bab terakhir yang dibuka saat halaman di-refresh.
   - **Cari & Ganti (`🔎 Cari & Ganti` / `Alt+F`):** Ganti nama tokoh atau istilah serentak di seluruh beat dalam bab aktif (dilengkapi snapshot riwayat otomatis sebelum mengganti).
   - Klik **`🧠 Extract State & Update Codex`** seusai menulis beat agar ringkasan dan kondisi karakter terus terbarui ke memori jangka panjang.
7. **Langkah 7 — Kompilasi & Ekspor Naskah (`📤 Ekspor`):**
   - Klik **`📤 Ekspor`** di pojok kanan atas (tersedia di Desktop & HP) untuk memilih format:
     - **`📘 Ebook (.EPUB)`** standar penerbit (lengkap metadata, judul, sinopsis, tipografi buku, pemisah `* * *`, dan Daftar Isi otomatis),
     - **`🖨️ Cetak / Save PDF`** (tata letak buku A5 siap cetak atau simpan PDF via `Ctrl+P`),
     - **`📄 Novel Penuh (.MD)`** (lengkap dengan lampiran Story Bible & Codex), atau **`📝 Bab Aktif (.MD)`**.

### Pintasan Keyboard Cepat
| Pintasan | Fungsi |
| :--- | :--- |
| **`Alt + Z`** | Masuk / keluar **Zen Mode** (menyembunyikan panel samping agar fokus menulis) |
| **`Alt + R`** | Beralih antara **Mode Kartu Beat** dan **📖 Mode Baca Utuh** (`A- / A / A+` & navigasi bab) |
| **`Alt + F`** | Membuka / menutup **🔎 Cari & Ganti** di seluruh beat pada bab aktif |

---

## 7. Tutorial Lanjutan — Akses Internet Aman via Cloudflare Tunnel (Opsional)

Gunakan langkah ini hanya jika Anda ingin mengakses Studio dari HP/laptop di luar rumah **tanpa membuka port router**:

1. **Generate konfigurasi keamanan (sekali saja):**
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
2. **Aktifkan penguncian & jalankan `cloudflared`:**
   - **Linux:** Jalankan `sudo bash deploy/setup_ufw_cloudflare.sh`. Saat `NOVEL_SECURITY_MODE=STRICT_CLOUDFLARE` aktif di `backend/.env.security`, `start_studio.sh` otomatis mengikat FastAPI pada `127.0.0.1:8000` dan menolak request tanpa header validasi Cloudflare (`403 Forbidden`).
   - **Windows / macOS:** Pasang `cloudflared` (`winget install Cloudflare.cloudflared` / `brew install cloudflared`), jalankan `uvicorn` dengan `--host 127.0.0.1`, lalu ikuti panduan langkah tunnel di `deploy/PANDUAN_CLOUDFLARE_TUNNEL.md`.

---

## 8. Lampiran — Optimasi ZRAM (Linux) & Troubleshooting Cepat

### Aktifkan ZRAM di Linux Mint / Ubuntu / Debian *(Disarankan untuk RAM 8 GB Mode Lokal)*
```bash
sudo apt update && sudo apt install -y zram-tools
printf "ALGO=zstd\nPERCENT=50\nPRIORITY=100\n" | sudo tee /etc/default/zramswap
printf "vm.swappiness=100\nvm.vfs_cache_pressure=50\n" | sudo tee /etc/sysctl.d/99-mint-ai.conf
sudo systemctl restart zramswap && sudo sysctl --system
```
*(Di Fedora ZRAM umumnya aktif otomatis lewat `systemd-zram-generator`; di Arch Linux pasang `zram-generator`.)*

### Panduan Mengatasi Masalah Umum

- **Proses Write Beat terasa sangat lambat atau menunggu lama di CPU 2-Core:**
  Di CPU hemat daya tanpa GPU (seperti Intel Celeron), pembacaan konteks awal membutuhkan ~40–90 detik pada Beat pertama sebelum kata pertama mengalir (penghitung detik tampil langsung di atas kotak editor). Untuk pengalaman yang jauh lebih cepat, pilih salah satu:
  1. Beralih ke **API Online** (*Gemini / OpenRouter / Groq*) di tab **`🌐 API Online & Sumber Lain`**, **atau**
  2. Unduh model super-ringan **`Qwen3-1.7B-Q4_K_M.gguf` (`1.03 GB`)** di tab **`📚 Katalog GGUF`**.
- **Error saat memakai API AI Online (`401` / `404` / `429`):**
  - `401 / 403`: API Key keliru, kadaluarsa, atau belum aktif untuk layanan terkait.
  - `404 / model_not_found`: pastikan ID model sesuai dengan daftar milik provider (klik **`🔍 Ambil Daftar Model`** di tab **`🌐 API Online`**).
  - `429 Too Many Requests`: batas kuota per menit tier gratis tercapai — tunggu sebentar atau pilih model lain.
  - Menyambung ke **Ollama di PC lain dalam satu Wi-Fi**: jalankan `OLLAMA_HOST=0.0.0.0 ollama serve` pada PC GPU tersebut, lalu isi `Base URL` di Studio dengan `http://<IP-PC-GPU>:11434/v1`.
- **Teks Bahasa Indonesia di mode lokal tampak aneh / rusak:**
  Pastikan *KV Cache* tidak memakai `q4_0` pada model kecil (Studio sudah otomatis memakai `f16` untuk $\le 2.6\text{ GB}$ dan `q8_0` untuk `7B+`), serta setel `XTC Probability` = `0.0` dan `Temperature` = `0.70–0.85` di panel kanan.
- **Error `401` saat mengunduh model `.gguf` kustom dari HuggingFace:**
  Repositori model tersebut bersifat *gated* (memerlukan persetujuan lisensi). Gunakan rilisan publik komunitas seperti `bartowski/*-GGUF` atau `unsloth/*-GGUF`.
- **Masalah khusus Windows (`llama.dll` tidak ditemukan / Firewall / PowerShell):**
  Pastikan semua file `.dll` hasil ekstrak `.zip` berada tepat di dalam folder `bin\` bersama `llama-server.exe` (untuk CUDA wajib ekstrak juga `cudart-llama-bin-win-cuda-12.4-x64.zip`). Ubah profil jaringan Wi-Fi ke **Private** dan buka port `8000` dengan `New-NetFirewallRule`.
- **Masalah khusus macOS (`cannot be opened` / `dyld library`):**
  Jalankan `xattr -dr com.apple.quarantine bin/` dan pastikan semua file `.dylib` / `.metallib` berada di folder `bin/`.
- **Masalah khusus Android Termux (`lxml`/`pydantic` gagal compile atau server berhenti):**
  Wajib instal `python-lxml` dan `python-pydantic` lewat `pkg` lalu buat venv dengan `--system-site-packages`, serta aktifkan `termux-wake-lock`.
- **Membaca Log Runtime:**
  Log mesin AI lokal tersedia di `.logs/llama-server.log` dan log server web di `.logs/fastapi.log`.
