import json
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

try:
    import httpx  # type: ignore
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore

BACKEND_DIR = Path(__file__).resolve().parent
CONFIG_FILE_PATH = Path(
    os.environ.get("NOVEL_AI_CONFIG_PATH", str(BACKEND_DIR / ".ai_provider_config.json"))
)


PROVIDER_PRESETS: List[Dict[str, Any]] = [
    {
        "preset_id": "openrouter",
        "label": "OpenRouter (Banyak Model & Gratis Tier)",
        "provider_type": "openai_compatible",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openrouter/free",
        "suggested_models": [
            "openrouter/free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "google/gemma-3-27b-it:free",
            "qwen/qwen3-32b:free",
            "deepseek/deepseek-chat-v3-0324:free",
            "deepseek/deepseek-chat",
            "openai/gpt-4o-mini",
        ],
        "requires_api_key": True,
        "notes": "Satu API key untuk banyak model AI sekaligus (otomatis memilih model gratis/aktif terbaik dari akun OpenRouter Anda).",
    },
    {
        "preset_id": "gemini",
        "label": "Google Gemini (AI Studio API)",
        "provider_type": "openai_compatible",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_model": "gemini-2.5-flash",
        "suggested_models": [
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-2.5-pro",
            "gemini-1.5-flash",
        ],
        "requires_api_key": True,
        "notes": "Endpoint resmi Google AI Studio. Cukup tempel API Key Gemini — model Flash aktif otomatis dipilih.",
    },
    {
        "preset_id": "groq",
        "label": "Groq Cloud (Inferensi Super Kilat)",
        "provider_type": "openai_compatible",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "suggested_models": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "qwen-qwq-32b",
            "gemma2-9b-it",
        ],
        "requires_api_key": True,
        "notes": "Kecepatan ratusan token/detik via LPU; tersedia tier gratis dari console.groq.com.",
    },
    {
        "preset_id": "openai",
        "label": "OpenAI (ChatGPT API)",
        "provider_type": "openai_compatible",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "suggested_models": [
            "gpt-4o-mini",
            "gpt-4.1-mini",
            "gpt-4o",
            "gpt-4.1",
        ],
        "requires_api_key": True,
        "notes": "API resmi OpenAI. Cukup tempel API Key — model aktif di akun Anda dipilih otomatis.",
    },
    {
        "preset_id": "deepseek",
        "label": "DeepSeek API",
        "provider_type": "openai_compatible",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "suggested_models": [
            "deepseek-chat",
            "deepseek-reasoner",
        ],
        "requires_api_key": True,
        "notes": "Kualitas penulisan fiksi & dialog sangat tinggi dengan biaya API ekonomis.",
    },
    {
        "preset_id": "mistral",
        "label": "Mistral AI (La Plateforme)",
        "provider_type": "openai_compatible",
        "base_url": "https://api.mistral.ai/v1",
        "default_model": "mistral-small-latest",
        "suggested_models": [
            "mistral-small-latest",
            "mistral-large-latest",
            "open-mistral-nemo",
        ],
        "requires_api_key": True,
        "notes": "Prosa ekspresif gaya Eropa; bagus untuk fiksi sastra & fantasi.",
    },
    {
        "preset_id": "anthropic",
        "label": "Anthropic Claude (Messages API)",
        "provider_type": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-sonnet-4-20250514",
        "suggested_models": [
            "claude-sonnet-4-20250514",
            "claude-3-7-sonnet-latest",
            "claude-3-5-haiku-latest",
            "claude-3-5-sonnet-latest",
        ],
        "requires_api_key": True,
        "notes": "Kualitas sastra & dialog Claude. Cukup tempel API Key Anthropic Anda.",
    },
    {
        "preset_id": "ollama",
        "label": "Ollama (Lokal / Server Wi-Fi LAN)",
        "provider_type": "openai_compatible",
        "base_url": "http://127.0.0.1:11434/v1",
        "default_model": "qwen2.5:7b",
        "suggested_models": [
            "qwen2.5:7b",
            "qwen3:4b",
            "gemma2:9b",
            "mistral-nemo:12b",
        ],
        "requires_api_key": False,
        "notes": "Hubungkan ke instance Ollama di komputer ini atau PC lain yang punya GPU di jaringan rumah.",
    },
    {
        "preset_id": "custom_openai",
        "label": "LM Studio / KoboldCpp / vLLM / Custom URL",
        "provider_type": "openai_compatible",
        "base_url": "http://127.0.0.1:1234/v1",
        "default_model": "local-model",
        "suggested_models": [],
        "requires_api_key": False,
        "notes": "Sumber kompatibel OpenAI apa saja (LM Studio, KoboldCpp, TabbyAPI, vLLM, HuggingFace Router, dll.).",
    },
]

