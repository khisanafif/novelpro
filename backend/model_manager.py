"""
MODEL MANAGER, KATALOG KURASI, CUSTOM GGUF ADDER & RUNTIME SWITCHER API
Linux Mint (RAM 8-12+ GB Edition)

Fitur:
1. Katalog Model Kurasi Lengkap (Tier Ultra-Ringan s.d. Workstation) dengan
   spesifikasi RAM/CPU, kecepatan estimasi, kelebihan, & kekurangan.
2. Tambah Model Kustom (Custom GGUF Adder):
   - Unduh langsung dari URL/Repo HuggingFace publik (dengan validasi SSRF & HTTP HEAD check).
   - Deteksi & impor otomatis file `.gguf` dari folder `~/Downloads/` Linux Mint ke `models/`.
3. API Switching Model Atomik di bawah Single-Worker Inference Queue:
   - Mematikan proses `llama-server` lama agar RAM bersih sebelum memuat model baru.
   - Auto-tuning `--cache-type-k/v` (`f16` untuk <=2.6GB / `q8_0` untuk 7B+) & `--reasoning off` untuk Qwen3.
"""

import asyncio
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse
import urllib.request

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

from database import update_project


STUDIO_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = Path(os.environ.get("NOVEL_MODELS_DIR", str(STUDIO_ROOT / "models"))).resolve()
BIN_DIR = Path(os.environ.get("NOVEL_BIN_DIR", str(STUDIO_ROOT / "bin"))).resolve()
RUN_DIR = (STUDIO_ROOT / ".run").resolve()
LOG_DIR = (STUDIO_ROOT / ".logs").resolve()
USER_DOWNLOADS_DIR = (Path.home() / "Downloads").resolve()
CUSTOM_MODELS_META_FILE = (MODELS_DIR / "custom_models.json").resolve()

EXTRA_MODEL_DIRS = [
    MODELS_DIR,
    Path("/opt/novel-studio/models"),
]

ALLOWED_CUSTOM_DOWNLOAD_HOSTS = {
    "huggingface.co",
    "hf.co",
    "cdn-lfs.huggingface.co",
    "cdn-lfs-us-1.huggingface.co",
    "cdn-lfs-eu-1.huggingface.co",
    "github.com",
    "objects.githubusercontent.com",
}

SAFE_GGUF_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,180}\.gguf$")


# ============================================================================
# KATALOG MODEL GGUF KURASI NOVEL (VERIFIED OPEN HUGGINGFACE URLS + SPEK)
# ============================================================================

