import asyncio
from contextlib import asynccontextmanager
import json
import os
import re
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from database import (
    DEFAULT_BANNED_PHRASES,
    add_episodic_memory,
    add_single_micro_beat,
    count_words,
    create_chapter,
    create_codex_item,
    create_project,
    create_story_phase,
    delete_chapter,
    delete_codex_item,
    delete_micro_beat,
    delete_project,
    delete_story_phase,
    export_project_backup_dict,
    get_active_phase_for_chapter,
    get_chapter,
    get_codex_item,
    get_micro_beat,
    get_project,
    get_story_bible_bundle,
    get_story_phase,
    import_project_backup_dict,
    init_db,
    list_beat_revisions,
    list_chapters,
    list_codex_items,
    list_micro_beats,
    list_projects,
    list_story_phases,
    move_micro_beat,
    replace_chapter_micro_beats,
    save_beat_prose_and_revision,
    search_codex_fts_bm25,
    search_episodic_memory_bm25,
    update_chapter,
    update_codex_item,
    update_micro_beat,
    update_project,
    update_story_phase,
)
from engine import (
    ContextAssembler,
    DeterministicPacingEngine,
    parse_json_safely,
)
from memory_manager import (
    FTS5MemoryRetriever,
    FourTierMemoryAssembler,
    PostBeatStateExtractor,
)
from exporter import router as exporter_router
from ai_provider import (
    build_chat_request,
    extract_nonstream_text,
    extract_stream_token,
    fetch_remote_models,
    get_public_provider_summary,
    load_provider_config,
    save_provider_config,
    test_provider_connection,
)
from model_manager import ModelRuntimeManager, download_manager
from security_config import (
    CloudflareSecurityConfig,
    CloudflareZeroTrustMiddleware,
)

security_config = CloudflareSecurityConfig.from_env()

LLAMA_SERVER_BASE_URL = os.environ.get("LLAMA_SERVER_URL", "http://127.0.0.1:8080")
LLAMA_CHAT_COMPLETIONS_URL = f"{LLAMA_SERVER_BASE_URL.rstrip('/')}/v1/chat/completions"
LLAMA_RAW_COMPLETION_URL = f"{LLAMA_SERVER_BASE_URL.rstrip('/')}/completion"


# ============================================================================
# SINGLE-WORKER ASYNCIO LOCK / QUEUE UNTUK LINUX MINT RAM 8 GB
# ============================================================================