_PRESET_MAP: Dict[str, Dict[str, Any]] = {p["preset_id"]: p for p in PROVIDER_PRESETS}


def mask_api_key(key: str) -> str:
    clean = (key or "").strip()
    if not clean:
        return ""
    if len(clean) <= 10:
        return "*" * len(clean)
    return f"{clean[:4]}...{clean[-4:]}"


def normalize_base_url(raw_url: str, default_url: str = "https://api.openai.com/v1") -> str:
    cleaned = (raw_url or "").strip().rstrip("/")
    if not cleaned:
        cleaned = default_url.rstrip("/")
    parsed = urlparse(cleaned)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Base URL harus diawali http:// atau https:// dan memiliki host yang valid.")
    return cleaned


def build_openai_chat_url(base_url: str) -> str:
    cleaned = normalize_base_url(base_url)
    if cleaned.endswith("/chat/completions"):
        return cleaned
    parsed = urlparse(cleaned)
    if not parsed.path or parsed.path == "/":
        return f"{cleaned}/v1/chat/completions"
    return f"{cleaned}/chat/completions"


def build_openai_models_url(base_url: str) -> str:
    cleaned = normalize_base_url(base_url)
    if cleaned.endswith("/chat/completions"):
        cleaned = cleaned[: -len("/chat/completions")]
    parsed = urlparse(cleaned)
    if not parsed.path or parsed.path == "/":
        return f"{cleaned}/v1/models"
    return f"{cleaned}/models"


def build_anthropic_messages_url(base_url: str) -> str:
    cleaned = normalize_base_url(base_url, "https://api.anthropic.com/v1")
    if cleaned.endswith("/messages"):
        return cleaned
    parsed = urlparse(cleaned)
    if not parsed.path or parsed.path == "/":
        return f"{cleaned}/v1/messages"
    return f"{cleaned}/messages"


def default_provider_config(local_llama_url: str = "http://127.0.0.1:8080") -> Dict[str, Any]:
    return {
        "provider_type": "local_llama",  # 'local_llama' | 'openai_compatible' | 'anthropic'
        "preset_id": "local_llama",
        "display_name": "Lokal llama-server (GGUF)",
        "base_url": local_llama_url.rstrip("/"),
        "model_name": "",
        "api_key": "",
        "extra_headers": {},
        "timeout_seconds": 180,
    }


def load_provider_config(local_llama_url: str = "http://127.0.0.1:8080") -> Dict[str, Any]:
    cfg = default_provider_config(local_llama_url=local_llama_url)
    cfg_path = Path(os.environ.get("NOVEL_AI_CONFIG_PATH", str(CONFIG_FILE_PATH)))
    if cfg_path.is_file():
        try:
            loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cfg.update(loaded)
        except Exception:
            pass

    # Override opsional dari environment variables jika disetel
    env_ptype = os.environ.get("NOVEL_AI_PROVIDER", "").strip().lower()
    if env_ptype in ("local_llama", "openai_compatible", "anthropic"):
        cfg["provider_type"] = env_ptype
    if os.environ.get("NOVEL_AI_BASE_URL", "").strip():
        cfg["base_url"] = os.environ["NOVEL_AI_BASE_URL"].strip().rstrip("/")
    if os.environ.get("NOVEL_AI_MODEL", "").strip():
        cfg["model_name"] = os.environ["NOVEL_AI_MODEL"].strip()
    if os.environ.get("NOVEL_AI_API_KEY", "").strip():
        cfg["api_key"] = os.environ["NOVEL_AI_API_KEY"].strip()

    if cfg.get("provider_type") == "local_llama":
        cfg["base_url"] = local_llama_url.rstrip("/")

    return cfg