CURATED_GGUF_CATALOG: List[Dict[str, Any]] = [
    {
        "catalog_id": "qwen2.5-3b-instruct-q4",
        "profile_name": "Qwen2.5-3B-Instruct-Q4_K_M",
        "display_name": "Qwen 2.5 3B Instruct (Q4_K_M)",
        "tier": "Tier 1 • Cepat & Seimbang (Rekomendasi Utama Laptop Ini)",
        "filename": "Qwen2.5-3B-Instruct-Q4_K_M.gguf",
        "size_mb": 1840.5,
        "ram_estimate_gb": 2.4,
        "min_ram_gb": 4,
        "min_cpu_cores": 2,
        "recommended_for": "Rekomendasi Utama CPU Celeron 2-Core: cepat, Bahasa Indonesia rapi, & Plot JSON patuh",
        "pros": "Bahasa Indonesia baku sangat alami, patuh JSON Plot Architect/Extractor, hemat RAM.",
        "cons": "Metafora sastra tidak sedalam model creative-writing 7B/12B; sensitif jika KV cache ditekan ke q4_0 (otomatis f16 di Studio).",
        "download_url": "https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q4_K_M.gguf",
        "is_recommended_cpu": True,
    },
    {
        "catalog_id": "qwen2.5-3b-instruct-q5",
        "profile_name": "Qwen2.5-3B-Instruct-Q5_K_M",
        "display_name": "Qwen 2.5 3B Instruct (Q5_K_M)",
        "tier": "Tier 1 • Cepat & Presisi",
        "filename": "Qwen2.5-3B-Instruct-Q5_K_M.gguf",
        "size_mb": 2121.7,
        "ram_estimate_gb": 2.8,
        "min_ram_gb": 6,
        "min_cpu_cores": 2,
        "recommended_for": "Varian 3B presisi lebih tinggi dengan diksi lebih tajam & konsisten",
        "pros": "Diksi Bahasa Indonesia lebih akurat dari Q4_K_M dengan kenaikan RAM sangat tipis.",
        "cons": "~15% lebih lambat di CPU 2-Core dibanding Q4_K_M.",
        "download_url": "https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q5_K_M.gguf",
        "is_recommended_cpu": True,
    },
    {
        "catalog_id": "qwen3-1.7b-q4",
        "profile_name": "Qwen3-1.7B-Q4_K_M",
        "display_name": "Qwen 3 1.7B (Q4_K_M — Super Kilat)",
        "tier": "Tier 1 • Ultra-Ringan (Drafting & Outline Kilat)",
        "filename": "Qwen3-1.7B-Q4_K_M.gguf",
        "size_mb": 1056.1,
        "ram_estimate_gb": 1.6,
        "min_ram_gb": 4,
        "min_cpu_cores": 2,
        "recommended_for": "Kecepatan maksimal di CPU 2-Core atau saat multitasking banyak aplikasi di Linux Mint",
        "pros": "Ukuran hanya ~1 GB, generasi ~2x lebih cepat dari 3B, sangat cocok untuk menyusun kerangka beat cepat.",
        "cons": "Kedalaman emosi dan ingatan konteks kompleks kalah dibanding 3B/4B/7B.",
        "download_url": "https://huggingface.co/unsloth/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q4_K_M.gguf",
        "is_recommended_cpu": True,
    },
    {
        "catalog_id": "gemma-2-2b-it-q4",
        "profile_name": "gemma-2-2b-it-Q4_K_M",
        "display_name": "Google Gemma-2 2B Instruct (Q4_K_M)",
        "tier": "Tier 1 • Ultra-Ringan (Prosa Mengalir)",
        "filename": "gemma-2-2b-it-Q4_K_M.gguf",
        "size_mb": 1629.4,
        "ram_estimate_gb": 2.3,
        "min_ram_gb": 4,
        "min_cpu_cores": 2,
        "recommended_for": "Alternatif ringan bergaya kalimat luwes & puitis khas arsitektur Google Gemma-2",
        "pros": "Ritme kalimat terasa hangat & mengalir, cepat di CPU 2-Core.",
        "cons": "Tata bahasa Indonesia & kepatuhan JSON ketat sedikit di bawah Qwen 2.5 3B.",
        "download_url": "https://huggingface.co/bartowski/gemma-2-2b-it-GGUF/resolve/main/gemma-2-2b-it-Q4_K_M.gguf",
        "is_recommended_cpu": True,
    },
    {
        "catalog_id": "llama-3.2-3b-q4",
        "profile_name": "Llama-3.2-3B-Instruct-Q4_K_M",
        "display_name": "Meta Llama-3.2 3B Instruct (Q4_K_M)",
        "tier": "Tier 1 • Cepat (Spesialis Novel Inggris / Aksi)",
        "filename": "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "size_mb": 1925.8,
        "ram_estimate_gb": 2.5,
        "min_ram_gb": 6,
        "min_cpu_cores": 2,
        "recommended_for": "Penulisan novel berbahasa Inggris dengan tempo dialog & aksi cepat",
        "pros": "Dialog bahasa Inggris ringkas, natural, dan responsif.",
        "cons": "Untuk prosa Bahasa Indonesia, diksi masih kerap bernuansa terjemahan.",
        "download_url": "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "is_recommended_cpu": True,
    },
    {
        "catalog_id": "qwen3-4b-q4",
        "profile_name": "Qwen_Qwen3-4B-Q4_K_M",
        "display_name": "Qwen 3 4B (Q4_K_M — Upgrade Terbaik RAM 8–12 GB)",
        "tier": "Tier 2 • Menengah Modern (Sweet Spot Kualitas vs Kecepatan)",
        "filename": "Qwen_Qwen3-4B-Q4_K_M.gguf",
        "size_mb": 2381.6,
        "ram_estimate_gb": 3.1,
        "min_ram_gb": 8,
        "min_cpu_cores": 2,
        "recommended_for": "Upgrade kualitas narasi & nalar plot dibanding 3B dengan RAM tetap di bawah 3.2 GB",
        "pros": "Pemahaman subteks karakter dan Bahasa Indonesia sangat cerdas untuk ukuran 4B (~2.3 GB). Mode think otomatis dinonaktifkan agar langsung menulis.",
        "cons": "~25-35% lebih lambat di Celeron 2-Core dibanding Qwen2.5-3B.",
        "download_url": "https://huggingface.co/bartowski/Qwen_Qwen3-4B-GGUF/resolve/main/Qwen_Qwen3-4B-Q4_K_M.gguf",
        "is_recommended_cpu": True,
    },
    {
        "catalog_id": "eva-qwen2.5-7b-iq4",
        "profile_name": "EVA-Qwen2.5-7B-IQ4_XS",
        "display_name": "EVA-Qwen 2.5 7B v0.1 (IQ4_XS — Raja Prosa Fiksi)",
        "tier": "Tier 3 • Sastra Profesional (7B–8B)",
        "filename": "EVA-Qwen2.5-7B-v0.1-IQ4_XS.gguf",
        "size_mb": 4023.0,
        "ram_estimate_gb": 4.9,
        "min_ram_gb": 8,
        "min_cpu_cores": 4,
        "recommended_for": "Fine-tune penulisan novel & narasi sastra mendalam (Show Don't Tell paling kaya)",
        "pros": "Kaya detail sensorik, emosi halus, minim gaya bahasa asisten AI, kuat untuk Bahasa Indonesia & Inggris.",
        "cons": "Sangat lambat di CPU Celeron 2-Core (~5-8 menit/beat); optimal di CPU 4-8 Core atau GPU.",
        "download_url": "https://huggingface.co/bartowski/EVA-Qwen2.5-7B-v0.1-GGUF/resolve/main/EVA-Qwen2.5-7B-v0.1-IQ4_XS.gguf",
        "is_recommended_cpu": False,
    },
    {
        "catalog_id": "qwen2.5-7b-instruct-iq4",
        "profile_name": "Qwen2.5-7B-Instruct-IQ4_XS",
        "display_name": "Qwen 2.5 7B Instruct (IQ4_XS — Struktur & Lore Ketat)",
        "tier": "Tier 3 • Sastra & Plot Kompleks (7B–8B)",
        "filename": "Qwen2.5-7B-Instruct-IQ4_XS.gguf",
        "size_mb": 4023.0,
        "ram_estimate_gb": 4.9,
        "min_ram_gb": 8,
        "min_cpu_cores": 4,
        "recommended_for": "Menjaga aturan dunia kompleks, misteri deduktif, dan kepatuhan ketat pada Phase Guardrails",
        "pros": "Konsistensi logika paling disiplin untuk plot berlapis dan Bahasa Indonesia baku.",
        "cons": "Prosa kadang sedikit lebih rapi/formal daripada EVA-Qwen2.5-7B; butuh CPU 4+ Core agar gegas.",
        "download_url": "https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct-IQ4_XS.gguf",
        "is_recommended_cpu": False,
    },
    {
        "catalog_id": "stheno-v3.2-8b-iq4",
        "profile_name": "Stheno-v3.2-8B-IQ4_XS",
        "display_name": "Llama-3 Stheno v3.2 8B (IQ4_XS — Dialog & Thriller)",
        "tier": "Tier 3 • Dialog & Konflik Intens (8B)",
        "filename": "L3-8B-Stheno-v3.2-IQ4_XS.gguf",
        "size_mb": 4241.6,
        "ram_estimate_gb": 5.2,
        "min_ram_gb": 8,
        "min_cpu_cores": 4,
        "recommended_for": "Adegan penuh dialog berkarakter, konflik intens, thriller, & subteks psikologis",
        "pros": "Dialog antar tokoh hidup dan berani mengeksplorasi ketegangan gelap tanpa sensor berlebih.",
        "cons": "Lebih unggul di Bahasa Inggris; di Bahasa Indonesia kadang terasa berstruktur terjemahan; lambat di 2-Core.",
        "download_url": "https://huggingface.co/bartowski/L3-8B-Stheno-v3.2-GGUF/resolve/main/L3-8B-Stheno-v3.2-IQ4_XS.gguf",
        "is_recommended_cpu": False,
    },
    {
        "catalog_id": "qwen3-8b-iq4",
        "profile_name": "Qwen_Qwen3-8B-IQ4_XS",
        "display_name": "Qwen 3 8B (IQ4_XS — Generasi Terbaru)",
        "tier": "Tier 3 • Generasi Terbaru (8B)",
        "filename": "Qwen_Qwen3-8B-IQ4_XS.gguf",
        "size_mb": 4350.5,
        "ram_estimate_gb": 5.3,
        "min_ram_gb": 10,
        "min_cpu_cores": 4,
        "recommended_for": "Kualitas penalaran adegan, kesinambungan fakta Codex, & Bahasa Indonesia tingkat tinggi",
        "pros": "Penalaran sebab-akibat antarkarakter paling tajam di kelas 8B.",
        "cons": "Berat untuk CPU Celeron 2-Core; idealnya dijalankan di CPU 4-8 Core atau GPU.",
        "download_url": "https://huggingface.co/bartowski/Qwen_Qwen3-8B-GGUF/resolve/main/Qwen_Qwen3-8B-IQ4_XS.gguf",
        "is_recommended_cpu": False,
    },
    {
        "catalog_id": "mn-12b-celeste-iq4",
        "profile_name": "MN-12B-Celeste-V1.9-IQ4_XS",
        "display_name": "Mistral Nemo Celeste 12B v1.9 (IQ4_XS)",
        "tier": "Tier 4 • Workstation Sastra (Khusus RAM >= 12–16 GB / GPU)",
        "filename": "MN-12B-Celeste-V1.9-IQ4_XS.gguf",
        "size_mb": 6430.3,
        "ram_estimate_gb": 7.6,
        "min_ram_gb": 12,
        "min_cpu_cores": 6,
        "recommended_for": "Kualitas penulisan novel kelas atas jika memakai PC/laptop RAM 12–16+ GB atau GPU NVIDIA/AMD",
        "pros": "Kosakata kaya, atmosfer puitis mendalam, nyaris bebas klise AI.",
        "cons": "Memakan ~7.6 GB RAM (mepet di 11.8 GB jika membuka banyak app) & sangat lambat tanpa GPU atau CPU kencang.",
        "download_url": "https://huggingface.co/bartowski/MN-12B-Celeste-V1.9-GGUF/resolve/main/MN-12B-Celeste-V1.9-IQ4_XS.gguf",
        "is_recommended_cpu": False,
    },
]