class SingleWorkerInferenceQueue:
    """
    Menjamin native C++ llama-server (--parallel 1, id_slot: 0) di Linux Mint RAM 8 GB
    hanya pernah memproses tepat 1 request inferensi pada satu waktu.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._waiting_count = 0
        self._active_task_label: Optional[str] = None

    @property
    def is_busy(self) -> bool:
        return self._lock.locked()

    @property
    def waiting_count(self) -> int:
        return self._waiting_count

    @property
    def active_task_label(self) -> Optional[str]:
        return self._active_task_label

    @asynccontextmanager
    async def acquire_slot(self, task_label: str) -> AsyncGenerator[int, None]:
        self._waiting_count += 1
        queue_position = self._waiting_count
        try:
            await self._lock.acquire()
            self._waiting_count -= 1
            self._active_task_label = task_label
            yield queue_position
        finally:
            self._active_task_label = None
            if self._lock.locked():
                self._lock.release()


inference_queue = SingleWorkerInferenceQueue()
# Alias kompatibilitas dengan Bagian 9 Blueprint
inference_lock = inference_queue._lock


def get_linux_memory_status() -> Dict[str, Any]:
    """Membaca pemakaian RAM aktual lintas-OS (Linux/Android /proc/meminfo, macOS vm_stat, Windows GlobalMemoryStatusEx)."""
    base_queue_info = {
        "inference_busy": inference_queue.is_busy,
        "inference_waiting": inference_queue.waiting_count,
        "active_task": inference_queue.active_task_label,
    }
    # 1. Linux & Android Termux (/proc/meminfo)
    if os.path.isfile("/proc/meminfo"):
        mem: Dict[str, int] = {}
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        val_parts = parts[1].strip().split()
                        if val_parts and val_parts[0].isdigit():
                            mem[parts[0].strip()] = int(val_parts[0])
            total_mb = round(mem.get("MemTotal", 0) / 1024.0, 1)
            avail_mb = round(mem.get("MemAvailable", 0) / 1024.0, 1)
            used_mb = round(max(0.0, total_mb - avail_mb), 1)
            swap_total_mb = round(mem.get("SwapTotal", 0) / 1024.0, 1)
            swap_free_mb = round(mem.get("SwapFree", 0) / 1024.0, 1)
            return {
                "total_mb": total_mb,
                "used_mb": used_mb,
                "available_mb": avail_mb,
                "usage_percent": round((used_mb / total_mb) * 100.0, 1) if total_mb > 0 else 0.0,
                "swap_total_mb": swap_total_mb,
                "swap_used_mb": round(max(0.0, swap_total_mb - swap_free_mb), 1),
                **base_queue_info,
            }
        except Exception:
            pass

    # 2. Windows 10/11 (kernel32.GlobalMemoryStatusEx)
    if os.name == "nt":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))  # type: ignore[attr-defined]
            total_mb = round(stat.ullTotalPhys / (1024.0 * 1024.0), 1)
            avail_mb = round(stat.ullAvailPhys / (1024.0 * 1024.0), 1)
            used_mb = round(max(0.0, total_mb - avail_mb), 1)
            return {
                "total_mb": total_mb,
                "used_mb": used_mb,
                "available_mb": avail_mb,
                "usage_percent": round((used_mb / total_mb) * 100.0, 1) if total_mb > 0 else 0.0,
                "swap_total_mb": 0.0,
                "swap_used_mb": 0.0,
                **base_queue_info,
            }
        except Exception:
            pass

    # 3. macOS (sysctl + vm_stat)
    if os.name == "posix" and os.uname().sysname.lower() == "darwin":
        try:
            import subprocess as _sp

            total_bytes = int(_sp.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip())
            vm_out = _sp.check_output(["vm_stat"], text=True)
            page_size = 4096
            ps_m = re.search(r"page size of (\d+) bytes", vm_out)
            if ps_m:
                page_size = int(ps_m.group(1))
            free_pages = 0
            for key in ("Pages free", "Pages inactive", "Pages speculative"):
                km = re.search(rf"{key}:\s+(\d+)", vm_out)
                if km:
                    free_pages += int(km.group(1))
            total_mb = round(total_bytes / (1024.0 * 1024.0), 1)
            avail_mb = round((free_pages * page_size) / (1024.0 * 1024.0), 1)
            used_mb = round(max(0.0, total_mb - avail_mb), 1)
            return {
                "total_mb": total_mb,
                "used_mb": used_mb,
                "available_mb": avail_mb,
                "usage_percent": round((used_mb / total_mb) * 100.0, 1) if total_mb > 0 else 0.0,
                "swap_total_mb": 0.0,
                "swap_used_mb": 0.0,
                **base_queue_info,
            }
        except Exception:
            pass

    return {
        "total_mb": 8192.0,
        "used_mb": 0.0,
        "available_mb": 8192.0,
        "usage_percent": 0.0,
        "swap_total_mb": 0.0,
        "swap_used_mb": 0.0,
        **base_queue_info,
    }


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    yield


class StreamingSafeGZipMiddleware(GZipMiddleware):
    """Kompresi GZip (>=800 bytes) untuk JSON/HTML/JS/CSS, melewati endpoint SSE streaming."""

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") == "http":
            path = scope.get("path", "")
            if path.endswith("/stream") or path.endswith("/stream-beat"):
                await self.app(scope, receive, send)
                return
        await super().__call__(scope, receive, send)


app = FastAPI(
    title="AI Novel Studio Backend (Linux Mint 8GB RAM Edition)",
    version="1.0.0",
    description="Deterministic Narrative Pacing, 4-Tier FTS5 BM25 Memory, & Single-Slot llama-server Orchestrator",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(StreamingSafeGZipMiddleware, minimum_size=800)
app.add_middleware(CloudflareZeroTrustMiddleware, config=security_config)

if exporter_router is not None:
    app.include_router(exporter_router)


# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class ProjectCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    author_name: str = "Penulis Studio"
    genre: str = Field(..., min_length=1)
    main_objective: str = Field(..., min_length=1)
    logline: str = ""
    pov_style: str = "Third-Person Limited"
    tense_style: str = "Lampau / Past Narrative"
    tone_style: str = "Atmosferik, Imersif, Show Dont Tell"
    style_sample: str = ""
    banned_phrases: List[str] = Field(default_factory=lambda: list(DEFAULT_BANNED_PHRASES))
    total_planned_chapters: int = Field(default=24, ge=1, le=500)
    default_chapter_words: int = Field(default=3200, ge=400, le=20000)
    rolling_global_summary: str = ""
    active_model_profile: str = "Qwen2.5-3B-Instruct-Q4_K_M"
    seed_default_phases: bool = True


class ProjectUpdateRequest(BaseModel):
    title: Optional[str] = None
    author_name: Optional[str] = None
    genre: Optional[str] = None
    logline: Optional[str] = None
    main_objective: Optional[str] = None
    pov_style: Optional[str] = None
    tense_style: Optional[str] = None
    tone_style: Optional[str] = None
    style_sample: Optional[str] = None
    banned_phrases: Optional[List[str]] = None
    total_planned_chapters: Optional[int] = Field(default=None, ge=1, le=500)
    default_chapter_words: Optional[int] = Field(default=None, ge=400, le=20000)
    rolling_global_summary: Optional[str] = None
    active_model_profile: Optional[str] = None


class StoryPhaseCreateRequest(BaseModel):
    phase_order: int = Field(default=1, ge=1)
    phase_name: str = Field(..., min_length=1)
    start_chapter: int = Field(..., ge=1)
    end_chapter: int = Field(..., ge=1)
    default_pacing: str = Field(default="BALANCED", pattern="^(SLOW_BURN|BALANCED|FAST_PACED|FRENETIC_ACTION)$")
    tension_min: int = Field(default=15, ge=0, le=100)
    tension_max: int = Field(default=45, ge=0, le=100)
    building_focus: str = Field(..., min_length=1)
    phase_guardrails: str = Field(..., min_length=1)


class StoryPhaseUpdateRequest(BaseModel):
    phase_order: Optional[int] = Field(default=None, ge=1)
    phase_name: Optional[str] = None
    start_chapter: Optional[int] = Field(default=None, ge=1)
    end_chapter: Optional[int] = Field(default=None, ge=1)
    default_pacing: Optional[str] = Field(default=None, pattern="^(SLOW_BURN|BALANCED|FAST_PACED|FRENETIC_ACTION)$")
    tension_min: Optional[int] = Field(default=None, ge=0, le=100)
    tension_max: Optional[int] = Field(default=None, ge=0, le=100)
    building_focus: Optional[str] = None
    phase_guardrails: Optional[str] = None


class CodexCreateRequest(BaseModel):
    category: str = Field(..., pattern="^(CHARACTER|LOCATION|WORLD_RULE|ITEM|LORE)$")
    name: str = Field(..., min_length=1)
    core_description: str = Field(..., min_length=1)
    keywords_csv: str = ""
    aliases_and_tags: str = ""
    is_pinned: int = Field(default=0, ge=0, le=1)
    speech_style: str = ""
    current_state: Optional[Dict[str, Any]] = None


class CodexUpdateRequest(BaseModel):
    category: Optional[str] = Field(default=None, pattern="^(CHARACTER|LOCATION|WORLD_RULE|ITEM|LORE)$")
    name: Optional[str] = None
    core_description: Optional[str] = None
    keywords_csv: Optional[str] = None
    aliases_and_tags: Optional[str] = None
    is_pinned: Optional[int] = Field(default=None, ge=0, le=1)
    speech_style: Optional[str] = None
    current_state: Optional[Dict[str, Any]] = None


class ChapterCreateRequest(BaseModel):
    chapter_number: int = Field(..., ge=1)
    title: str = Field(..., min_length=1)
    chapter_goal: str = Field(..., min_length=1)
    target_word_count: int = Field(default=3200, ge=350, le=20000)
    pacing_mode: Optional[str] = Field(default=None, pattern="^(SLOW_BURN|BALANCED|FAST_PACED|FRENETIC_ACTION)$")
    phase_id: Optional[str] = None
    mix_world_building: int = Field(default=50, ge=0, le=100)
    mix_psychology: int = Field(default=50, ge=0, le=100)
    mix_sensory: int = Field(default=70, ge=0, le=100)
    mix_dialogue: int = Field(default=40, ge=0, le=100)
    mix_action: int = Field(default=30, ge=0, le=100)
    ending_hook_style: str = "CLIFFHANGER"
    chapter_summary: str = ""
    status: str = Field(default="PLANNED", pattern="^(PLANNED|DRAFTING|COMPLETED)$")


class ChapterUpdateRequest(BaseModel):
    phase_id: Optional[str] = None
    chapter_number: Optional[int] = Field(default=None, ge=1)
    title: Optional[str] = None
    chapter_goal: Optional[str] = None
    target_word_count: Optional[int] = Field(default=None, ge=350, le=20000)
    pacing_mode: Optional[str] = Field(default=None, pattern="^(SLOW_BURN|BALANCED|FAST_PACED|FRENETIC_ACTION)$")
    mix_world_building: Optional[int] = Field(default=None, ge=0, le=100)
    mix_psychology: Optional[int] = Field(default=None, ge=0, le=100)
    mix_sensory: Optional[int] = Field(default=None, ge=0, le=100)
    mix_dialogue: Optional[int] = Field(default=None, ge=0, le=100)
    mix_action: Optional[int] = Field(default=None, ge=0, le=100)
    ending_hook_style: Optional[str] = None
    chapter_summary: Optional[str] = None
    status: Optional[str] = Field(default=None, pattern="^(PLANNED|DRAFTING|COMPLETED)$")


class MicroBeatUpdateRequest(BaseModel):
    pov_character_id: Optional[str] = None
    location_id: Optional[str] = None
    tension_level: Optional[int] = Field(default=None, ge=0, le=100)
    target_words: Optional[int] = Field(default=None, ge=100, le=2000)
    beat_instruction: Optional[str] = None
    stopping_point: Optional[str] = None
    sensory_anchor: Optional[str] = None
    conflict_focus: Optional[str] = None
    generated_prose: Optional[str] = None
    extracted_summary: Optional[str] = None
    status: Optional[str] = Field(default=None, pattern="^(PENDING|STREAMING|COMPLETED|REVISED)$")


class StreamBeatCustomOptions(BaseModel):
    endpoint_mode: str = Field(default="chat", pattern="^(chat|completion)$")
    temperature: float = Field(default=1.02, ge=0.1, le=2.0)
    min_p: float = Field(default=0.07, ge=0.0, le=1.0)
    dry_multiplier: float = Field(default=0.8, ge=0.0, le=5.0)
    xtc_probability: float = Field(default=0.1, ge=0.0, le=1.0)
    additional_author_note: str = ""
    save_on_complete: bool = True


class DirectWriteBeatRequest(BaseModel):
    """Kompatibilitas dengan payload langsung Bagian 9 Blueprint (/api/stream-beat)."""
    static_system_prompt: str
    dynamic_user_prompt: str
    target_words: int = 400
    beat_id: Optional[str] = None


class ModelSwitchRequest(BaseModel):
    model_identifier: str = Field(..., min_length=1)
    project_id: Optional[str] = None
    ctx_size: int = Field(default=8192, ge=1024, le=32768)
    threads: Optional[int] = Field(default=None, ge=1, le=32)
    kv_cache_type: Optional[str] = Field(default=None, pattern="^(f16|q8_0|q4_0)$")


class ModelDownloadRequest(BaseModel):
    catalog_id: str = Field(..., min_length=1)


class CustomModelDownloadRequest(BaseModel):
    url_or_repo: str = Field(..., min_length=3)
    filename: str = ""
    display_name: str = ""
    notes: str = ""


class ImportLocalModelRequest(BaseModel):
    filename: str = Field(..., min_length=1)
    move_file: bool = True
    display_name: str = ""
    notes: str = ""


class AIProviderConfigRequest(BaseModel):
    provider_type: str = Field(..., pattern="^(local_llama|openai_compatible|anthropic)$")
    preset_id: str = "custom_openai"
    display_name: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    clear_api_key: bool = False
    timeout_seconds: int = Field(default=180, ge=15, le=600)
    stop_local_llama: bool = True


class AIProviderModelsQuery(BaseModel):
    provider_type: str = Field(default="openai_compatible", pattern="^(openai_compatible|anthropic)$")
    base_url: str = Field(..., min_length=4)
    api_key: Optional[str] = None


# ============================================================================
# HELPER PANGGILAN MESIN AI NON-STREAMING (ARCHITECT & EXTRACTOR LINTAS-PROVIDER)
# ============================================================================

async def call_llama_server_json(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1800,
    temperature: float = 0.35,
) -> Optional[Any]:
    """
    Memanggil provider AI aktif (lokal llama-server, OpenAI-compatible online/Ollama,
    atau Anthropic Claude) untuk menghasilkan struktur JSON (Plot Architect & State Extractor).
    """
    provider_cfg = load_provider_config(LLAMA_SERVER_BASE_URL)
    ptype = str(provider_cfg.get("provider_type") or "local_llama").lower()
    local_sampler = {
        "cache_prompt": True,
        "id_slot": 0,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "min_p": 0.07,
        "repeat_penalty": 1.05,
    }
    url, headers, chat_payload = build_chat_request(
        provider_cfg=provider_cfg,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        stream=False,
        llama_sampler=local_sampler,
        endpoint_mode="chat",
    )

    try:
        json_timeout = httpx.Timeout(connect=10.0, write=30.0, read=600.0, pool=10.0)
        async with httpx.AsyncClient(timeout=json_timeout) as client:
            resp = await client.post(url, headers=headers, json=chat_payload)
            if resp.status_code == 200:
                body = resp.json()
                content = extract_nonstream_text(ptype, body)
                parsed = parse_json_safely(content)
                if parsed is not None:
                    return parsed

            # Fallback ke endpoint native /completion hanya jika mode local_llama
            if ptype == "local_llama":
                raw_payload = {
                    "prompt": f"{system_prompt}\n\n{user_prompt}\n",
                    "stream": False,
                    "cache_prompt": True,
                    "id_slot": 0,
                    "n_predict": max_tokens,
                    "temperature": temperature,
                    "min_p": 0.07,
                }
                resp_raw = await client.post(LLAMA_RAW_COMPLETION_URL, json=raw_payload)
                if resp_raw.status_code == 200:
                    body_raw = resp_raw.json()
                    content_raw = body_raw.get("content", "")
                    return parse_json_safely(content_raw)
    except Exception:
        return None
    return None


# ============================================================================
# ENDPOINT SISTEM & PEMANTAUAN RAM LINUX MINT 8 GB
# ============================================================================

@app.get("/api/system/ram")
def check_ram() -> Dict[str, Any]:
    return get_linux_memory_status()


@app.get("/api/system/health")
async def system_health() -> Dict[str, Any]:
    ram_info = get_linux_memory_status()
    llama_online = False
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            r = await client.get(f"{LLAMA_SERVER_BASE_URL.rstrip('/')}/health")
            llama_online = r.status_code == 200
    except Exception:
        llama_online = False

    active_model_path = ModelRuntimeManager.read_active_model_from_proc()
    provider_summary = get_public_provider_summary(LLAMA_SERVER_BASE_URL)
    ai_ready = (provider_summary["provider_type"] != "local_llama") or llama_online
    return {
        "status": "ok",
        "llama_server_url": LLAMA_SERVER_BASE_URL,
        "llama_server_online": llama_online,
        "ai_ready": ai_ready,
        "llama_binary_installed": bool(ModelRuntimeManager.find_llama_server_bin()),
        "active_model_filename": os.path.basename(active_model_path) if active_model_path else None,
        "ai_provider": provider_summary,
        "ram": ram_info,
        "security": security_config.public_summary(),
    }


@app.get("/api/system/security-status")
def system_security_status() -> Dict[str, Any]:
    return security_config.public_summary()


# ============================================================================
# ENDPOINT API MODEL SWITCHER & DOWNLOADER GGUF (DUAL-MODEL RUNTIME CONTROL)
# ============================================================================

@app.get("/api/models")
async def api_list_models() -> Dict[str, Any]:
    """Menampilkan daftar file .gguf lokal, status model aktif di RAM, & katalog kurasi."""
    return await ModelRuntimeManager.get_runtime_status(LLAMA_SERVER_BASE_URL)


@app.post("/api/models/switch")
async def api_switch_model(req: ModelSwitchRequest) -> Dict[str, Any]:
    """
    Menghentikan llama-server model lama agar RAM bersih, lalu menyalakan llama-server
    dengan model `.gguf` pilihan baru secara atomik di bawah SingleWorkerInferenceQueue.
    """
    from urllib.parse import urlparse

    parsed = urlparse(LLAMA_SERVER_BASE_URL)
    llama_host = parsed.hostname or "127.0.0.1"
    llama_port = parsed.port or 8080

    async with inference_queue.acquire_slot(f"switch-model:{req.model_identifier}"):
        try:
            result = await ModelRuntimeManager.switch_model(
                model_identifier=req.model_identifier,
                project_id=req.project_id,
                ctx_size=req.ctx_size,
                threads=req.threads,
                kv_cache_type=req.kv_cache_type,
                llama_host=llama_host,
                llama_port=llama_port,
            )
            save_provider_config(
                {"provider_type": "local_llama", "preset_id": "local_llama"},
                local_llama_url=LLAMA_SERVER_BASE_URL,
            )
            return result
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/models/stop")
async def api_stop_llama_server() -> Dict[str, Any]:
    """Menghentikan proses llama-server untuk membebaskan seluruh RAM model."""
    async with inference_queue.acquire_slot("stop-llama-server"):
        return ModelRuntimeManager.stop_llama_server()


@app.get("/api/ai/provider")
def api_get_ai_provider() -> Dict[str, Any]:
    """Mengambil konfigurasi provider AI aktif (aman tanpa plaintext API Key) & daftar preset."""
    return get_public_provider_summary(LLAMA_SERVER_BASE_URL)


@app.post("/api/ai/provider")
async def api_set_ai_provider(req: AIProviderConfigRequest) -> Dict[str, Any]:
    """Mengaktifkan mode Lokal GGUF atau API Online/Eksternal (OpenAI, Gemini, Groq, OpenRouter, Claude, Ollama, dll.)."""
    async with inference_queue.acquire_slot(f"switch-ai-provider:{req.provider_type}"):
        try:
            saved = save_provider_config(
                {
                    "provider_type": req.provider_type,
                    "preset_id": req.preset_id,
                    "display_name": req.display_name,
                    "base_url": req.base_url,
                    "model_name": req.model_name,
                    "api_key": req.api_key,
                    "clear_api_key": req.clear_api_key,
                    "timeout_seconds": req.timeout_seconds,
                },
                local_llama_url=LLAMA_SERVER_BASE_URL,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        stop_info = None
        if req.provider_type != "local_llama" and req.stop_local_llama:
            stop_info = ModelRuntimeManager.stop_llama_server()

        return {
            "saved": True,
            "provider": get_public_provider_summary(LLAMA_SERVER_BASE_URL),
            "stopped_local_llama": stop_info,
            "configured_model": saved.get("model_name"),
        }


@app.post("/api/ai/provider/test")
async def api_test_ai_provider(req: Optional[AIProviderConfigRequest] = None) -> Dict[str, Any]:
    """Menguji koneksi nyata & API key terhadap provider sebelum disimpan/digunakan."""
    payload = req.model_dump(exclude_unset=True) if req else None
    try:
        return await test_provider_connection(payload, local_llama_url=LLAMA_SERVER_BASE_URL)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Uji koneksi gagal: {e}") from e


@app.post("/api/ai/provider/models")
async def api_list_remote_provider_models(req: AIProviderModelsQuery) -> Dict[str, Any]:
    """Mengambil daftar ID model yang tersedia langsung dari endpoint `/v1/models` provider."""
    try:
        effective_key = (req.api_key or "").strip()
        if not effective_key:
            current = load_provider_config(LLAMA_SERVER_BASE_URL)
            if current.get("base_url", "").rstrip("/") == req.base_url.strip().rstrip("/"):
                effective_key = str(current.get("api_key") or "")
        models = await fetch_remote_models(
            base_url=req.base_url,
            provider_type=req.provider_type,
            api_key=effective_key,
        )
        return {"models": models, "count": len(models)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal mengambil daftar model: {e}") from e


@app.post("/api/models/download")
def api_start_model_download(req: ModelDownloadRequest) -> Dict[str, Any]:
    """Memulai unduhan background model .gguf dari katalog resmi Bartowski/HuggingFace."""
    try:
        return download_manager.start_download(req.catalog_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/api/models/downloads")
def api_list_model_downloads() -> Dict[str, Dict[str, Any]]:
    return download_manager.get_all_jobs()


@app.post("/api/models/downloads/{catalog_id}/cancel")
def api_cancel_model_download(catalog_id: str) -> Dict[str, Any]:
    cancelled = download_manager.cancel_download(catalog_id)
    return {"catalog_id": catalog_id, "cancelled": cancelled}


@app.post("/api/models/download-custom")
def api_download_custom_model(req: CustomModelDownloadRequest) -> Dict[str, Any]:
    """Mengunduh model `.gguf` kustom dari URL HuggingFace / Repo ID publik."""
    try:
        return download_manager.start_custom_download(
            url_or_repo=req.url_or_repo,
            filename=req.filename,
            display_name=req.display_name,
            notes=req.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/models/import-local")
def api_import_local_model(req: ImportLocalModelRequest) -> Dict[str, Any]:
    """Memindahkan/menyalin file `.gguf` dari folder ~/Downloads ke folder models/."""
    try:
        return ModelRuntimeManager.import_from_downloads(
            filename=req.filename,
            move_file=req.move_file,
            display_name=req.display_name,
            notes=req.notes,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.delete("/api/models/local/{filename}")
def api_delete_local_model(filename: str) -> Dict[str, Any]:
    """Menghapus file `.gguf` non-aktif dari folder models/ untuk menghemat disk."""
    try:
        return ModelRuntimeManager.delete_local_model(filename)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ============================================================================
# ENDPOINT CRUD PROJECTS (STORY BIBLE)
# ============================================================================

@app.post("/api/projects", status_code=201)
def api_create_project(req: ProjectCreateRequest) -> Dict[str, Any]:
    return create_project(
        title=req.title,
        author_name=req.author_name,
        genre=req.genre,
        main_objective=req.main_objective,
        logline=req.logline,
        pov_style=req.pov_style,
        tense_style=req.tense_style,
        tone_style=req.tone_style,
        style_sample=req.style_sample,
        banned_phrases=req.banned_phrases,
        total_planned_chapters=req.total_planned_chapters,
        default_chapter_words=req.default_chapter_words,
        rolling_global_summary=req.rolling_global_summary,
        active_model_profile=req.active_model_profile,
        seed_default_phases=req.seed_default_phases,
    )


@app.get("/api/projects")
def api_list_projects() -> List[Dict[str, Any]]:
    return list_projects()


@app.get("/api/projects/{project_id}")
def api_get_project(project_id: str) -> Dict[str, Any]:
    proj = get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project tidak ditemukan.")
    return proj


@app.put("/api/projects/{project_id}")
@app.patch("/api/projects/{project_id}")
def api_update_project(project_id: str, req: ProjectUpdateRequest) -> Dict[str, Any]:
    existing = get_project(project_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Project tidak ditemukan.")
    updated = update_project(project_id, req.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Gagal memperbarui project.")
    return updated


@app.delete("/api/projects/{project_id}")
def api_delete_project(project_id: str) -> Dict[str, Any]:
    deleted = delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project tidak ditemukan.")
    return {"deleted": True, "id": project_id}


@app.get("/api/projects/{project_id}/story-bible")
def api_get_story_bible(
    project_id: str,
    chapter_number: Optional[int] = Query(default=None, ge=1),
    q: str = Query(default=""),
) -> Dict[str, Any]:
    try:
        return get_story_bible_bundle(
            project_id=project_id,
            chapter_number=chapter_number,
            query_context=q,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/api/projects/{project_id}/backup")
def api_export_project_backup(project_id: str) -> Response:
    """Mengunduh snapshot cadangan lengkap seluruh proyek dalam format JSON."""
    try:
        snapshot = export_project_backup_dict(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    safe_title = re.sub(r"[^a-zA-Z0-9_-]+", "_", snapshot["project"]["title"]).strip("_").lower() or "novel"
    return Response(
        content=json.dumps(snapshot, ensure_ascii=False, indent=2).encode("utf-8"),
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_title}_backup.json"',
            "Cache-Control": "no-store",
        },
    )


@app.post("/api/projects/restore", status_code=201)
def api_restore_project_backup(backup_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Mengimpor kembali file cadangan proyek (.json) menjadi proyek novel baru yang utuh."""
    try:
        return import_project_backup_dict(backup_payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ============================================================================
# ENDPOINT CRUD STORY PHASES (RENTANG BAB X - Y)
# ============================================================================

@app.post("/api/projects/{project_id}/phases", status_code=201)
def api_create_story_phase(project_id: str, req: StoryPhaseCreateRequest) -> Dict[str, Any]:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Project tidak ditemukan.")
    if req.start_chapter > req.end_chapter:
        raise HTTPException(
            status_code=400,
            detail="start_chapter tidak boleh lebih besar dari end_chapter.",
        )
    if req.tension_min > req.tension_max:
        raise HTTPException(
            status_code=400,
            detail="tension_min tidak boleh lebih besar dari tension_max.",
        )
    return create_story_phase(
        project_id=project_id,
        phase_order=req.phase_order,
        phase_name=req.phase_name,
        start_chapter=req.start_chapter,
        end_chapter=req.end_chapter,
        default_pacing=req.default_pacing,
        tension_min=req.tension_min,
        tension_max=req.tension_max,
        building_focus=req.building_focus,
        phase_guardrails=req.phase_guardrails,
    )


@app.get("/api/projects/{project_id}/phases")
def api_list_story_phases(project_id: str) -> List[Dict[str, Any]]:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Project tidak ditemukan.")
    return list_story_phases(project_id)


@app.get("/api/projects/{project_id}/active-phase/{chapter_number}")
def api_get_active_phase(project_id: str, chapter_number: int) -> Dict[str, Any]:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Project tidak ditemukan.")
    phase = get_active_phase_for_chapter(project_id, chapter_number)
    if not phase:
        raise HTTPException(status_code=404, detail="Story Phase untuk nomor bab ini belum diatur.")
    return phase


@app.put("/api/phases/{phase_id}")
@app.patch("/api/phases/{phase_id}")
def api_update_story_phase(phase_id: str, req: StoryPhaseUpdateRequest) -> Dict[str, Any]:
    existing = get_story_phase(phase_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Story Phase tidak ditemukan.")
    updated = update_story_phase(phase_id, req.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Gagal memperbarui Story Phase.")
    return updated


@app.delete("/api/phases/{phase_id}")
def api_delete_story_phase(phase_id: str) -> Dict[str, Any]:
    if not delete_story_phase(phase_id):
        raise HTTPException(status_code=404, detail="Story Phase tidak ditemukan.")
    return {"deleted": True, "id": phase_id}


# ============================================================================
# ENDPOINT CRUD CODEX / LOREBOOK & FTS5 BM25 SEARCH
# ============================================================================

@app.post("/api/projects/{project_id}/codex", status_code=201)
def api_create_codex_item(project_id: str, req: CodexCreateRequest) -> Dict[str, Any]:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Project tidak ditemukan.")
    return create_codex_item(
        project_id=project_id,
        category=req.category,
        name=req.name,
        core_description=req.core_description,
        keywords_csv=req.keywords_csv,
        aliases_and_tags=req.aliases_and_tags,
        is_pinned=req.is_pinned,
        speech_style=req.speech_style,
        current_state=req.current_state,
    )


@app.get("/api/projects/{project_id}/codex")
def api_list_codex_items(
    project_id: str,
    category: Optional[str] = Query(default=None),
    pinned_only: bool = Query(default=False),
) -> List[Dict[str, Any]]:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Project tidak ditemukan.")
    return list_codex_items(project_id, category=category, pinned_only=pinned_only)


@app.get("/api/projects/{project_id}/codex/search")
def api_search_codex_bm25(
    project_id: str,
    q: str = Query(..., min_length=1),
    limit: int = Query(default=6, ge=1, le=30),
) -> Dict[str, Any]:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Project tidak ditemukan.")
    codex_hits = search_codex_fts_bm25(project_id=project_id, query_text=q, limit=limit)
    episodic_hits = search_episodic_memory_bm25(project_id=project_id, query_text=q, limit=limit)
    return {
        "query": q,
        "codex_matches": codex_hits,
        "episodic_memories": episodic_hits,
    }


@app.get("/api/codex/{codex_id}")
def api_get_codex_item(codex_id: str) -> Dict[str, Any]:
    item = get_codex_item(codex_id)
    if not item:
        raise HTTPException(status_code=404, detail="Codex item tidak ditemukan.")
    return item


@app.put("/api/codex/{codex_id}")
@app.patch("/api/codex/{codex_id}")
def api_update_codex_item(codex_id: str, req: CodexUpdateRequest) -> Dict[str, Any]:
    if not get_codex_item(codex_id):
        raise HTTPException(status_code=404, detail="Codex item tidak ditemukan.")
    updated = update_codex_item(codex_id, req.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Gagal memperbarui Codex item.")
    return updated


@app.delete("/api/codex/{codex_id}")
def api_delete_codex_item(codex_id: str) -> Dict[str, Any]:
    if not delete_codex_item(codex_id):
        raise HTTPException(status_code=404, detail="Codex item tidak ditemukan.")
    return {"deleted": True, "id": codex_id}


# ============================================================================
# ENDPOINT CRUD CHAPTER CONFIG & PACING PLAN
# ============================================================================

@app.post("/api/projects/{project_id}/chapters", status_code=201)
def api_create_chapter(project_id: str, req: ChapterCreateRequest) -> Dict[str, Any]:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Project tidak ditemukan.")
    try:
        return create_chapter(
            project_id=project_id,
            chapter_number=req.chapter_number,
            title=req.title,
            chapter_goal=req.chapter_goal,
            target_word_count=req.target_word_count,
            pacing_mode=req.pacing_mode,
            phase_id=req.phase_id,
            mix_world_building=req.mix_world_building,
            mix_psychology=req.mix_psychology,
            mix_sensory=req.mix_sensory,
            mix_dialogue=req.mix_dialogue,
            mix_action=req.mix_action,
            ending_hook_style=req.ending_hook_style,
            chapter_summary=req.chapter_summary,
            status=req.status,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal membuat bab: {e}") from e


@app.get("/api/projects/{project_id}/chapters")
def api_list_chapters(project_id: str) -> List[Dict[str, Any]]:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Project tidak ditemukan.")
    return list_chapters(project_id)


@app.get("/api/chapters/{chapter_id}")
def api_get_chapter(chapter_id: str) -> Dict[str, Any]:
    ch = get_chapter(chapter_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Bab tidak ditemukan.")
    ch["beats"] = list_micro_beats(chapter_id)
    return ch


@app.put("/api/chapters/{chapter_id}")
@app.patch("/api/chapters/{chapter_id}")
def api_update_chapter(chapter_id: str, req: ChapterUpdateRequest) -> Dict[str, Any]:
    if not get_chapter(chapter_id):
        raise HTTPException(status_code=404, detail="Bab tidak ditemukan.")
    updated = update_chapter(chapter_id, req.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Gagal memperbarui bab.")
    return updated


@app.delete("/api/chapters/{chapter_id}")
def api_delete_chapter(chapter_id: str) -> Dict[str, Any]:
    if not delete_chapter(chapter_id):
        raise HTTPException(status_code=404, detail="Bab tidak ditemukan.")
    return {"deleted": True, "id": chapter_id}


@app.get("/api/chapters/{chapter_id}/calculate-plan")
def api_calculate_chapter_plan(chapter_id: str) -> Dict[str, Any]:
    ch = get_chapter(chapter_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Bab tidak ditemukan.")

    t_min = int(ch.get("tension_min") or 15)
    t_max = int(ch.get("tension_max") or 55)
    plan = DeterministicPacingEngine.calculate_chapter_plan(
        target_words=int(ch["target_word_count"]),
        pacing_mode=str(ch["pacing_mode"]),
        t_min=t_min,
        t_max=t_max,
    )
    directives = DeterministicPacingEngine.compile_mixing_directives(
        ch, int(round((t_min + t_max) / 2))
    )
    return {
        "chapter_id": ch["id"],
        "chapter_number": ch["chapter_number"],
        "chapter_title": ch["title"],
        "phase_name": ch.get("phase_name"),
        "plan": plan,
        "mixing_directives": directives,
    }


class SingleBeatCreateRequest(BaseModel):
    beat_instruction: str = "Lanjutkan adegan berikutnya secara konkret dan atmosferik."
    stopping_point: str = "Hentikan tepat pada dialog atau tindakan mikro penutup."
    target_words: int = Field(default=400, ge=100, le=2000)
    tension_level: int = Field(default=45, ge=5, le=100)
    pov_character_id: Optional[str] = None
    location_id: Optional[str] = None
    sensory_anchor: str = ""
    conflict_focus: str = ""


@app.get("/api/chapters/{chapter_id}/beats")
def api_list_chapter_beats(chapter_id: str) -> List[Dict[str, Any]]:
    if not get_chapter(chapter_id):
        raise HTTPException(status_code=404, detail="Bab tidak ditemukan.")
    return list_micro_beats(chapter_id)


@app.post("/api/chapters/{chapter_id}/beats", status_code=201)
def api_add_single_chapter_beat(chapter_id: str, req: SingleBeatCreateRequest) -> Dict[str, Any]:
    if not get_chapter(chapter_id):
        raise HTTPException(status_code=404, detail="Bab tidak ditemukan.")
    return add_single_micro_beat(
        chapter_id=chapter_id,
        beat_instruction=req.beat_instruction,
        stopping_point=req.stopping_point,
        target_words=req.target_words,
        tension_level=req.tension_level,
        pov_character_id=req.pov_character_id,
        location_id=req.location_id,
        sensory_anchor=req.sensory_anchor,
        conflict_focus=req.conflict_focus,
    )


@app.delete("/api/beats/{beat_id}")
def api_delete_single_beat(beat_id: str) -> Dict[str, Any]:
    if not delete_micro_beat(beat_id):
        raise HTTPException(status_code=404, detail="Micro-Beat tidak ditemukan.")
    return {"deleted": True, "id": beat_id}


class BeatMoveRequest(BaseModel):
    direction: str = Field(..., pattern="^(up|down)$")


@app.post("/api/beats/{beat_id}/move")
def api_move_micro_beat(beat_id: str, req: BeatMoveRequest) -> List[Dict[str, Any]]:
    """Memindahkan urutan Micro-Beat ke atas atau ke bawah dalam bab."""
    try:
        return move_micro_beat(beat_id, req.direction)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/api/beats/{beat_id}")
def api_get_micro_beat(beat_id: str) -> Dict[str, Any]:
    beat = get_micro_beat(beat_id)
    if not beat:
        raise HTTPException(status_code=404, detail="Micro-Beat tidak ditemukan.")
    return beat


@app.put("/api/beats/{beat_id}")
@app.patch("/api/beats/{beat_id}")
def api_update_micro_beat(beat_id: str, req: MicroBeatUpdateRequest) -> Dict[str, Any]:
    if not get_micro_beat(beat_id):
        raise HTTPException(status_code=404, detail="Micro-Beat tidak ditemukan.")
    updated = update_micro_beat(beat_id, req.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Gagal memperbarui Micro-Beat.")
    return updated


@app.get("/api/beats/{beat_id}/revisions")
def api_list_beat_revisions(beat_id: str) -> List[Dict[str, Any]]:
    if not get_micro_beat(beat_id):
        raise HTTPException(status_code=404, detail="Micro-Beat tidak ditemukan.")
    return list_beat_revisions(beat_id)


class ManualRevisionSaveRequest(BaseModel):
    prose_content: str
    revision_note: str = "Manual Author Edit"


@app.post("/api/beats/{beat_id}/revisions", status_code=201)
def api_save_manual_beat_revision(beat_id: str, req: ManualRevisionSaveRequest) -> Dict[str, Any]:
    if not get_micro_beat(beat_id):
        raise HTTPException(status_code=404, detail="Micro-Beat tidak ditemukan.")
    saved = save_beat_prose_and_revision(
        beat_id=beat_id,
        prose_content=req.prose_content,
        revision_note=req.revision_note,
        status="REVISED",
    )
    return saved


# ============================================================================
# ENDPOINT GENERATE MICRO-BEATS OLEH AI PLOT ARCHITECT
# ============================================================================

@app.post("/api/chapters/{chapter_id}/generate-beats")
async def api_generate_chapter_beats(chapter_id: str) -> Dict[str, Any]:
    """
    Meminta AI Plot Architect memecah Chapter Goal menjadi daftar Micro-Beats
    sesuai target kata (target_word_count), mode pacing (SLOW_BURN / BALANCED / FAST_PACED),
    dan kurva ketegangan (tension_curve).
    Menggunakan Single-Worker Asyncio Lock agar aman di RAM 8 GB.
    """
    try:
        architect_ctx = ContextAssembler.assemble_plot_architect_prompts(chapter_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    chapter = architect_ctx["chapter"]
    plan = architect_ctx["plan"]
    codex_items = architect_ctx["codex_items"]
    total_beats = int(plan["total_micro_beats"])
    words_per_beat = int(plan["words_per_beat"])
    tension_curve = plan["tension_curve"]

    # Map nama karakter & lokasi ke ID codex jika cocok
    char_map = {
        c["name"].lower(): c["id"]
        for c in codex_items
        if c["category"] == "CHARACTER"
    }
    loc_map = {
        c["name"].lower(): c["id"]
        for c in codex_items
        if c["category"] == "LOCATION"
    }
    default_char_id = next(iter(char_map.values()), None)
    default_loc_id = next(iter(loc_map.values()), None)

    async with inference_queue.acquire_slot(f"plot-architect:chapter-{chapter['chapter_number']}"):
        llm_result = await call_llama_server_json(
            system_prompt=architect_ctx["system_prompt"],
            user_prompt=architect_ctx["user_prompt"],
            max_tokens=min(2400, total_beats * 220),
            temperature=0.4,
        )

    raw_beats: List[Dict[str, Any]] = []
    generation_source = "llama_server_architect"

    if isinstance(llm_result, dict) and isinstance(llm_result.get("beats"), list):
        raw_beats = llm_result["beats"]
    elif isinstance(llm_result, list):
        raw_beats = llm_result

    fallback_beats = ContextAssembler.build_deterministic_fallback_beats(
        chapter=chapter, plan=plan, codex_items=codex_items
    )

    if not raw_beats:
        generation_source = "deterministic_pacing_engine"
        final_beats_payload = fallback_beats
    else:
        final_beats_payload = []
        for idx in range(total_beats):
            fb = fallback_beats[idx]
            item = raw_beats[idx] if idx < len(raw_beats) and isinstance(raw_beats[idx], dict) else {}

            pov_name = str(item.get("pov_character_name", "")).strip().lower()
            loc_name = str(item.get("location_name", "")).strip().lower()

            resolved_pov_id = item.get("pov_character_id") or char_map.get(pov_name) or default_char_id
            resolved_loc_id = item.get("location_id") or loc_map.get(loc_name) or default_loc_id

            final_beats_payload.append(
                {
                    "beat_number": idx + 1,
                    "pov_character_id": resolved_pov_id,
                    "location_id": resolved_loc_id,
                    "tension_level": int(item.get("tension_level") or tension_curve[idx]),
                    "target_words": int(item.get("target_words") or words_per_beat),
                    "sensory_anchor": str(item.get("sensory_anchor") or fb["sensory_anchor"]).strip(),
                    "conflict_focus": str(item.get("conflict_focus") or fb["conflict_focus"]).strip(),
                    "beat_instruction": str(item.get("beat_instruction") or fb["beat_instruction"]).strip(),
                    "stopping_point": str(item.get("stopping_point") or fb["stopping_point"]).strip(),
                }
            )

    saved_beats = replace_chapter_micro_beats(chapter_id, final_beats_payload)
    update_chapter(chapter_id, {"status": "DRAFTING"})

    return {
        "chapter_id": chapter_id,
        "chapter_number": chapter["chapter_number"],
        "generation_source": generation_source,
        "pacing_plan": plan,
        "beats": saved_beats,
    }


# ============================================================================
# ENDPOINT STREAMING GENERASI NARASI PER MICRO-BEAT (SSE + ANTI-SUMMARY TRIM)
# ============================================================================

async def _stream_beat_sse_generator(
    beat_id: str,
    options: StreamBeatCustomOptions,
    request: Optional[Request] = None,
) -> AsyncGenerator[str, None]:
    """
    Generator Server-Sent Events (SSE) yang:
    1. Mengantri secara aman pada SingleWorkerInferenceQueue (1 proses di RAM 8 GB).
    2. Merakit konteks 4-Tier & Sampler Sastra (`id_slot: 0`, KV Cache Pinning).
    3. Mengirim heartbeat `PROCESSING_PROMPT` tiap 2 detik selama prompt dievaluasi CPU
       sehingga koneksi HTTP/browser tidak pernah putus/terlihat macet.
    4. Memutus koneksi llama-server seketika bila penulis menekan Hentikan (`is_disconnected`).
    5. Menjalankan Anti-Summary Tail Trimming di akhir stream dan menyimpan ke SQLite.
    """
    try:
        assembled = ContextAssembler.assemble_beat_prompts(beat_id)
    except ValueError as e:
        yield f"data: {json.dumps({'status': 'ERROR', 'detail': str(e)}, ensure_ascii=False)}\n\n"
        return

    beat = assembled["beat"]
    project = assembled["project"]
    static_system_prompt = assembled["static_system_prompt"]
    dynamic_user_prompt = assembled["dynamic_user_prompt"]
    if options.additional_author_note.strip():
        dynamic_user_prompt += f"\n\n[CATATAN KHUSUS SUTRADARA]: {options.additional_author_note.strip()}"

    sampler = ContextAssembler.get_literary_sampler_params(
        target_words=int(beat.get("target_words", 400)),
        temperature=options.temperature,
        min_p=options.min_p,
        dry_multiplier=options.dry_multiplier,
        xtc_probability=options.xtc_probability,
        id_slot=0,
    )

    if inference_queue.is_busy:
        yield (
            f"data: {json.dumps({'status': 'QUEUED', 'detail': 'Menunggu giliran memori AI (Single-Slot RAM 8 GB)...', 'waiting': inference_queue.waiting_count + 1}, ensure_ascii=False)}\n\n"
        )

    async with inference_queue.acquire_slot(f"stream-beat:{beat_id}"):
        prev_status = beat.get("status") or "PENDING"
        update_micro_beat(beat_id, {"status": "STREAMING"})
        yield (
            f"data: {json.dumps({'status': 'STARTED', 'beat_id': beat_id, 'beat_number': beat['beat_number'], 'sampler': sampler}, ensure_ascii=False)}\n\n"
        )

        collected_chunks: List[str] = []

        provider_cfg = load_provider_config(LLAMA_SERVER_BASE_URL)
        ptype = str(provider_cfg.get("provider_type") or "local_llama").lower()
        target_url, req_headers, payload = build_chat_request(
            provider_cfg=provider_cfg,
            system_prompt=static_system_prompt,
            user_prompt=dynamic_user_prompt,
            max_tokens=sampler["max_tokens"],
            temperature=sampler["temperature"],
            stream=True,
            llama_sampler=sampler,
            endpoint_mode=options.endpoint_mode,
        )
        provider_label = provider_cfg.get("display_name") or ptype

        token_queue: asyncio.Queue = asyncio.Queue()

        async def _llama_stream_producer() -> None:
            # read=None mencegah httpx ReadTimeout saat CPU 2-core mengevaluasi prompt panjang
            llama_timeout = httpx.Timeout(connect=12.0, write=30.0, read=None, pool=10.0)
            try:
                async with httpx.AsyncClient(timeout=llama_timeout) as client:
                    async with client.stream("POST", target_url, headers=req_headers, json=payload) as resp:
                        if resp.status_code != 200:
                            err_body = await resp.aread()
                            err_msg = err_body.decode("utf-8", errors="replace")[:350]
                            await token_queue.put(("error", f"[{provider_label}] HTTP {resp.status_code}: {err_msg}"))
                            return

                        async for line in resp.aiter_lines():
                            if not line or not line.startswith("data: "):
                                continue
                            raw_data = line[6:].strip()
                            if raw_data == "[DONE]":
                                break
                            try:
                                parsed = json.loads(raw_data)
                                token, stream_err = extract_stream_token(ptype, parsed)
                                if stream_err:
                                    await token_queue.put(("error", f"[{provider_label}] {stream_err}"))
                                    return
                                if token:
                                    await token_queue.put(("token", token))
                            except json.JSONDecodeError:
                                continue
                await token_queue.put(("eof", None))
            except asyncio.CancelledError:
                raise
            except httpx.RequestError as exc:
                await token_queue.put(("error", f"Gagal terhubung ke {provider_label} ({target_url}): {exc}"))
            except Exception as exc:
                await token_queue.put(("error", f"Kesalahan internal stream ({provider_label}): {exc}"))

        producer_task = asyncio.create_task(_llama_stream_producer())
        start_ts = time.monotonic()
        first_token_seen = False

        try:
            while True:
                if request is not None and await request.is_disconnected():
                    producer_task.cancel()
                    break
                try:
                    kind, val = await asyncio.wait_for(token_queue.get(), timeout=2.0)
                except asyncio.TimeoutError:
                    elapsed = int(time.monotonic() - start_ts)
                    if not first_token_seen:
                        yield (
                            f"data: {json.dumps({'status': 'PROCESSING_PROMPT', 'elapsed_seconds': elapsed}, ensure_ascii=False)}\n\n"
                        )
                    else:
                        yield ": keepalive\n\n"
                    continue

                if kind == "token":
                    first_token_seen = True
                    collected_chunks.append(val)
                    yield (
                        f"data: {json.dumps({'status': 'STREAM', 'token': val}, ensure_ascii=False)}\n\n"
                    )
                elif kind == "error":
                    restore_status = prev_status if prev_status != "STREAMING" else "PENDING"
                    update_micro_beat(beat_id, {"status": restore_status})
                    yield (
                        f"data: {json.dumps({'status': 'ERROR', 'detail': val}, ensure_ascii=False)}\n\n"
                    )
                    return
                elif kind == "eof":
                    break
        finally:
            if not producer_task.done():
                producer_task.cancel()
                try:
                    await producer_task
                except (asyncio.CancelledError, Exception):
                    pass

        # Jika dibatalkan sebelum selesai dan belum ada hasil akhir
        if request is not None and await request.is_disconnected() and not collected_chunks:
            restore_status = prev_status if prev_status != "STREAMING" else "PENDING"
            update_micro_beat(beat_id, {"status": restore_status})
            return

        raw_prose = "".join(collected_chunks).strip()
        cleaned_prose, removed_moralizing = ContextAssembler.trim_moralizing_tail(
            raw_prose,
            custom_banned_phrases=project.get("banned_phrases"),
        )

        saved_beat = beat
        if options.save_on_complete and cleaned_prose:
            saved_beat = save_beat_prose_and_revision(
                beat_id=beat_id,
                prose_content=cleaned_prose,
                revision_note="SSE Streamed Literary Generation",
                sampler_snapshot=sampler,
                status="COMPLETED",
            )
        elif not cleaned_prose:
            restore_status = prev_status if prev_status != "STREAMING" else "PENDING"
            update_micro_beat(beat_id, {"status": restore_status})

        yield (
            f"data: {json.dumps({'status': 'DONE', 'beat_id': beat_id, 'actual_words': count_words(cleaned_prose), 'trimmed_moralizing_sentences': removed_moralizing, 'final_prose': cleaned_prose, 'beat': saved_beat}, ensure_ascii=False)}\n\n"
        )


@app.post("/api/beats/{beat_id}/stream")
async def api_stream_beat_post(
    beat_id: str,
    request: Request,
    options: Optional[StreamBeatCustomOptions] = None,
) -> StreamingResponse:
    opts = options or StreamBeatCustomOptions()
    return StreamingResponse(
        _stream_beat_sse_generator(beat_id=beat_id, options=opts, request=request),
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/beats/{beat_id}/stream")
async def api_stream_beat_get(
    beat_id: str,
    request: Request,
    endpoint_mode: str = Query(default="chat", pattern="^(chat|completion)$"),
    temperature: float = Query(default=1.02, ge=0.1, le=2.0),
    min_p: float = Query(default=0.07, ge=0.0, le=1.0),
    dry_multiplier: float = Query(default=0.8, ge=0.0, le=5.0),
    xtc_probability: float = Query(default=0.1, ge=0.0, le=1.0),
) -> StreamingResponse:
    opts = StreamBeatCustomOptions(
        endpoint_mode=endpoint_mode,
        temperature=temperature,
        min_p=min_p,
        dry_multiplier=dry_multiplier,
        xtc_probability=xtc_probability,
    )
    return StreamingResponse(
        _stream_beat_sse_generator(beat_id=beat_id, options=opts, request=request),
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/stream-beat")
async def api_stream_beat_direct(req: DirectWriteBeatRequest, request: Request) -> StreamingResponse:
    """Endpoint kompatibilitas langsung sesuai Bagian 9 Blueprint."""
    if req.beat_id:
        return await api_stream_beat_post(req.beat_id, request, StreamBeatCustomOptions())

    async def direct_generator() -> AsyncGenerator[str, None]:
        if inference_queue.is_busy:
            yield f"data: {json.dumps({'status': 'QUEUED', 'detail': 'Menunggu giliran memori AI...'})}\n\n"

        async with inference_queue.acquire_slot("direct-stream-beat"):
            yield f"data: {json.dumps({'status': 'STARTED'})}\n\n"
            sampler = ContextAssembler.get_literary_sampler_params(
                target_words=req.target_words,
                min_p=0.07,
                dry_multiplier=0.8,
                xtc_probability=0.1,
                id_slot=0,
            )
            provider_cfg = load_provider_config(LLAMA_SERVER_BASE_URL)
            ptype = str(provider_cfg.get("provider_type") or "local_llama").lower()
            target_url, req_headers, payload = build_chat_request(
                provider_cfg=provider_cfg,
                system_prompt=req.static_system_prompt,
                user_prompt=req.dynamic_user_prompt,
                max_tokens=sampler["max_tokens"],
                temperature=sampler["temperature"],
                stream=True,
                llama_sampler=sampler,
                endpoint_mode="chat",
            )
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(connect=12.0, write=30.0, read=None, pool=10.0)) as client:
                    async with client.stream("POST", target_url, headers=req_headers, json=payload) as resp:
                        if resp.status_code != 200:
                            err_txt = (await resp.aread()).decode("utf-8", errors="replace")[:300]
                            yield f"data: {json.dumps({'status': 'ERROR', 'detail': f'HTTP {resp.status_code}: {err_txt}'})}\n\n"
                            return
                        async for line in resp.aiter_lines():
                            if not line or not line.startswith("data: "):
                                continue
                            raw = line[6:].strip()
                            if raw == "[DONE]":
                                yield f"data: {json.dumps({'status': 'DONE'})}\n\n"
                                break
                            try:
                                data = json.loads(raw)
                                token, stream_err = extract_stream_token(ptype, data)
                                if stream_err:
                                    yield f"data: {json.dumps({'status': 'ERROR', 'detail': stream_err})}\n\n"
                                    return
                                if token:
                                    yield f"data: {json.dumps({'status': 'STREAM', 'token': token})}\n\n"
                            except Exception:
                                continue
                        else:
                            yield f"data: {json.dumps({'status': 'DONE'})}\n\n"
            except httpx.RequestError as exc:
                yield f"data: {json.dumps({'status': 'ERROR', 'detail': str(exc)})}\n\n"

    return StreamingResponse(
        direct_generator(),
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================================
# ENDPOINT 4-TIER MEMORY INSPECTOR & POST-BEAT STATE EXTRACTOR
# ============================================================================

@app.get("/api/beats/{beat_id}/memory-context")
def api_inspect_beat_memory_context(beat_id: str) -> Dict[str, Any]:
    """
    Mengembalikan rakitan lengkap 4-Tier Memory beserta telemetri pencarian FTS5 BM25 (<1ms)
    untuk satu Micro-Beat sebelum atau sesudah streaming.
    """
    try:
        assembled = FourTierMemoryAssembler.assemble_four_tier_prompt(beat_id=beat_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return {
        "beat_id": beat_id,
        "beat_number": assembled["beat"]["beat_number"],
        "fts5_telemetry": assembled["fts5_telemetry"],
        "tiers_breakdown": assembled["tiers_breakdown"],
        "static_system_prompt": assembled["static_system_prompt"],
        "dynamic_user_prompt": assembled["dynamic_user_prompt"],
        "full_4tier_prompt": assembled["full_4tier_prompt"],
    }


@app.post("/api/beats/{beat_id}/extract-state")
async def api_extract_post_beat_state(
    beat_id: str,
    mode: str = Query(default="auto", pattern="^(auto|fast_local)$"),
) -> Dict[str, Any]:
    """
    Post-Beat State Extractor Endpoint:
    Setelah streaming narasi beat selesai, mengekstrak:
    1. Ringkasan faktual 2 kalimat (extracted_summary di tabel micro_beats).
    2. Kata kunci FTS5 BM25 & memori episodik (episodic_memory_fts).
    3. Perubahan kondisi karakter (current_state: location, condition, emotional_state, inventory, knowledge)
       di tabel codex_items (yang otomatis menyinkronkan indeks codex_fts lewat Trigger SQLite).
    4. Pembaruan chapter_summary dan rolling_global_summary di tabel chapters & projects.

    - mode="auto"       : Menggunakan llama-server (dengan fallback heuristik lokal jika offline).
    - mode="fast_local" : Ekstraktor deterministik <1ms tanpa memanggil llama-server (menjaga KV Cache Slot 0 tetap utuh).
    """
    beat = get_micro_beat(beat_id)
    if not beat:
        raise HTTPException(status_code=404, detail=f"Micro-Beat {beat_id} tidak ditemukan.")

    if not (beat.get("generated_prose") or "").strip():
        raise HTTPException(
            status_code=400,
            detail="Micro-Beat ini belum memiliki teks prosa (generated_prose kosong).",
        )

    if mode == "fast_local":
        try:
            return await PostBeatStateExtractor.extract_and_persist_state(
                beat_id=beat_id,
                mode="fast_local",
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    async with inference_queue.acquire_slot(f"state-extractor:{beat_id}"):
        try:
            result = await PostBeatStateExtractor.extract_and_persist_state(
                beat_id=beat_id,
                llama_chat_url=LLAMA_CHAT_COMPLETIONS_URL,
                llama_completion_url=LLAMA_RAW_COMPLETION_URL,
                mode=mode,
                provider_cfg=load_provider_config(LLAMA_SERVER_BASE_URL),
            )
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e


FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        workers=1,
        reload=False,
    )