def save_provider_config(
    updates: Dict[str, Any],
    local_llama_url: str = "http://127.0.0.1:8080",
) -> Dict[str, Any]:
    current = load_provider_config(local_llama_url=local_llama_url)
    ptype = str(updates.get("provider_type") or current["provider_type"]).strip().lower()
    if ptype not in ("local_llama", "openai_compatible", "anthropic"):
        raise ValueError("provider_type harus salah satu dari: local_llama, openai_compatible, anthropic.")

    preset_id = str(updates.get("preset_id") or (ptype if ptype == "local_llama" else current.get("preset_id") or "custom_openai")).strip()
    preset_meta = _PRESET_MAP.get(preset_id, {})

    if ptype == "local_llama":
        base_url = local_llama_url.rstrip("/")
        model_name = ""
        display_name = "Lokal llama-server (GGUF)"
    else:
        raw_url = str(updates.get("base_url") or preset_meta.get("base_url") or current.get("base_url") or "").strip()
        base_url = normalize_base_url(raw_url)
        raw_model = str(updates.get("model_name") if updates.get("model_name") is not None else "").strip()
        if raw_model.lower() == "auto":
            raw_model = ""
        # Bila user tidak memilih model secara manual, gunakan default preset (atau model lama jika preset/URL sama)
        if raw_model:
            model_name = raw_model
        elif preset_id == current.get("preset_id") and base_url == str(current.get("base_url") or "").rstrip("/") and current.get("model_name"):
            model_name = str(current["model_name"])
        else:
            model_name = str(preset_meta.get("default_model") or "").strip() or "auto"
        display_name = str(
            updates.get("display_name")
            or preset_meta.get("label")
            or model_name
        ).strip()

    clear_key = bool(updates.get("clear_api_key", False))
    same_provider_target = (
        ptype != "local_llama"
        and preset_id == current.get("preset_id")
        and normalize_base_url(str(updates.get("base_url") or preset_meta.get("base_url") or current.get("base_url") or "")) == str(current.get("base_url") or "").rstrip("/")
    )
    if clear_key:
        api_key = ""
    elif "api_key" in updates and updates["api_key"] is not None and str(updates["api_key"]).strip():
        api_key = str(updates["api_key"]).strip()
    elif same_provider_target:
        api_key = str(current.get("api_key") or "")
    else:
        api_key = ""

    if ptype != "local_llama" and preset_meta.get("requires_api_key") and not api_key:
        raise ValueError(f"API Key wajib diisi untuk {display_name}.")

    timeout_sec = max(15, min(600, int(updates.get("timeout_seconds") or current.get("timeout_seconds") or 180)))
    extra_headers = updates.get("extra_headers") if isinstance(updates.get("extra_headers"), dict) else current.get("extra_headers") or {}

    new_cfg = {
        "provider_type": ptype,
        "preset_id": preset_id,
        "display_name": display_name,
        "base_url": base_url,
        "model_name": model_name,
        "api_key": api_key,
        "extra_headers": extra_headers,
        "timeout_seconds": timeout_sec,
    }

    cfg_path = Path(os.environ.get("NOVEL_AI_CONFIG_PATH", str(CONFIG_FILE_PATH)))
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = cfg_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(new_cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_path, cfg_path)
    if os.name == "posix":
        try:
            os.chmod(cfg_path, 0o600)
        except OSError:
            pass
    return new_cfg