_CATALOG_BY_ID = {c["catalog_id"]: c for c in CURATED_GGUF_CATALOG}
_CATALOG_BY_FILENAME = {c["filename"].lower(): c for c in CURATED_GGUF_CATALOG}


# ============================================================================
# HELPER VALIDASI URL CUSTOM & REGISTRASI METADATA MODEL KUSTOM
# ============================================================================

def normalize_and_validate_custom_gguf_url(
    raw_url_or_repo: str,
    explicit_filename: str = "",
) -> Tuple[str, str]:
    """
    Menerima URL `.gguf` langsung ATAU pasangan HuggingFace `repo_id` + `filename`,
    mengubah `/blob/main/` menjadi `/resolve/main/`, memvalidasi skema `https://`
    serta allowlist host untuk mencegah SSRF.
    """
    raw = (raw_url_or_repo or "").strip()
    fname_arg = (explicit_filename or "").strip()

    if not raw:
        raise ValueError("Masukkan URL HuggingFace (.gguf) atau Repo ID (misal: bartowski/Qwen2.5-3B-Instruct-GGUF).")

    if raw.startswith("http://"):
        raise ValueError("Hanya URL HTTPS terenkripsi yang diizinkan untuk mengunduh model.")

    # Jika user mengisi format repo HuggingFace `owner/repo` tanpa https://
    if not raw.startswith("https://"):
        repo_clean = raw.strip("/")
        if not re.match(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$", repo_clean):
            raise ValueError(
                "Format Repo HuggingFace tidak valid. Gunakan 'owner/repo' (contoh: bartowski/Qwen2.5-3B-Instruct-GGUF) atau URL https:// lengkap."
            )
        if not fname_arg:
            raise ValueError("Jika memasukkan Repo ID HuggingFace, isi juga Nama File `.gguf` yang ingin diunduh.")
        url = f"https://huggingface.co/{repo_clean}/resolve/main/{fname_arg}"
    else:
        url = raw
        if "huggingface.co/" in url and "/blob/" in url:
            url = url.replace("/blob/", "/resolve/", 1)

    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in ALLOWED_CUSTOM_DOWNLOAD_HOSTS:
        raise ValueError(
            f"Domain '{host or '-'}' tidak masuk daftar sumber terpercaya ({', '.join(sorted(ALLOWED_CUSTOM_DOWNLOAD_HOSTS))})."
        )

    url_filename = os.path.basename(urllib.parse.unquote(parsed.path))
    final_filename = os.path.basename(fname_arg) if fname_arg else url_filename
    if not SAFE_GGUF_FILENAME_RE.match(final_filename):
        raise ValueError(
            f"Nama file '{final_filename}' tidak valid. Nama file wajib berakhiran `.gguf` dan hanya boleh berisi huruf, angka, titik, `_`, atau `-`."
        )

    return url, final_filename


def load_custom_models_metadata() -> Dict[str, Dict[str, Any]]:
    if not CUSTOM_MODELS_META_FILE.is_file():
        return {}
    try:
        data = json.loads(CUSTOM_MODELS_META_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_custom_model_metadata(
    filename: str,
    display_name: str = "",
    notes: str = "",
    download_url: str = "",
) -> Dict[str, Any]:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    meta_map = load_custom_models_metadata()
    entry = {
        "filename": filename,
        "profile_name": Path(filename).stem,
        "display_name": (display_name or "").strip() or Path(filename).stem,
        "recommended_for": (notes or "").strip() or "Model GGUF Kustom yang ditambahkan pengguna",
        "download_url": download_url,
        "added_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    meta_map[filename.lower()] = entry
    CUSTOM_MODELS_META_FILE.write_text(
        json.dumps(meta_map, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return entry


# ============================================================================
# DOWNLOAD MANAGER (STREAMING ATOMIK KE .part -> .gguf)
# ============================================================================

class ModelDownloadManager:
    """Mengelola unduhan file `.gguf` dari katalog resmi maupun URL kustom terverifikasi."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._cancel_flags: Dict[str, threading.Event] = {}

    def get_all_jobs(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {k: dict(v) for k, v in self._jobs.items()}

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def cancel_download(self, job_id: str) -> bool:
        with self._lock:
            ev = self._cancel_flags.get(job_id)
            if ev:
                ev.set()
                return True
            return False

    def _enqueue_download(
        self,
        job_id: str,
        filename: str,
        download_url: str,
        estimated_mb: float = 0.0,
    ) -> Dict[str, Any]:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        target_path = (MODELS_DIR / filename).resolve()
        if not target_path.is_relative_to(MODELS_DIR):
            raise ValueError("Path target tidak valid.")

        if target_path.exists() and target_path.stat().st_size > 10 * 1024 * 1024:
            return {
                "catalog_id": job_id,
                "filename": filename,
                "status": "ALREADY_EXISTS",
                "percent": 100.0,
                "path": str(target_path),
            }

        with self._lock:
            existing = self._jobs.get(job_id)
            if existing and existing.get("status") == "DOWNLOADING":
                return dict(existing)

            cancel_event = threading.Event()
            self._cancel_flags[job_id] = cancel_event
            job_state = {
                "catalog_id": job_id,
                "filename": filename,
                "download_url": download_url,
                "status": "DOWNLOADING",
                "downloaded_mb": 0.0,
                "total_mb": estimated_mb,
                "percent": 0.0,
                "speed_mbps": 0.0,
                "error": "",
                "started_at": time.time(),
            }
            self._jobs[job_id] = job_state

        worker = threading.Thread(
            target=self._download_worker,
            args=(job_id, download_url, target_path, cancel_event),
            daemon=True,
        )
        worker.start()
        return dict(job_state)

    def start_download(self, catalog_id: str) -> Dict[str, Any]:
        entry = _CATALOG_BY_ID.get(catalog_id)
        if not entry:
            raise ValueError(f"Model katalog '{catalog_id}' tidak dikenali.")
        return self._enqueue_download(
            job_id=catalog_id,
            filename=entry["filename"],
            download_url=entry["download_url"],
            estimated_mb=float(entry["size_mb"]),
        )

    def start_custom_download(
        self,
        url_or_repo: str,
        filename: str = "",
        display_name: str = "",
        notes: str = "",
    ) -> Dict[str, Any]:
        url, final_filename = normalize_and_validate_custom_gguf_url(url_or_repo, filename)

        # Verifikasi cepat (HTTP HEAD) sebelum menjalankan thread download
        estimated_mb = 0.0
        try:
            head_req = urllib.request.Request(
                url,
                method="HEAD",
                headers={"User-Agent": "ZenLiteraryStudio/1.0"},
            )
            with urllib.request.urlopen(head_req, timeout=12) as hr:
                clen = int(hr.headers.get("Content-Length") or 0)
                if clen > 0:
                    estimated_mb = round(clen / (1024 * 1024), 1)
        except urllib.error.HTTPError as he:
            if he.code == 401:
                raise ValueError("Model HuggingFace ini terkunci (401 Unauthorized / gated repo). Pilih repo GGUF publik terbuka seperti milik bartowski/unsloth.") from he
            if he.code == 404:
                raise ValueError(f"File model tidak ditemukan (404) pada URL: {url}") from he
            raise ValueError(f"Server sumber menolak permintaan HEAD (HTTP {he.code}).") from he
        except Exception as exc:
            raise ValueError(f"Gagal menjangkau URL model: {exc}") from exc

        save_custom_model_metadata(
            filename=final_filename,
            display_name=display_name or Path(final_filename).stem,
            notes=notes,
            download_url=url,
        )
        job_id = f"custom:{final_filename}"
        return self._enqueue_download(
            job_id=job_id,
            filename=final_filename,
            download_url=url,
            estimated_mb=estimated_mb,
        )

    def _download_worker(
        self,
        job_id: str,
        url: str,
        target_path: Path,
        cancel_event: threading.Event,
    ) -> None:
        part_path = target_path.with_suffix(".gguf.part")
        downloaded = 0
        if part_path.exists():
            downloaded = part_path.stat().st_size

        try:
            headers = {"User-Agent": "ZenLiteraryStudio/1.0"}
            if downloaded > 0:
                headers["Range"] = f"bytes={downloaded}-"

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                status_code = getattr(resp, "status", 200)
                if status_code == 200 and downloaded > 0:
                    downloaded = 0
                    mode = "wb"
                elif status_code == 206:
                    mode = "ab"
                else:
                    downloaded = 0
                    mode = "wb"

                content_len = int(resp.headers.get("Content-Length") or 0)
                total_bytes = downloaded + content_len if content_len > 0 else 0
                t0 = time.monotonic()
                session_bytes = 0

                with open(part_path, mode) as out_f:
                    while True:
                        if cancel_event.is_set():
                            with self._lock:
                                self._jobs[job_id]["status"] = "CANCELLED"
                            return
                        chunk = resp.read(1024 * 512)
                        if not chunk:
                            break
                        out_f.write(chunk)
                        chunk_len = len(chunk)
                        downloaded += chunk_len
                        session_bytes += chunk_len
                        elapsed = max(0.05, time.monotonic() - t0)
                        speed_mbps = (session_bytes / (1024 * 1024)) / elapsed
                        pct = (
                            round((downloaded / total_bytes) * 100.0, 2)
                            if total_bytes > 0
                            else 0.0
                        )
                        with self._lock:
                            self._jobs[job_id].update(
                                {
                                    "downloaded_mb": round(downloaded / (1024 * 1024), 2),
                                    "total_mb": round(total_bytes / (1024 * 1024), 2)
                                    if total_bytes > 0
                                    else self._jobs[job_id]["total_mb"],
                                    "percent": pct,
                                    "speed_mbps": round(speed_mbps, 2),
                                }
                            )

            os.replace(part_path, target_path)
            with self._lock:
                self._jobs[job_id].update(
                    {
                        "status": "COMPLETED",
                        "percent": 100.0,
                        "path": str(target_path),
                    }
                )
        except Exception as exc:
            with self._lock:
                self._jobs[job_id].update(
                    {
                        "status": "ERROR",
                        "error": str(exc),
                    }
                )


download_manager = ModelDownloadManager()


# ============================================================================
# LLAMA-SERVER PROCESS & RUNTIME MODEL SWITCHER
# ============================================================================

class ModelRuntimeManager:
    """
    Mengelola daftar file `.gguf` lokal, impor dari `~/Downloads`, deteksi binary `llama-server`,
    serta pergantian model di RAM secara atomik melalui Single-Slot Inference Lock.
    """

    _cached_help_by_bin: Dict[str, str] = {}

    @staticmethod
    def find_llama_server_bin() -> Optional[Path]:
        bin_names = ["llama-server.exe", "llama-server"] if os.name == "nt" else ["llama-server"]
        candidates: List[Path] = []
        env_bin = os.environ.get("LLAMA_SERVER_BIN", "").strip()
        if env_bin:
            candidates.append(Path(env_bin))
        for bname in bin_names:
            candidates.append(BIN_DIR / bname)
            candidates.append(Path("/opt/novel-studio/bin") / bname)
            which_bin = shutil.which(bname)
            if which_bin:
                candidates.append(Path(which_bin))

        for path in candidates:
            if path.is_file() and (os.name == "nt" or os.access(path, os.X_OK)):
                return path.resolve()
        return None

    @staticmethod
    def _build_subprocess_env(bin_path: Path) -> Dict[str, str]:
        env = os.environ.copy()
        bin_dir = str(bin_path.parent)
        if os.name == "nt":
            env["PATH"] = f"{bin_dir};{env.get('PATH', '')}".strip(";")
        elif os.uname().sysname.lower() == "darwin":
            env["DYLD_LIBRARY_PATH"] = f"{bin_dir}:{env.get('DYLD_LIBRARY_PATH', '')}".strip(":")
        else:
            env["LD_LIBRARY_PATH"] = f"{bin_dir}:{env.get('LD_LIBRARY_PATH', '')}".strip(":")
        return env

    @classmethod
    def _read_llama_help_text(cls, bin_path: Path) -> str:
        key = str(bin_path)
        if key in cls._cached_help_by_bin:
            return cls._cached_help_by_bin[key]
        env = cls._build_subprocess_env(bin_path)
        res = subprocess.run(
            [str(bin_path), "--help"],
            capture_output=True,
            text=True,
            timeout=8,
            env=env,
        )
        help_txt = f"{res.stdout}\n{res.stderr}"
        cls._cached_help_by_bin[key] = help_txt
        return help_txt

    @classmethod
    def detect_flash_attn_args(cls, bin_path: Path) -> List[str]:
        try:
            help_text = cls._read_llama_help_text(bin_path)
            if "--flash-attn [on|off|auto]" in help_text or "-fa, --flash-attn [" in help_text:
                return ["--flash-attn", "auto"]
            if "--flash-attn" in help_text:
                return ["--flash-attn"]
        except Exception:
            pass
        return []

    @classmethod
    def detect_load_mode_args(cls, bin_path: Path) -> List[str]:
        try:
            help_text = cls._read_llama_help_text(bin_path)
            if "--load-mode" in help_text:
                return ["--load-mode", "mmap"]
            if "  --mmap" in help_text or ", --mmap" in help_text:
                return ["--mmap"]
        except Exception:
            pass
        return []

    @classmethod
    def detect_qwen3_reasoning_off_args(cls, bin_path: Path, model_filename: str) -> List[str]:
        """Untuk model Qwen3 yang memiliki mode <think>, matikan reasoning agar prosa langsung keluar."""
        if "qwen3" not in (model_filename or "").lower():
            return []
        try:
            help_text = cls._read_llama_help_text(bin_path)
            if "--reasoning [on|off|auto]" in help_text:
                return ["--reasoning", "off"]
            if "--reasoning-budget" in help_text:
                return ["--reasoning-budget", "0"]
        except Exception:
            pass
        return []

    @staticmethod
    def get_pid_file() -> Path:
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        return RUN_DIR / "llama-server.pid"

    @staticmethod
    def get_active_model_file() -> Path:
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        return RUN_DIR / "llama-active-model.txt"

    @classmethod
    def get_running_llama_pid(cls) -> Optional[int]:
        pid_file = cls.get_pid_file()
        if not pid_file.is_file():
            return None
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
            if os.name == "nt":
                res = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return pid if str(pid) in res.stdout else None
            os.kill(pid, 0)
            return pid
        except (ValueError, ProcessLookupError, PermissionError, OSError):
            return None

    @classmethod
    def read_active_model_from_proc(cls) -> Optional[str]:
        pid = cls.get_running_llama_pid()
        if not pid:
            return None
        cmdline_path = Path(f"/proc/{pid}/cmdline")
        if cmdline_path.is_file():
            try:
                raw = cmdline_path.read_bytes().decode("utf-8", errors="replace")
                parts = [p for p in raw.split("\x00") if p]
                for idx, arg in enumerate(parts):
                    if arg in ("-m", "--model") and idx + 1 < len(parts):
                        return parts[idx + 1]
            except Exception:
                pass
        # Fallback lintas-OS (Windows & macOS tidak memiliki /proc/<pid>/cmdline)
        active_file = cls.get_active_model_file()
        if active_file.is_file():
            txt = active_file.read_text(encoding="utf-8", errors="replace").strip()
            if txt:
                return txt
        return None

    @classmethod
    def resolve_safe_model_path(cls, model_identifier: str) -> Path:
        ident = (model_identifier or "").strip()
        if not ident:
            raise ValueError("Nama file atau profil model tidak boleh kosong.")

        if ident in _CATALOG_BY_ID:
            ident = _CATALOG_BY_ID[ident]["filename"]
        else:
            for item in CURATED_GGUF_CATALOG:
                if item["profile_name"].lower() == ident.lower():
                    ident = item["filename"]
                    break

        candidate_name = os.path.basename(ident)
        allowed_roots = [d.resolve() for d in EXTRA_MODEL_DIRS]

        for root in allowed_roots:
            if not root.is_dir():
                continue
            direct = (root / candidate_name).resolve()
            if direct.is_relative_to(root) and direct.is_file() and direct.suffix.lower() == ".gguf":
                return direct

            for found in root.glob(f"*/{candidate_name}"):
                resolved = found.resolve()
                if resolved.is_relative_to(root) and resolved.is_file():
                    return resolved

        raise FileNotFoundError(
            f"File model '{candidate_name}' belum ditemukan di {MODELS_DIR}/. "
            "Letakkan file .gguf atau unduh melalui katalog/form model kustom."
        )

    @classmethod
    def scan_local_models(cls) -> List[Dict[str, Any]]:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        discovered: List[Dict[str, Any]] = []
        seen_paths: set = set()
        active_path = cls.read_active_model_from_proc()
        custom_meta = load_custom_models_metadata()

        for root in EXTRA_MODEL_DIRS:
            if not root.is_dir():
                continue
            for gguf_path in sorted(root.rglob("*.gguf")):
                if not gguf_path.is_file():
                    continue
                resolved = str(gguf_path.resolve())
                if resolved in seen_paths:
                    continue
                seen_paths.add(resolved)
                stat = gguf_path.stat()
                size_mb = round(stat.st_size / (1024 * 1024), 1)
                cat_meta = _CATALOG_BY_FILENAME.get(gguf_path.name.lower())
                cus_meta = custom_meta.get(gguf_path.name.lower())
                meta = cat_meta or cus_meta or {}
                discovered.append(
                    {
                        "filename": gguf_path.name,
                        "path": resolved,
                        "size_mb": size_mb,
                        "size_gb": round(size_mb / 1024.0, 2),
                        "profile_name": meta.get("profile_name") or gguf_path.stem,
                        "display_name": meta.get("display_name") or gguf_path.name,
                        "recommended_for": meta.get("recommended_for") or "Model GGUF Lokal Kustom",
                        "is_custom": not bool(cat_meta),
                        "is_active": bool(active_path and os.path.abspath(active_path) == resolved),
                    }
                )
        return discovered

    @classmethod
    def scan_downloads_gguf(cls) -> List[Dict[str, Any]]:
        """Memindai file `.gguf` yang mungkin sudah diunduh browser ke ~/Downloads/."""
        if not USER_DOWNLOADS_DIR.is_dir():
            return []
        local_names = {m["filename"].lower() for m in cls.scan_local_models()}
        found: List[Dict[str, Any]] = []
        for p in sorted(USER_DOWNLOADS_DIR.glob("*.gguf")):
            if not p.is_file() or p.name.startswith("."):
                continue
            stat = p.stat()
            if stat.st_size < 10 * 1024 * 1024:
                continue
            found.append(
                {
                    "filename": p.name,
                    "path": str(p.resolve()),
                    "size_mb": round(stat.st_size / (1024 * 1024), 1),
                    "size_gb": round(stat.st_size / (1024 * 1024 * 1024), 2),
                    "already_in_models": p.name.lower() in local_names,
                }
            )
        return found

    @classmethod
    def import_from_downloads(
        cls,
        filename: str,
        move_file: bool = True,
        display_name: str = "",
        notes: str = "",
    ) -> Dict[str, Any]:
        """Memindahkan/menyalin file `.gguf` dari `~/Downloads` ke `models/` dengan aman."""
        safe_name = os.path.basename((filename or "").strip())
        if not SAFE_GGUF_FILENAME_RE.match(safe_name):
            raise ValueError("Nama file `.gguf` tidak valid.")

        src_path = (USER_DOWNLOADS_DIR / safe_name).resolve()
        if not src_path.is_relative_to(USER_DOWNLOADS_DIR) or not src_path.is_file():
            raise FileNotFoundError(f"File '{safe_name}' tidak ditemukan di {USER_DOWNLOADS_DIR}.")

        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        dst_path = (MODELS_DIR / safe_name).resolve()
        if not dst_path.is_relative_to(MODELS_DIR):
            raise ValueError("Path tujuan tidak valid.")

        if move_file:
            shutil.move(str(src_path), str(dst_path))
        else:
            shutil.copy2(str(src_path), str(dst_path))

        if safe_name.lower() not in _CATALOG_BY_FILENAME:
            save_custom_model_metadata(
                filename=safe_name,
                display_name=display_name or Path(safe_name).stem,
                notes=notes or "Diimpor dari folder ~/Downloads",
            )

        return {
            "imported": True,
            "action": "moved" if move_file else "copied",
            "filename": safe_name,
            "path": str(dst_path),
            "size_gb": round(dst_path.stat().st_size / (1024 * 1024 * 1024), 2),
        }

    @classmethod
    def delete_local_model(cls, filename: str) -> Dict[str, Any]:
        safe_name = os.path.basename((filename or "").strip())
        if not SAFE_GGUF_FILENAME_RE.match(safe_name):
            raise ValueError("Nama file `.gguf` tidak valid.")

        target_path = (MODELS_DIR / safe_name).resolve()
        if not target_path.is_relative_to(MODELS_DIR) or not target_path.is_file():
            raise FileNotFoundError(f"Model '{safe_name}' tidak ditemukan di {MODELS_DIR}.")

        active_path = cls.read_active_model_from_proc()
        if active_path and os.path.abspath(active_path) == str(target_path):
            raise ValueError("Tidak bisa menghapus model yang sedang aktif di RAM. Switch atau matikan AI dahulu.")

        target_path.unlink()
        return {"deleted": True, "filename": safe_name}

    @classmethod
    async def get_runtime_status(cls, llama_base_url: str = "http://127.0.0.1:8080") -> Dict[str, Any]:
        bin_path = cls.find_llama_server_bin()
        local_models = cls.scan_local_models()
        downloads_gguf = cls.scan_downloads_gguf()
        pid = cls.get_running_llama_pid()
        active_model_path = cls.read_active_model_from_proc()

        online = False
        server_model_alias = None
        if httpx is not None:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    r = await client.get(f"{llama_base_url.rstrip('/')}/health")
                    online = r.status_code == 200
                    if online:
                        mr = await client.get(f"{llama_base_url.rstrip('/')}/v1/models")
                        if mr.status_code == 200:
                            mdata = mr.json().get("data", [])
                            if mdata:
                                server_model_alias = mdata[0].get("id")
            except Exception:
                online = False

        local_by_name = {m["filename"].lower(): m for m in local_models}
        jobs = download_manager.get_all_jobs()
        catalog_with_status: List[Dict[str, Any]] = []
        for entry in CURATED_GGUF_CATALOG:
            item = dict(entry)
            local_hit = local_by_name.get(entry["filename"].lower())
            part_path = (MODELS_DIR / f"{entry['filename']}.part").resolve()
            part_mb = 0.0
            part_pct = 0.0
            if not local_hit and part_path.is_file():
                part_mb = round(part_path.stat().st_size / (1024 * 1024), 1)
                if entry.get("size_mb", 0) > 0:
                    part_pct = min(99.9, round((part_mb / entry["size_mb"]) * 100.0, 1))
            item["downloaded"] = bool(local_hit)
            item["is_active"] = bool(local_hit and local_hit["is_active"])
            item["partial_mb"] = part_mb
            item["partial_percent"] = part_pct
            item["download_job"] = jobs.get(entry["catalog_id"])
            catalog_with_status.append(item)

        custom_jobs = [
            j for jid, j in jobs.items()
            if jid.startswith("custom:") and j.get("status") in ("DOWNLOADING", "ERROR")
        ]

        return {
            "llama_binary_installed": bool(bin_path),
            "llama_binary_path": str(bin_path) if bin_path else None,
            "llama_server_online": online,
            "llama_server_pid": pid,
            "active_model_path": active_model_path,
            "active_model_filename": os.path.basename(active_model_path) if active_model_path else server_model_alias,
            "models_dir": str(MODELS_DIR),
            "downloads_dir": str(USER_DOWNLOADS_DIR),
            "local_models": local_models,
            "downloads_gguf": downloads_gguf,
            "curated_catalog": catalog_with_status,
            "custom_download_jobs": custom_jobs,
            "total_cpu_cores": os.cpu_count() or 2,
        }

    @classmethod
    def stop_llama_server(cls) -> Dict[str, Any]:
        pid = cls.get_running_llama_pid()
        pid_file = cls.get_pid_file()
        active_model_file = cls.get_active_model_file()
        if active_model_file.exists():
            active_model_file.unlink()
        if not pid:
            if pid_file.exists():
                pid_file.unlink()
            return {"stopped": False, "detail": "llama-server tidak sedang berjalan."}

        if os.name == "nt":
            try:
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=8)
            except Exception:
                try:
                    os.kill(pid, signal.SIGTERM)
                except Exception:
                    pass
            if pid_file.exists():
                pid_file.unlink()
            return {"stopped": True, "pid": pid, "detail": "llama-server dihentikan di Windows."}

        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            if pid_file.exists():
                pid_file.unlink()
            return {"stopped": True, "pid": pid, "detail": "Proses sudah berhenti."}

        wnohang = getattr(os, "WNOHANG", None)
        for _ in range(25):
            time.sleep(0.15)
            if wnohang is not None:
                try:
                    reaped_pid, _ = os.waitpid(pid, wnohang)
                    if reaped_pid == pid:
                        if pid_file.exists():
                            pid_file.unlink()
                        return {"stopped": True, "pid": pid, "detail": "llama-server dihentikan dengan aman."}
                except ChildProcessError:
                    pass

            stat_path = Path(f"/proc/{pid}/stat")
            if stat_path.is_file():
                try:
                    stat_txt = stat_path.read_text(encoding="utf-8", errors="replace")
                    if ") Z " in stat_txt:
                        if pid_file.exists():
                            pid_file.unlink()
                        return {"stopped": True, "pid": pid, "detail": "llama-server selesai berhenti."}
                except Exception:
                    pass

            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                if pid_file.exists():
                    pid_file.unlink()
                return {"stopped": True, "pid": pid, "detail": "llama-server dihentikan dengan aman."}

        sigkill = getattr(signal, "SIGKILL", signal.SIGTERM)
        try:
            os.kill(pid, sigkill)
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass
        except ProcessLookupError:
            pass
        if pid_file.exists():
            pid_file.unlink()
        return {"stopped": True, "pid": pid, "detail": "llama-server dihentikan (SIGKILL fallback)."}

    @classmethod
    async def switch_model(
        cls,
        model_identifier: str,
        project_id: Optional[str] = None,
        ctx_size: int = 8192,
        threads: Optional[int] = None,
        kv_cache_type: Optional[str] = None,
        llama_host: str = "127.0.0.1",
        llama_port: int = 8080,
        startup_timeout_seconds: int = 60,
    ) -> Dict[str, Any]:
        bin_path = cls.find_llama_server_bin()
        if not bin_path:
            raise RuntimeError(
                f"Binary llama-server belum ditemukan di {BIN_DIR}/ atau PATH. "
                "Pasang llama-server terlebih dahulu."
            )

        model_path = cls.resolve_safe_model_path(model_identifier)
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file_path = LOG_DIR / "llama-server.log"

        cls.stop_llama_server()

        total_cores = os.cpu_count() or 2
        if threads is None:
            effective_threads = (total_cores - 1) if total_cores > 2 else total_cores
        else:
            effective_threads = max(1, min(total_cores, int(threads)))

        fa_args = cls.detect_flash_attn_args(bin_path)
        lm_args = cls.detect_load_mode_args(bin_path)
        qwen3_args = cls.detect_qwen3_reasoning_off_args(bin_path, model_path.name)

        model_size_gb = model_path.stat().st_size / (1024 * 1024 * 1024)
        effective_kv = (kv_cache_type or os.environ.get("LLAMA_KV_CACHE_TYPE", "")).strip().lower()
        if effective_kv not in ("f16", "q8_0", "q4_0"):
            effective_kv = "f16" if model_size_gb <= 2.6 else "q8_0"

        cmd: List[str] = [
            str(bin_path),
            "--model", str(model_path),
            "--host", str(llama_host),
            "--port", str(llama_port),
            "--ctx-size", str(int(ctx_size)),
            "--cache-type-k", effective_kv,
            "--cache-type-v", effective_kv,
            "--parallel", "1",
            "--threads", str(effective_threads),
            "--batch-size", "512",
            "--ubatch-size", "256",
            "--cont-batching",
            *lm_args,
            *fa_args,
            *qwen3_args,
        ]

        env = cls._build_subprocess_env(bin_path)

        def _apply_nice() -> None:
            try:
                if hasattr(os, "nice"):
                    os.nice(10)
            except OSError:
                pass

        popen_kwargs: Dict[str, Any] = {
            "stdout": None,
            "stderr": subprocess.STDOUT,
            "env": env,
        }
        if os.name == "nt":
            flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
                subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0
            )
            popen_kwargs["creationflags"] = flags
        else:
            popen_kwargs["start_new_session"] = True
            popen_kwargs["preexec_fn"] = _apply_nice

        with open(log_file_path, "ab") as log_f:
            log_f.write(
                f"\n=== [Model Switcher] Memuat model: {model_path.name} ({time.strftime('%Y-%m-%d %H:%M:%S')}) ===\n".encode(
                    "utf-8"
                )
            )
            popen_kwargs["stdout"] = log_f
            proc = subprocess.Popen(cmd, **popen_kwargs)

        cls.get_pid_file().write_text(str(proc.pid), encoding="utf-8")
        cls.get_active_model_file().write_text(str(model_path), encoding="utf-8")

        health_url = f"http://{llama_host}:{llama_port}/health"
        ready = False
        last_err = ""
        deadline = time.monotonic() + startup_timeout_seconds

        if httpx is not None:
            async with httpx.AsyncClient(timeout=2.5) as client:
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        break
                    try:
                        r = await client.get(health_url)
                        if r.status_code == 200:
                            ready = True
                            break
                        last_err = f"HTTP {r.status_code}"
                    except Exception as exc:
                        last_err = str(exc)
                    await asyncio.sleep(0.5)
        else:
            await asyncio.sleep(2.0)
            ready = proc.poll() is None

        if not ready:
            tail_log = ""
            if log_file_path.is_file():
                lines = log_file_path.read_text(encoding="utf-8", errors="replace").splitlines()
                tail_log = "\n".join(lines[-15:])
            raise RuntimeError(
                f"llama-server gagal siap dalam {startup_timeout_seconds}s ({last_err}). "
                f"Log terakhir:\n{tail_log}"
            )

        meta = _CATALOG_BY_FILENAME.get(model_path.name.lower(), {})
        resolved_profile = meta.get("profile_name") or model_path.stem
        if project_id:
            update_project(project_id, {"active_model_profile": resolved_profile})

        return {
            "switched": True,
            "pid": proc.pid,
            "model_filename": model_path.name,
            "model_path": str(model_path),
            "profile_name": resolved_profile,
            "ctx_size": ctx_size,
            "threads": effective_threads,
            "kv_cache_type": effective_kv,
            "health_url": health_url,
        }
