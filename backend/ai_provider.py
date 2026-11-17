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
        "default_model": "deepseek/deepseek-chat-v3-0324:free",
        "suggested_models": [
            "deepseek/deepseek-chat-v3-0324:free",
            "qwen/qwen-2.5-72b-instruct",
            "google/gemini-2.0-flash-001",
            "anthropic/claude-3.5-sonnet",
            "mistralai/mistral-large-2411",
        ],
        "requires_api_key": True,
        "notes": "Satu API key untuk akses DeepSeek, Qwen 72B, Claude, Gemini, & berbagai model gratis (:free).",
    },
    {
        "preset_id": "gemini",
        "label": "Google Gemini (AI Studio API)",
        "provider_type": "openai_compatible",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_model": "gemini-2.5-flash",
        "suggested_models": [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
        ],
        "requires_api_key": True,
        "notes": "Endpoint OpenAI-compatible resmi Google AI Studio. Cepat, konteks panjang, dan dukung Bahasa Indonesia sangat baik.",
    },
    {
        "preset_id": "groq",
        "label": "Groq Cloud (Inferensi Super Kilat)",
        "provider_type": "openai_compatible",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "suggested_models": [
            "llama-3.3-70b-versatile",
            "qwen-qwq-32b",
            "gemma2-9b-it",
        ],
        "requires_api_key": True,
        "notes": "Kecepatan ratusan token/detik via LPU; tersedia tier gratis dari console.groq.com.",
    },
    {
        "preset_id": "openai",
        "label": "OpenAI (GPT-4o / GPT-4.1)",
        "provider_type": "openai_compatible",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "suggested_models": [
            "gpt-4o-mini",
            "gpt-4.1-mini",
            "gpt-4.1",
            "gpt-4o",
        ],
        "requires_api_key": True,
        "notes": "API resmi OpenAI atau proxy mana pun yang memakai protokol OpenAI v1.",
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
        "notes": "Kualitas penulisan fiksi, dialog, dan penalaran plot sangat tinggi dengan biaya API ekonomis.",
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
        ],
        "requires_api_key": True,
        "notes": "Prosa ekspresif gaya Eropa; bagus untuk fiksi sastra & fantasi.",
    },
    {
        "preset_id": "anthropic",
        "label": "Anthropic Claude (Messages API)",
        "provider_type": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-3-5-sonnet-latest",
        "suggested_models": [
            "claude-3-7-sonnet-latest",
            "claude-3-5-sonnet-latest",
            "claude-3-5-haiku-latest",
        ],
        "requires_api_key": True,
        "notes": "Standar emas nuansa sastra dan subteks dialog (menggunakan protokol resmi Anthropic Messages API).",
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
        model_name = str(updates.get("model_name") if updates.get("model_name") is not None else current.get("model_name") or "").strip()
        if not model_name:
            raise ValueError("Nama Model (model_name) wajib diisi untuk provider AI eksternal/online.")
        display_name = str(
            updates.get("display_name")
            or preset_meta.get("label")
            or model_name
        ).strip()

    clear_key = bool(updates.get("clear_api_key", False))
    if clear_key:
        api_key = ""
    elif "api_key" in updates and updates["api_key"] is not None and str(updates["api_key"]).strip():
        api_key = str(updates["api_key"]).strip()
    else:
        api_key = str(current.get("api_key") or "")

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
    if ptype == "anthropic":
        preset = _PRESET_MAP.get("anthropic", {})
        return list(preset.get("suggested_models") or ["claude-3-7-sonnet-latest", "claude-3-5-sonnet-latest"])

    url = build_openai_models_url(base_url)
    headers: Dict[str, str] = {}
    if api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:250]}")
        data = resp.json()

    raw_list = data.get("data") if isinstance(data, dict) else data
    if not isinstance(raw_list, list):
        return []
    models = sorted(
        {
            str(m.get("id") or m.get("name") or "").strip()
            for m in raw_list
            if isinstance(m, dict) and (m.get("id") or m.get("name"))
        }
    )
    return models[:250]


async def test_provider_connection(
    test_cfg: Optional[Dict[str, Any]] = None,
    local_llama_url: str = "http://127.0.0.1:8080",
) -> Dict[str, Any]:
    if httpx is None:
        raise RuntimeError("httpx belum terinstal.")

    cfg = dict(load_provider_config(local_llama_url=local_llama_url))
    if isinstance(test_cfg, dict):
        for k in ("provider_type", "preset_id", "base_url", "model_name", "timeout_seconds"):
            if test_cfg.get(k) is not None and str(test_cfg.get(k)).strip() != "":
                cfg[k] = test_cfg[k]
        if test_cfg.get("clear_api_key"):
            cfg["api_key"] = ""
        elif test_cfg.get("api_key") is not None and str(test_cfg.get("api_key")).strip():
            cfg["api_key"] = str(test_cfg["api_key"]).strip()

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

    url, headers, payload = build_chat_request(
        provider_cfg=cfg,
        system_prompt="Balas singkat untuk uji koneksi.",
        user_prompt="Balas tepat dengan: OK",
        max_tokens=16,
        temperature=0.1,
        stream=False,
    )
    async with httpx.AsyncClient(timeout=25.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        latency = round((time.monotonic() - t0) * 1000, 1)
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:350]}")
        text = extract_nonstream_text(ptype, resp.json()).strip()
        return {
            "ok": True,
            "provider_type": ptype,
            "model_name": cfg.get("model_name"),
            "latency_ms": latency,
            "sample_reply": text[:80] or "OK",
            "detail": f"Koneksi berhasil ke {cfg.get('model_name')} ({latency} ms)",
        }