def get_public_provider_summary(local_llama_url: str = "http://127.0.0.1:8080") -> Dict[str, Any]:
    cfg = load_provider_config(local_llama_url=local_llama_url)
    api_key = str(cfg.get("api_key") or "")
    return {
        "provider_type": cfg["provider_type"],
        "preset_id": cfg.get("preset_id") or cfg["provider_type"],
        "display_name": cfg.get("display_name") or cfg["provider_type"],
        "base_url": cfg.get("base_url") or "",
        "model_name": cfg.get("model_name") or "",
        "has_api_key": bool(api_key),
        "api_key_masked": mask_api_key(api_key),
        "timeout_seconds": int(cfg.get("timeout_seconds") or 180),
        "presets": PROVIDER_PRESETS,
    }


def build_chat_request(
    provider_cfg: Dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 800,
    temperature: float = 0.75,
    stream: bool = True,
    llama_sampler: Optional[Dict[str, Any]] = None,
    endpoint_mode: str = "chat",
) -> Tuple[str, Dict[str, str], Dict[str, Any]]:
    """
    Merakit (url, headers, payload) secara akurat sesuai protokol provider aktif:
    - local_llama      -> full sampler C++ llama.cpp + /v1/chat/completions atau /completion
    - openai_compatible -> JSON standar OpenAI (aman untuk OpenAI, Gemini, OpenRouter, Groq, DeepSeek, Ollama, LM Studio)
    - anthropic        -> Messages API resmi Anthropic (top-level `system`, `x-api-key`)
    """
    ptype = str(provider_cfg.get("provider_type") or "local_llama").lower()
    api_key = str(provider_cfg.get("api_key") or "").strip()
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    extra_hdr = provider_cfg.get("extra_headers") or {}
    if isinstance(extra_hdr, dict):
        for hk, hv in extra_hdr.items():
            if hk and hv:
                headers[str(hk)] = str(hv)

    if ptype == "anthropic":
        url = build_anthropic_messages_url(provider_cfg.get("base_url", "https://api.anthropic.com/v1"))
        if api_key:
            headers["x-api-key"] = api_key
        headers.setdefault("anthropic-version", "2023-06-01")
        payload: Dict[str, Any] = {
            "model": provider_cfg.get("model_name") or "claude-3-5-sonnet-latest",
            "max_tokens": int(max_tokens),
            "temperature": max(0.0, min(1.0, float(temperature))),
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "stream": bool(stream),
        }
        return url, headers, payload

    if ptype == "openai_compatible":
        base_url = provider_cfg.get("base_url") or "https://api.openai.com/v1"
        url = build_openai_chat_url(base_url)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if "openrouter.ai" in base_url.lower():
            headers.setdefault("HTTP-Referer", "http://localhost:8000")
            headers.setdefault("X-Title", "The Zen Literary Studio")
        payload = {
            "model": provider_cfg.get("model_name") or "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": int(max_tokens),
            "temperature": max(0.0, min(2.0, float(temperature))),
            "stream": bool(stream),
        }
        return url, headers, payload

    # Default: local_llama (llama.cpp native)
    base_url = str(provider_cfg.get("base_url") or "http://127.0.0.1:8080").rstrip("/")
    sampler_clean = dict(llama_sampler or {})
    sampler_clean.setdefault("max_tokens", int(max_tokens))
    sampler_clean.setdefault("temperature", float(temperature))

    if endpoint_mode == "completion":
        url = f"{base_url}/completion"
        payload = {
            "prompt": f"{system_prompt}\n\n{user_prompt}\n",
            "stream": bool(stream),
            "n_predict": int(sampler_clean.get("max_tokens", max_tokens)),
            **sampler_clean,
        }
    else:
        url = f"{base_url}/v1/chat/completions"
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": bool(stream),
            **sampler_clean,
        }
    return url, headers, payload


def extract_stream_token(provider_type: str, parsed: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """
    Mengembalikan `(token_text, error_message_if_any)` dari satu event JSON SSE.
    Mendukung OpenAI delta, llama.cpp completion text, dan Anthropic content_block_delta.
    """
    if isinstance(parsed.get("error"), dict):
        err_msg = parsed["error"].get("message") or json.dumps(parsed["error"], ensure_ascii=False)
        return "", str(err_msg)
    if isinstance(parsed.get("error"), str) and parsed["error"]:
        return "", parsed["error"]

    if provider_type == "anthropic":
        evt_type = parsed.get("type")
        if evt_type == "content_block_delta":
            delta = parsed.get("delta") or {}
            if delta.get("type") == "text_delta":
                return str(delta.get("text") or ""), None
        return "", None

    if "choices" in parsed and parsed["choices"]:
        choice0 = parsed["choices"][0]
        delta = choice0.get("delta") or {}
        if isinstance(delta, dict) and delta.get("content"):
            return str(delta["content"]), None
        if choice0.get("text"):
            return str(choice0["text"]), None
        msg = choice0.get("message") or {}
        if isinstance(msg, dict) and msg.get("content"):
            return str(msg["content"]), None

    if "content" in parsed and parsed["content"]:
        return str(parsed["content"]), None

    return "", None


def extract_nonstream_text(provider_type: str, body: Dict[str, Any]) -> str:
    if provider_type == "anthropic":
        blocks = body.get("content") or []
        if isinstance(blocks, list):
            return "".join(
                str(b.get("text") or "")
                for b in blocks
                if isinstance(b, dict) and b.get("type") == "text"
            )
        return ""

    if "choices" in body and body["choices"]:
        c0 = body["choices"][0]
        msg = c0.get("message") or {}
        if isinstance(msg, dict) and msg.get("content"):
            return str(msg["content"])
        if c0.get("text"):
            return str(c0["text"])

    if body.get("content"):
        return str(body["content"])

    return ""


async def fetch_remote_models(
    base_url: str,
    provider_type: str = "openai_compatible",
    api_key: str = "",
) -> List[str]:
    if httpx is None:
        raise RuntimeError("httpx belum terinstal.")

    ptype = (provider_type or "openai_compatible").lower()
    headers: Dict[str, str] = {}
    if ptype == "anthropic":
        url = build_anthropic_messages_url(base_url).replace("/messages", "/models")
        if api_key.strip():
            headers["x-api-key"] = api_key.strip()
        headers["anthropic-version"] = "2023-06-01"
    else:
        url = build_openai_models_url(base_url)
        if api_key.strip():
            headers["Authorization"] = f"Bearer {api_key.strip()}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            if ptype == "anthropic" and resp.status_code in (404, 405):
                return list(_PRESET_MAP.get("anthropic", {}).get("suggested_models") or [])
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:250]}")
        data = resp.json()

    raw_list = data.get("data") if isinstance(data, dict) else data
    if not isinstance(raw_list, list):
        return []
    models = sorted(
        {
            str(m.get("id") or m.get("name") or "").strip().removeprefix("models/")
            for m in raw_list
            if isinstance(m, dict) and (m.get("id") or m.get("name"))
        }
    )
    return models[:250]


def _is_usable_text_model(model_id: str) -> bool:
    low = (model_id or "").lower()
    blocked_tokens = ("whisper", "tts", "embed", "dall-e", "moderation", "guard", "transcribe", "realtime", "imagen", "veo")
    return bool(low) and not any(tok in low for tok in blocked_tokens)


async def _pick_and_probe_candidates(
    cfg: Dict[str, Any],
    explicit_model: str = "",
) -> Tuple[str, Dict[str, Any]]:
    """
    Jika user tidak memilih model secara manual, otomatis menemukan dan memverifikasi model
    yang aktif di akun/server provider (`fetch_remote_models` + prioritas preset).
    """
    ptype = str(cfg.get("provider_type") or "openai_compatible").lower()
    preset_meta = _PRESET_MAP.get(str(cfg.get("preset_id") or ""), {})
    base_url = str(cfg.get("base_url") or preset_meta.get("base_url") or "")
    api_key = str(cfg.get("api_key") or "")

    candidates: List[str] = []
    if explicit_model and explicit_model.lower() != "auto":
        candidates.append(explicit_model)
    else:
        live_models: List[str] = []
        try:
            live_models = [m for m in await fetch_remote_models(base_url, ptype, api_key) if _is_usable_text_model(m)]
        except RuntimeError as exc:
            # Jika gagal karena Auth (401/403) atau koneksi putus, gagalkan langsung tanpa muter
            err_l = str(exc).lower()
            if "http 401" in err_l or "http 403" in err_l:
                raise RuntimeError(f"API Key ditolak oleh server: {exc}") from exc
            live_models = []
        except Exception:
            live_models = []

        live_set = set(live_models)
        suggested = list(preset_meta.get("suggested_models") or [])
        if preset_meta.get("default_model") and preset_meta["default_model"] not in suggested:
            suggested.insert(0, str(preset_meta["default_model"]))

        # 1. Prioritaskan model rekomendasi yang benar-benar ada di akun /models
        if live_models:
            for sm in suggested:
                if sm in live_set and sm not in candidates:
                    candidates.append(sm)
            # Untuk OpenRouter: prioritaskan model `:free` yang tersedia
            for lm in live_models:
                if ":free" in lm.lower() and lm not in candidates:
                    candidates.append(lm)
            # Lalu model chat umum terbaik (flash/mini/chat/instruct/sonnet/llama)
            for lm in live_models:
                if any(k in lm.lower() for k in ("flash", "chat", "sonnet", "mini", "instruct", "llama", "qwen", "gemini", "mistral")):
                    if lm not in candidates:
                        candidates.append(lm)
            for lm in live_models:
                if lm not in candidates:
                    candidates.append(lm)
        else:
            # Fallback bila server tidak menyediakan endpoint /models
            for sm in suggested:
                if sm not in candidates:
                    candidates.append(sm)

    if not candidates:
        raise RuntimeError(
            "Tidak ada model aktif ditemukan di server tersebut. Pastikan server sudah memuat model atau masukkan ID model di Opsi Lanjutan."
        )

    last_err = ""
    for cand in candidates[:4]:
        probe_cfg = dict(cfg, model_name=cand)
        url, headers, payload = build_chat_request(
            provider_cfg=probe_cfg,
            system_prompt="Balas singkat untuk uji koneksi.",
            user_prompt="Balas tepat dengan: OK",
            max_tokens=16,
            temperature=0.1,
            stream=False,
        )
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except Exception as exc:
            raise RuntimeError(f"Gagal menghubungi {url}: {exc}") from exc

        latency = round((time.monotonic() - t0) * 1000, 1)
        if resp.status_code == 200:
            text = extract_nonstream_text(ptype, resp.json()).strip()
            return cand, {
                "ok": True,
                "provider_type": ptype,
                "model_name": cand,
                "latency_ms": latency,
                "sample_reply": text[:80] or "OK",
                "detail": f"Terhubung ke {cand} ({latency} ms)",
            }

        err_txt = resp.text[:300]
        last_err = f"HTTP {resp.status_code}: {err_txt}"
        # Gagal cepat jika API Key salah / dilarang — tidak perlu mencoba model lain
        if resp.status_code in (401, 403):
            raise RuntimeError(f"API Key tidak valid atau ditolak ({last_err})")

    raise RuntimeError(f"Semua kandidat model gagal dihubungi ({last_err})")


async def test_provider_connection(
    test_cfg: Optional[Dict[str, Any]] = None,
    local_llama_url: str = "http://127.0.0.1:8080",
) -> Dict[str, Any]:
    if httpx is None:
        raise RuntimeError("httpx belum terinstal.")

    current = load_provider_config(local_llama_url=local_llama_url)
    cfg = dict(current)
    explicit_model = ""
    if isinstance(test_cfg, dict):
        for k in ("provider_type", "preset_id", "base_url", "timeout_seconds"):
            if test_cfg.get(k) is not None and str(test_cfg.get(k)).strip() != "":
                cfg[k] = test_cfg[k]
        explicit_model = str(test_cfg.get("model_name") or "").strip()
        if explicit_model.lower() == "auto":
            explicit_model = ""
        preset_meta = _PRESET_MAP.get(str(cfg.get("preset_id") or ""), {})
        same_target = (
            str(cfg.get("preset_id") or "") == str(current.get("preset_id") or "")
            and str(cfg.get("base_url") or preset_meta.get("base_url") or "").rstrip("/") == str(current.get("base_url") or "").rstrip("/")
        )
        if test_cfg.get("clear_api_key"):
            cfg["api_key"] = ""
        elif test_cfg.get("api_key") is not None and str(test_cfg.get("api_key")).strip():
            cfg["api_key"] = str(test_cfg["api_key"]).strip()
        elif not same_target:
            cfg["api_key"] = ""
    else:
        explicit_model = str(cfg.get("model_name") or "").strip()

    ptype = str(cfg.get("provider_type") or "local_llama").lower()
    t0 = time.monotonic()

    if ptype == "local_llama":
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{local_llama_url.rstrip('/')}/health")
            latency = round((time.monotonic() - t0) * 1000, 1)
            if r.status_code == 200:
                return {
                    "ok": True,
                    "provider_type": ptype,
                    "latency_ms": latency,
                    "detail": f"llama-server lokal aktif di {local_llama_url}",
                }
            raise RuntimeError(f"llama-server mengembalikan HTTP {r.status_code}")

    preset_meta = _PRESET_MAP.get(str(cfg.get("preset_id") or ""), {})
    if preset_meta.get("requires_api_key") and not str(cfg.get("api_key") or "").strip():
        raise RuntimeError(f"API Key wajib diisi untuk {preset_meta.get('label') or ptype}.")

    _, probe_res = await _pick_and_probe_candidates(cfg, explicit_model=explicit_model)
    return probe_res


async def resolve_and_activate_provider(
    updates: Dict[str, Any],
    verify_connection: bool = True,
    local_llama_url: str = "http://127.0.0.1:8080",
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Memvalidasi, memilih model aktif terbaik secara otomatis bila `model_name` kosong/auto,
    menguji koneksi sebelum menyimpan, lalu mengaktifkan provider baru tanpa mematikan
    engine lama bila koneksi gagal.
    """
    ptype = str(updates.get("provider_type") or "local_llama").strip().lower()
    if ptype == "local_llama":
        saved = save_provider_config(updates, local_llama_url=local_llama_url)
        return saved, None

    current = load_provider_config(local_llama_url=local_llama_url)
    preset_id = str(updates.get("preset_id") or "custom_openai").strip()
    preset_meta = _PRESET_MAP.get(preset_id, {})
    base_url = normalize_base_url(str(updates.get("base_url") or preset_meta.get("base_url") or ""))
    display_name = str(updates.get("display_name") or preset_meta.get("label") or base_url).strip()

    same_target = (
        preset_id == current.get("preset_id")
        and base_url == str(current.get("base_url") or "").rstrip("/")
    )
    if updates.get("clear_api_key"):
        api_key = ""
    elif updates.get("api_key") is not None and str(updates["api_key"]).strip():
        api_key = str(updates["api_key"]).strip()
    elif same_target:
        api_key = str(current.get("api_key") or "")
    else:
        api_key = ""

    if preset_meta.get("requires_api_key") and not api_key:
        raise ValueError(f"API Key wajib diisi untuk {display_name}.")

    explicit_model = str(updates.get("model_name") or "").strip()
    if explicit_model.lower() == "auto":
        explicit_model = ""

    probe_result: Optional[Dict[str, Any]] = None
    chosen_model = explicit_model
    if verify_connection:
        probe_cfg = {
            "provider_type": ptype,
            "preset_id": preset_id,
            "display_name": display_name,
            "base_url": base_url,
            "api_key": api_key,
            "model_name": explicit_model,
        }
        chosen_model, probe_result = await _pick_and_probe_candidates(
            probe_cfg, explicit_model=explicit_model
        )

    final_updates = dict(updates)
    if chosen_model:
        final_updates["model_name"] = chosen_model
    saved = save_provider_config(final_updates, local_llama_url=local_llama_url)
    return saved, probe_result
