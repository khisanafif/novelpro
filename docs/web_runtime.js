/**
 * The Zen Literary Studio — Pure-Browser Serverless Runtime (GitHub Pages Edition)
 * -----------------------------------------------------------------------------
 * Memungkinkan seluruh Studio Novel berjalan 100% langsung di browser statis
 * (GitHub Pages / Static Hosting) tanpa server Python/FastAPI:
 *  - Persistensi lengkap di browser localStorage (kompatibel 1:1 dgn Backup JSON)
 *  - Pemanggilan API AI langsung dari browser (OpenRouter, Gemini, Groq, OpenAI,
 *    Mistral, Anthropic Claude CORS, Ollama / LM Studio LAN) + SSE Streaming
 *  - Deterministic Pacing Engine, 4-Tier Context Assembler, Anti-Summary Trimmer
 *  - Ekspor EPUB 3.0 ZIP murni di browser, Markdown (.md), Cetak HTML/PDF, & Backup JSON
 */
(function (global) {
    "use strict";

    const DB_STORAGE_KEY = "zen_web_studio_db_v1";
    const PROVIDER_STORAGE_KEY = "zen_web_ai_provider_v1";

    const DEFAULT_BANNED_PHRASES = [
        "tanpa mereka sadari",
        "waktu seakan berhenti",
        "menghela napas berat",
        "baru saja dimulai",
        "sebuah simfoni",
        "entah mengapa",
        "takdir berkata lain",
        "hanya waktu yang bisa menjawab",
    ];

    const PROVIDER_PRESETS = [
        {
            preset_id: "gemini",
            label: "Google Gemini (AI Studio)",
            provider_type: "openai_compatible",
            base_url: "https://generativelanguage.googleapis.com/v1beta/openai",
            default_model: "",
            suggested_models: [
                "gemini-3.8-flash",
                "gemini-3.5-flash-lite",
                "gemini-3-flash",
                "gemini-3.1-pro-preview",
                "gemini-4-hydrogen",
            ],
            requires_api_key: true,
            notes: "Tempel API Key Gemini (AIza...) — otomatis mendeteksi model aktif terbaru langsung dari server Google.",
        },
        {
            preset_id: "openrouter",
            label: "OpenRouter (Banyak Model & Gratis Tier)",
            provider_type: "openai_compatible",
            base_url: "https://openrouter.ai/api/v1",
            default_model: "openrouter/free",
            suggested_models: [
                "openrouter/free",
                "meta-llama/llama-3.3-70b-instruct:free",
                "google/gemma-3-27b-it:free",
                "qwen/qwen3-32b:free",
                "openai/gpt-4o-mini",
            ],
            requires_api_key: true,
            notes: "Deteksi otomatis via awalan sk-or- — memilih model gratis/aktif terbaik dari akun OpenRouter Anda.",
        },
        {
            preset_id: "groq",
            label: "Groq Cloud (Inferensi Super Kilat)",
            provider_type: "openai_compatible",
            base_url: "https://api.groq.com/openai/v1",
            default_model: "",
            suggested_models: [
                "llama-3.3-70b-versatile",
                "llama-3.1-8b-instant",
                "qwen-qwq-32b",
                "gemma2-9b-it",
            ],
            requires_api_key: true,
            notes: "Deteksi otomatis via awalan gsk_ — inferensi ratusan token/detik di browser.",
        },
        {
            preset_id: "openai",
            label: "OpenAI (ChatGPT API)",
            provider_type: "openai_compatible",
            base_url: "https://api.openai.com/v1",
            default_model: "",
            suggested_models: ["gpt-4.1-mini", "gpt-4o-mini", "gpt-4.1", "gpt-4o"],
            requires_api_key: true,
            notes: "Deteksi otomatis untuk API Key OpenAI — memilih model aktif di akun Anda.",
        },
        {
            preset_id: "deepseek",
            label: "DeepSeek API",
            provider_type: "openai_compatible",
            base_url: "https://api.deepseek.com/v1",
            default_model: "",
            suggested_models: ["deepseek-chat", "deepseek-reasoner"],
            requires_api_key: true,
            notes: "Kualitas penulisan fiksi tinggi. Catatan: jika browser memblokir CORS DeepSeek, gunakan OpenRouter atau Studio lokal.",
        },
        {
            preset_id: "mistral",
            label: "Mistral AI (La Plateforme)",
            provider_type: "openai_compatible",
            base_url: "https://api.mistral.ai/v1",
            default_model: "",
            suggested_models: ["mistral-small-latest", "mistral-large-latest", "open-mistral-nemo"],
            requires_api_key: true,
            notes: "Mendukung akses browser langsung; prosa ekspresif untuk fiksi sastra & fantasi.",
        },
        {
            preset_id: "anthropic",
            label: "Anthropic Claude (Messages API)",
            provider_type: "anthropic",
            base_url: "https://api.anthropic.com/v1",
            default_model: "",
            suggested_models: [
                "claude-sonnet-4-20250514",
                "claude-3-7-sonnet-latest",
            ],
            requires_api_key: true,
            notes: "Deteksi otomatis via awalan sk-ant- (mengirim header direct-browser-access dari web).",
        },
        {
            preset_id: "xai",
            label: "xAI (Grok API)",
            provider_type: "openai_compatible",
            base_url: "https://api.x.ai/v1",
            default_model: "",
            suggested_models: ["grok-3-mini", "grok-3"],
            requires_api_key: true,
            notes: "Deteksi otomatis via awalan xai- untuk endpoint xAI Grok.",
        },
        {
            preset_id: "huggingface_router",
            label: "HuggingFace Inference Router",
            provider_type: "openai_compatible",
            base_url: "https://router.huggingface.co/v1",
            default_model: "",
            suggested_models: [],
            requires_api_key: true,
            notes: "Deteksi otomatis token hf_ menggunakan HuggingFace Inference Router.",
        },
        {
            preset_id: "ollama",
            label: "Ollama (Lokal / Server Wi-Fi LAN)",
            provider_type: "openai_compatible",
            base_url: "http://127.0.0.1:11434/v1",
            default_model: "",
            suggested_models: ["qwen3:4b", "qwen2.5:7b", "gemma3:4b"],
            requires_api_key: false,
            notes: "Untuk akses Ollama dari GitHub Pages HTTPS, jalankan Ollama dengan env OLLAMA_ORIGINS=*.",
        },
        {
            preset_id: "custom_openai",
            label: "LM Studio / KoboldCpp / vLLM / Custom URL",
            provider_type: "openai_compatible",
            base_url: "http://127.0.0.1:1234/v1",
            default_model: "",
            suggested_models: [],
            requires_api_key: false,
            notes: "Endpoint OpenAI-compatible apa saja yang mengizinkan CORS browser.",
        },
    ];

    const PRESET_MAP = Object.fromEntries(PROVIDER_PRESETS.map((p) => [p.preset_id, p]));
    const GENERIC_KEY_PROBE_ORDER = ["openrouter", "gemini", "groq", "openai", "mistral", "anthropic", "deepseek", "xai"];

    function classifyApiKeyProviders(apiKey) {
        const key = String(apiKey || "").trim();
        if (!key) return { candidates: ["ollama", "custom_openai"], highConf: false };
        if (key.startsWith("AIza")) return { candidates: ["gemini"], highConf: true };
        if (key.startsWith("sk-or-")) return { candidates: ["openrouter"], highConf: true };
        if (key.startsWith("sk-ant-")) return { candidates: ["anthropic"], highConf: true };
        if (key.startsWith("gsk_")) return { candidates: ["groq"], highConf: true };
        if (key.startsWith("xai-")) return { candidates: ["xai"], highConf: true };
        if (key.startsWith("sk-proj-") || key.startsWith("sk-svcacct-")) return { candidates: ["openai"], highConf: true };
        if (key.startsWith("hf_")) return { candidates: ["huggingface_router"], highConf: true };
        if (key.startsWith("sk-")) return { candidates: ["openai", "openrouter", "deepseek"], highConf: false };
        return { candidates: [...GENERIC_KEY_PROBE_ORDER], highConf: false };
    }

    function nowIso() {
        return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
    }

    function uuid() {
        if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
            return crypto.randomUUID();
        }
        return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
            const r = (Math.random() * 16) | 0;
            const v = c === "x" ? r : (r & 0x3) | 0x8;
            return v.toString(16);
        });
    }

    function countWords(text) {
        if (!text || !String(text).trim()) return 0;
        return String(text).trim().split(/\s+/).length;
    }

    function maskApiKey(key) {
        const clean = String(key || "").trim();
        if (!clean) return "";
        if (clean.length <= 8) return `${clean.slice(0, 2)}****`;
        return `${clean.slice(0, 4)}...${clean.slice(-4)}`;
    }

    function normalizeBaseUrl(rawUrl) {
        let u = String(rawUrl || "").trim();
        if (!u) throw new Error("Base URL API tidak boleh kosong.");
        if (!/^https?:\/\//i.test(u)) {
            throw new Error("Base URL harus diawali http:// atau https://.");
        }
        u = u.replace(/\/+$/, "");
        if (u.endsWith("/chat/completions")) u = u.slice(0, -"/chat/completions".length).replace(/\/+$/, "");
        if (u.endsWith("/messages")) u = u.slice(0, -"/messages".length).replace(/\/+$/, "");
        if (u.endsWith("/models")) u = u.slice(0, -"/models".length).replace(/\/+$/, "");
        return u;
    }

    function buildDefaultProviderConfig() {
        return {
            provider_type: "local_llama",
            preset_id: "local_llama",
            display_name: "Belum Terhubung (Masukkan API Key)",
            base_url: "",
            model_name: "",
            api_key: "",
            extra_headers: {},
            timeout_seconds: 180,
        };
    }

    function loadProviderConfig() {
        const base = buildDefaultProviderConfig();
        try {
            const raw = localStorage.getItem(PROVIDER_STORAGE_KEY);
            if (!raw) return base;
            const saved = JSON.parse(raw);
            if (saved && typeof saved === "object") {
                return { ...base, ...saved };
            }
        } catch (_) {
            // Abaikan JSON rusak
        }
        return base;
    }

    function saveProviderConfigRaw(cfg) {
        localStorage.setItem(PROVIDER_STORAGE_KEY, JSON.stringify(cfg));
    }

    function getPublicProviderSummary() {
        const cfg = loadProviderConfig();
        const apiKey = String(cfg.api_key || "").trim();
        const isWebReady = cfg.provider_type !== "local_llama" && Boolean(cfg.base_url);
        return {
            provider_type: isWebReady ? cfg.provider_type : "local_llama",
            preset_id: isWebReady ? (cfg.preset_id || "custom_openai") : "local_llama",
            display_name: isWebReady
                ? (cfg.display_name || cfg.model_name || cfg.base_url)
                : "Browser Mode (Belum Ada API Aktif)",
            base_url: cfg.base_url || "",
            model_name: cfg.model_name || "",
            has_api_key: Boolean(apiKey),
            api_key_masked: maskApiKey(apiKey),
            timeout_seconds: Number(cfg.timeout_seconds) || 180,
            presets: PROVIDER_PRESETS,
        };
    }

    function _buildOpenAiUrl(baseUrl, suffix) {
        const clean = normalizeBaseUrl(baseUrl);
        return `${clean}${suffix}`;
    }

    function _buildAnthropicUrl(baseUrl, suffix) {
        let clean = normalizeBaseUrl(baseUrl);
        if (clean.endsWith("/v1")) return `${clean}${suffix}`;
        return `${clean}/v1${suffix}`;
    }

    function buildChatRequest(cfg, systemPrompt, userPrompt, maxTokens = 800, temperature = 0.75, stream = true) {
        const ptype = String(cfg.provider_type || "").toLowerCase();
        const apiKey = String(cfg.api_key || "").trim();
        const headers = { "Content-Type": "application/json" };

        if (ptype === "anthropic") {
            const url = _buildAnthropicUrl(cfg.base_url || "https://api.anthropic.com/v1", "/messages");
            if (apiKey) headers["x-api-key"] = apiKey;
            headers["anthropic-version"] = "2023-06-01";
            headers["anthropic-dangerous-direct-browser-access"] = "true";
            return {
                url,
                headers,
                payload: {
                    model: cfg.model_name || "claude-sonnet-4-20250514",
                    max_tokens: Number(maxTokens) || 800,
                    temperature: Math.max(0.0, Math.min(1.0, Number(temperature) || 0.75)),
                    system: systemPrompt,
                    messages: [{ role: "user", content: userPrompt }],
                    stream: Boolean(stream),
                },
            };
        }

        const baseUrl = cfg.base_url || "https://api.openai.com/v1";
        const url = _buildOpenAiUrl(baseUrl, "/chat/completions");
        if (apiKey) headers["Authorization"] = `Bearer ${apiKey}`;
        if (baseUrl.toLowerCase().includes("openrouter.ai")) {
            headers["HTTP-Referer"] = global.location ? global.location.origin : "https://github.io";
            headers["X-Title"] = "The Zen Literary Studio";
        }
        return {
            url,
            headers,
            payload: {
                model: cfg.model_name || "gpt-4o-mini",
                messages: [
                    { role: "system", content: systemPrompt },
                    { role: "user", content: userPrompt },
                ],
                max_tokens: Number(maxTokens) || 800,
                temperature: Math.max(0.0, Math.min(2.0, Number(temperature) || 0.75)),
                stream: Boolean(stream),
            },
        };
    }

    function extractStreamToken(providerType, parsed) {
        if (parsed && parsed.error) {
            const msg = typeof parsed.error === "object" ? parsed.error.message || JSON.stringify(parsed.error) : parsed.error;
            return { token: "", error: String(msg) };
        }
        if (providerType === "anthropic") {
            if (parsed && parsed.type === "content_block_delta" && parsed.delta && parsed.delta.type === "text_delta") {
                return { token: String(parsed.delta.text || ""), error: null };
            }
            return { token: "", error: null };
        }
        if (parsed && Array.isArray(parsed.choices) && parsed.choices.length > 0) {
            const c0 = parsed.choices[0];
            if (c0.delta && c0.delta.content) return { token: String(c0.delta.content), error: null };
            if (c0.text) return { token: String(c0.text), error: null };
            if (c0.message && c0.message.content) return { token: String(c0.message.content), error: null };
        }
        if (parsed && parsed.content) return { token: String(parsed.content), error: null };
        return { token: "", error: null };
    }

    function extractNonStreamText(providerType, body) {
        if (!body || typeof body !== "object") return "";
        if (providerType === "anthropic") {
            if (Array.isArray(body.content)) {
                return body.content
                    .filter((b) => b && b.type === "text")
                    .map((b) => String(b.text || ""))
                    .join("");
            }
            return "";
        }
        if (Array.isArray(body.choices) && body.choices.length > 0) {
            const c0 = body.choices[0];
            if (c0.message && c0.message.content) return String(c0.message.content);
            if (c0.text) return String(c0.text);
        }
        if (body.content) return String(body.content);
        return "";
    }

    function wrapFetchError(err, baseUrl) {
        const msg = String(err && err.message ? err.message : err);
        if (err && (err.name === "TypeError" || msg.toLowerCase().includes("failed to fetch") || msg.toLowerCase().includes("network"))) {
            return new Error(
                `Gagal terhubung ke ${baseUrl || "server API"} dari browser (kemungkinan terblokir CORS atau koneksi internet). Gunakan OpenRouter, Google Gemini, Groq, OpenAI, Mistral, atau Anthropic Claude untuk akses langsung di GitHub Pages.`
            );
        }
        return err instanceof Error ? err : new Error(msg);
    }

    function isUsableTextModel(modelId) {
        const low = String(modelId || "").toLowerCase();
        if (!low) return false;
        const skip = [
            "embedding", "embed-", "whisper", "tts", "dall-e", "imagen",
            "moderation", "guard", "realtime", "transcribe", "audio", "sora", "veo",
            "aqa", "robotics", "computer-use", "-image", "image-generation", "nano-banana",
        ];
        return !skip.some((k) => low.includes(k));
    }

    function extractVersionTuple(modelId) {
        const low = String(modelId || "").toLowerCase();
        const re = /(?:^|[-_/])(\d{1,2})(?:\.(\d{1,2}))?(?:\.(\d{1,2}))?(?=$|[-_:/a-z])/g;
        let best = [0, 0, 0];
        let m;
        while ((m = re.exec(low)) !== null) {
            const maj = Number(m[1]);
            if (maj > 20) continue;
            const ver = [maj, Number(m[2] || 0), Number(m[3] || 0)];
            if (
                ver[0] > best[0] ||
                (ver[0] === best[0] && ver[1] > best[1]) ||
                (ver[0] === best[0] && ver[1] === best[1] && ver[2] > best[2])
            ) {
                best = ver;
            }
        }
        return best;
    }

    function rankModelsForWriting(models, presetId = "") {
        const scoreOf = (mid) => {
            const low = mid.toLowerCase();
            let s = 0;
            if (low === "openrouter/free") s += 500;
            if (presetId === "openrouter" && low.endsWith(":free")) s += 200;
            if (presetId === "gemini" && low.startsWith("gemini-")) s += 120;
            if (["flash", "hydrogen", "chat", "sonnet", "mini", "versatile", "small"].some((t) => low.includes(t))) s += 50;
            if (low.includes("pro") || low.includes("argon") || low.includes("large")) s += 25;
            if (low.includes("-latest")) s += 20;
            if (["deep-research", "thinking", "exp", "experimental", "vision"].some((t) => low.includes(t))) s -= 40;
            if (low.includes("live")) s -= 60;
            if (low.startsWith("gemma-") && presetId === "gemini") s -= 30;
            return s;
        };
        return [...models].sort((a, b) => {
            const sa = scoreOf(a);
            const sb = scoreOf(b);
            if (sb !== sa) return sb - sa;
            const va = extractVersionTuple(a);
            const vb = extractVersionTuple(b);
            for (let i = 0; i < 3; i++) {
                if (vb[i] !== va[i]) return vb[i] - va[i];
            }
            return a.length - b.length;
        });
    }

    async function fetchRemoteModels(providerType, baseUrl, apiKey) {
        const cleanUrl = normalizeBaseUrl(baseUrl);
        const key = String(apiKey || "").trim();
        const ptype = String(providerType || "openai_compatible").toLowerCase();

        // Google Gemini native /v1beta/models -> filter ketat `supportedGenerationMethods` berisi `generateContent`
        if (cleanUrl.toLowerCase().includes("generativelanguage.googleapis.com")) {
            const qUrl = `https://generativelanguage.googleapis.com/v1beta/models?pageSize=200${key ? `&key=${encodeURIComponent(key)}` : ""}`;
            try {
                const nr = await fetch(qUrl);
                if (nr.status === 200) {
                    const nd = await nr.json();
                    const arr = Array.isArray(nd.models) ? nd.models : [];
                    const gcModels = [];
                    for (const item of arr) {
                        const methods = Array.isArray(item.supportedGenerationMethods) ? item.supportedGenerationMethods : [];
                        if (!methods.includes("generateContent")) continue;
                        let mid = String(item.name || item.id || "").trim();
                        if (mid.startsWith("models/")) mid = mid.slice("models/".length);
                        if (mid && !gcModels.includes(mid)) gcModels.push(mid);
                    }
                    if (gcModels.length) return gcModels;
                } else if (nr.status === 400 || nr.status === 401 || nr.status === 403) {
                    const errTxt = (await nr.text()).slice(0, 220);
                    if (errTxt.toLowerCase().includes("api_key_invalid") || errTxt.toLowerCase().includes("api key not valid") || nr.status === 401 || nr.status === 403) {
                        throw new Error(`HTTP 401: ${errTxt}`);
                    }
                }
            } catch (e) {
                if (String(e.message || "").includes("HTTP 401")) throw e;
                // Fallback ke /openai/models bila perlu
            }
        }

        if (ptype === "anthropic") {
            const modelsUrl = _buildAnthropicUrl(cleanUrl, "/models");
            const headers = {
                "anthropic-version": "2023-06-01",
                "anthropic-dangerous-direct-browser-access": "true",
            };
            if (key) headers["x-api-key"] = key;
            let resp;
            try {
                resp = await fetch(modelsUrl, { headers });
            } catch (e) {
                throw wrapFetchError(e, cleanUrl);
            }
            if (resp.status === 404 || resp.status === 405) {
                return [...(PRESET_MAP.anthropic ? PRESET_MAP.anthropic.suggested_models : [])];
            }
            if (!resp.ok) {
                const txt = await resp.text();
                throw new Error(`HTTP ${resp.status}: ${txt.slice(0, 220)}`);
            }
            const data = await resp.json();
            const items = Array.isArray(data.data) ? data.data : [];
            const ids = items.map((x) => (x && typeof x === "object" ? x.id : x)).filter(Boolean).map(String);
            return ids.length ? ids : [...(PRESET_MAP.anthropic ? PRESET_MAP.anthropic.suggested_models : [])];
        }

        const url = _buildOpenAiUrl(cleanUrl, "/models");
        const headers = {};
        if (key) headers["Authorization"] = `Bearer ${key}`;
        let resp;
        try {
            resp = await fetch(url, { headers });
        } catch (e) {
            throw wrapFetchError(e, cleanUrl);
        }
        if (!resp.ok) {
            const txt = await resp.text();
            throw new Error(`HTTP ${resp.status}: ${txt.slice(0, 220)}`);
        }
        const data = await resp.json();
        const rawList = Array.isArray(data.data) ? data.data : Array.isArray(data.models) ? data.models : [];
        const out = [];
        for (const item of rawList) {
            let mid = item && typeof item === "object" ? (item.id || item.name) : item;
            if (!mid) continue;
            mid = String(mid);
            if (mid.startsWith("models/")) mid = mid.slice("models/".length);
            if (!out.includes(mid)) out.push(mid);
        }
        return out;
    }

    async function pickAndProbeCandidates(probeCfg, explicitModel = "") {
        const ptype = String(probeCfg.provider_type || "openai_compatible").toLowerCase();
        const presetId = String(probeCfg.preset_id || "");
        const presetMeta = PRESET_MAP[presetId] || {};
        const baseUrl = normalizeBaseUrl(probeCfg.base_url || presetMeta.base_url || "");
        const apiKey = String(probeCfg.api_key || "").trim();

        const candidates = [];
        if (explicitModel && explicitModel.toLowerCase() !== "auto") {
            candidates.push(explicitModel);
        } else {
            let liveModels = [];
            try {
                liveModels = (await fetchRemoteModels(ptype, baseUrl, apiKey)).filter(isUsableTextModel);
            } catch (e) {
                const emsg = String(e.message || "");
                if (emsg.includes("HTTP 401") || emsg.includes("HTTP 403")) {
                    throw new Error(`API Key ditolak oleh ${presetMeta.label || baseUrl} (${emsg}).`);
                }
                if (emsg.toLowerCase().includes("cors") || emsg.toLowerCase().includes("gagal terhubung")) {
                    throw e;
                }
            }

            if (liveModels.length) {
                const ranked = rankModelsForWriting(liveModels, presetId);
                if (presetId === "openrouter" && !ranked.includes("openrouter/free")) {
                    candidates.push("openrouter/free");
                }
                for (const m of ranked) {
                    if (!candidates.includes(m)) candidates.push(m);
                }
            } else {
                for (const s of presetMeta.suggested_models || []) {
                    if (!candidates.includes(s)) candidates.push(s);
                }
            }
            if (!candidates.length) {
                candidates.push(ptype === "anthropic" ? "claude-sonnet-4-20250514" : "gpt-4.1-mini");
            }
        }

        let lastErr = "Tidak ada kandidat model yang dapat merespons.";
        for (const candidate of candidates.slice(0, 8)) {
            const cfg = { ...probeCfg, base_url: baseUrl, model_name: candidate };
            const { url, headers, payload } = buildChatRequest(
                cfg,
                "Anda adalah asisten penguji koneksi singkat.",
                "Balas dengan satu kata: OK",
                16,
                0.1,
                false
            );
            const t0 = performance.now();
            let resp;
            try {
                resp = await fetch(url, {
                    method: "POST",
                    headers,
                    body: JSON.stringify(payload),
                });
            } catch (e) {
                throw wrapFetchError(e, baseUrl);
            }
            const latencyMs = Math.round(performance.now() - t0);

            if (resp.status === 200) {
                let txt = "";
                try {
                    const body = await resp.json();
                    txt = extractNonStreamText(ptype, body).trim();
                } catch (_) {
                    txt = "OK";
                }
                return {
                    chosenModel: candidate,
                    probeResult: {
                        ok: true,
                        latency_ms: latencyMs,
                        model_name: candidate,
                        provider_type: ptype,
                        preset_id: presetId,
                        sample_reply: (txt || "OK").slice(0, 80),
                        detail: `Terhubung ke ${presetMeta.label || ptype} • Model: ${candidate} (${latencyMs} ms)`,
                    },
                };
            }

            const errTxt = (await resp.text()).slice(0, 220);
            const lowErr = errTxt.toLowerCase();
            if (
                resp.status === 401 ||
                resp.status === 403 ||
                lowErr.includes("api_key_invalid") ||
                lowErr.includes("api key not valid")
            ) {
                throw new Error(`API Key ditolak oleh ${presetMeta.label || baseUrl} (HTTP ${resp.status}): ${errTxt}`);
            }
            lastErr = `Model '${candidate}' HTTP ${resp.status}: ${errTxt}`;
        }

        throw new Error(`Semua model di ${presetMeta.label || baseUrl} gagal diuji (${lastErr}).`);
    }

    async function autoDetectAndProbe(apiKey, explicitModel = "") {
        const cleanKey = String(apiKey || "").trim();
        if (!cleanKey) {
            for (const localPid of ["ollama", "custom_openai"]) {
                const meta = PRESET_MAP[localPid];
                const cfg = {
                    provider_type: meta.provider_type,
                    preset_id: localPid,
                    display_name: meta.label,
                    base_url: meta.base_url,
                    api_key: "",
                };
                try {
                    const res = await pickAndProbeCandidates(cfg, explicitModel);
                    return { detectedUpdates: { ...cfg, model_name: res.chosenModel }, probeResult: res.probeResult };
                } catch (_) {
                    // Coba berikutnya
                }
            }
            throw new Error(
                "Masukkan API Key AI Anda (Google Gemini, OpenRouter, Groq, OpenAI, Claude, Mistral, xAI), atau nyalakan Ollama/LM Studio dengan CORS aktif."
            );
        }

        const { candidates, highConf } = classifyApiKeyProviders(cleanKey);
        const errors = [];
        for (const pid of candidates) {
            const meta = PRESET_MAP[pid];
            if (!meta) continue;
            const cfg = {
                provider_type: meta.provider_type,
                preset_id: pid,
                display_name: meta.label,
                base_url: meta.base_url,
                api_key: cleanKey,
            };
            try {
                const res = await pickAndProbeCandidates(cfg, explicitModel);
                return { detectedUpdates: { ...cfg, model_name: res.chosenModel }, probeResult: res.probeResult };
            } catch (e) {
                errors.push(`${meta.label}: ${e.message}`);
                if (highConf) throw e;
            }
        }
        throw new Error(`API Key gagal pada semua provider yang diuji (${errors.slice(0, 3).join(" | ")})`);
    }

    async function resolveAndActivateProvider(updates, verifyConnection = true) {
        let ptype = String(updates.provider_type || "auto").trim().toLowerCase();
        if (ptype === "local_llama") {
            const next = buildDefaultProviderConfig();
            saveProviderConfigRaw(next);
            return { saved: next, probeResult: null };
        }

        const current = loadProviderConfig();
        let explicitModel = String(updates.model_name || "").trim();
        if (explicitModel.toLowerCase() === "auto") explicitModel = "";
        const rawBaseUrl = String(updates.base_url || "").trim();
        const rawApiKey = updates.clear_api_key ? "" : String(updates.api_key || "").trim();

        if (ptype === "auto" && !rawBaseUrl) {
            const effectiveKey = rawApiKey || (current.provider_type !== "local_llama" ? String(current.api_key || "") : "");
            const { detectedUpdates, probeResult } = await autoDetectAndProbe(effectiveKey, explicitModel);
            const nextCfg = {
                ...detectedUpdates,
                extra_headers: {},
                timeout_seconds: Number(updates.timeout_seconds) || 180,
            };
            saveProviderConfigRaw(nextCfg);
            return { saved: nextCfg, probeResult };
        }

        if (ptype === "auto" && rawBaseUrl) {
            ptype = rawBaseUrl.toLowerCase().includes("anthropic") ? "anthropic" : "openai_compatible";
        }

        const presetId = String(updates.preset_id || "custom_openai").trim();
        const presetMeta = PRESET_MAP[presetId] || {};
        const baseUrl = normalizeBaseUrl(rawBaseUrl || presetMeta.base_url || "");
        const displayName = String(updates.display_name || presetMeta.label || baseUrl).trim();

        const sameTarget = presetId === current.preset_id && baseUrl === String(current.base_url || "").replace(/\/+$/, "");
        let apiKey = "";
        if (updates.clear_api_key) {
            apiKey = "";
        } else if (rawApiKey) {
            apiKey = rawApiKey;
        } else if (sameTarget) {
            apiKey = String(current.api_key || "");
        }

        if (presetMeta.requires_api_key && !apiKey) {
            throw new Error(`API Key wajib diisi untuk ${displayName}.`);
        }

        let probeResult = null;
        let chosenModel = explicitModel;
        if (verifyConnection) {
            const res = await pickAndProbeCandidates(
                { provider_type: ptype, preset_id: presetId, display_name: displayName, base_url: baseUrl, api_key: apiKey },
                explicitModel
            );
            chosenModel = res.chosenModel;
            probeResult = res.probeResult;
        } else if (!chosenModel) {
            chosenModel = presetMeta.default_model || "auto";
        }

        const nextCfg = {
            provider_type: ptype,
            preset_id: presetId,
            display_name: displayName,
            base_url: baseUrl,
            model_name: chosenModel,
            api_key: apiKey,
            extra_headers: {},
            timeout_seconds: Number(updates.timeout_seconds) || 180,
        };
        saveProviderConfigRaw(nextCfg);
        return { saved: nextCfg, probeResult };
    }

    // =========================================================================
    // BROWSER DATABASE ENGINE (localStorage - Compatible Schema v1)
    // =========================================================================

    function loadDb() {
        const empty = {
            projects: [],
            story_phases: [],
            codex_items: [],
            chapters: [],
            micro_beats: [],
            beat_revisions: [],
        };
        try {
            const raw = localStorage.getItem(DB_STORAGE_KEY);
            if (!raw) return empty;
            const parsed = JSON.parse(raw);
            return {
                projects: Array.isArray(parsed.projects) ? parsed.projects : [],
                story_phases: Array.isArray(parsed.story_phases) ? parsed.story_phases : [],
                codex_items: Array.isArray(parsed.codex_items) ? parsed.codex_items : [],
                chapters: Array.isArray(parsed.chapters) ? parsed.chapters : [],
                micro_beats: Array.isArray(parsed.micro_beats) ? parsed.micro_beats : [],
                beat_revisions: Array.isArray(parsed.beat_revisions) ? parsed.beat_revisions : [],
            };
        } catch (_) {
            return empty;
        }
    }

    function saveDb(db) {
        localStorage.setItem(DB_STORAGE_KEY, JSON.stringify(db));
    }

    function buildDefaultPhases(totalChapters) {
        const c1End = Math.max(1, Math.round(totalChapters * 0.14));
        const c2End = Math.max(c1End + 1, Math.round(totalChapters * 0.40));
        const c3End = Math.max(c2End + 1, Math.round(totalChapters * 0.52));
        const c4End = Math.max(c3End + 1, Math.round(totalChapters * 0.80));
        const c5End = Math.max(c4End + 1, Math.round(totalChapters * 0.93));
        const c6End = Math.max(c5End + 1, totalChapters);

        return [
            {
                phase_name: "Fase I: Opening & Setup",
                start_chapter: 1,
                end_chapter: c1End,
                default_pacing: "SLOW_BURN",
                tension_min: 15,
                tension_max: 30,
                building_focus: "Pengenalan atmosfer dunia, rutinitas karakter POV, luka batin awal, dan pemicu insiden pertama.",
                phase_guardrails: "DILARANG memunculkan antagonis utama secara penuh atau menyelesaikan konflik besar. Fokus pada detail keseharian yang terganggu.",
            },
            {
                phase_name: "Fase II: Early Development",
                start_chapter: c1End + 1,
                end_chapter: c2End,
                default_pacing: "BALANCED",
                tension_min: 35,
                tension_max: 60,
                building_focus: "Eksplorasi aturan dunia lebih luas, dinamika relasi antar-karakter, sekutu/musuh awal, dan ujian pertama.",
                phase_guardrails: "Jaga agar rahasia inti dunia baru terbuka sebagian (maksimal 40%). Biarkan karakter membuat kesalahan taktis.",
            },
            {
                phase_name: "Fase III: Midpoint Twist",
                start_chapter: c2End + 1,
                end_chapter: c3End,
                default_pacing: "BALANCED",
                tension_min: 65,
                tension_max: 80,
                building_focus: "Pengungkapan fakta besar yang membalikkan asumsi protagonis (Point of No Return).",
                phase_guardrails: "Protagonis harus beralih dari reaktif menjadi proaktif. Konsekuensi kegagalan harus terasa permanen.",
            },
            {
                phase_name: "Fase IV: Crisis & Rising Stakes",
                start_chapter: c3End + 1,
                end_chapter: c4End,
                default_pacing: "BALANCED",
                tension_min: 75,
                tension_max: 90,
                building_focus: "Runtuhnya rencana lama, pengkhianatan atau kehilangan besar (All Hope Is Lost), dan tekanan psikologis ekstrem.",
                phase_guardrails: "DILARANG memberi jalan keluar instan (Deus Ex Machina). Setiap kemajuan kecil harus dibayar dengan pengorbanan.",
            },
            {
                phase_name: "Fase V: Climax",
                start_chapter: c4End + 1,
                end_chapter: c5End,
                default_pacing: "FAST_PACED",
                tension_min: 92,
                tension_max: 100,
                building_focus: "Benturan puncak antara protagonis dan konflik utama dengan pertaruhan tertinggi.",
                phase_guardrails: "DILARANG membuka subplot baru atau eksposisi sejarah panjang. Gunakan hanya aturan dunia dan alat yang sudah ditanam di bab sebelumnya.",
            },
            {
                phase_name: "Fase VI: Resolution / Ending",
                start_chapter: c5End + 1,
                end_chapter: c6End,
                default_pacing: "SLOW_BURN",
                tension_min: 15,
                tension_max: 30,
                building_focus: "Dampak emosional pasca-klimaks, perubahan batin protagonis, dan gema dunia yang baru.",
                phase_guardrails: "Hindari ceramah moral. Tutup cerita dengan citra sensorik konkret yang mencerminkan tema utama novel.",
            },
        ];
    }

    function enrichChapter(db, ch) {
        if (!ch) return null;
        const beats = db.micro_beats
            .filter((b) => b.chapter_id === ch.id)
            .sort((a, b) => a.beat_number - b.beat_number);
        const phase =
            db.story_phases.find(
                (p) =>
                    p.project_id === ch.project_id &&
                    ch.chapter_number >= p.start_chapter &&
                    ch.chapter_number <= p.end_chapter
            ) || null;
        const currentWords = beats.length
            ? beats.reduce((acc, b) => acc + countWords(b.generated_prose || ""), 0)
            : Number(ch.current_word_count || 0);
        return {
            ...ch,
            current_word_count: currentWords,
            phase_id: phase ? phase.id : ch.phase_id || null,
            phase_name: phase ? phase.phase_name : null,
            tension_min: phase ? phase.tension_min : 15,
            tension_max: phase ? phase.tension_max : 55,
            building_focus: phase ? phase.building_focus : "",
            phase_guardrails: phase ? phase.phase_guardrails : "",
        };
    }

    function recomputeChapterWordCount(db, chapterId) {
        const ch = db.chapters.find((c) => c.id === chapterId);
        if (!ch) return;
        const total = db.micro_beats
            .filter((b) => b.chapter_id === chapterId)
            .reduce((acc, b) => acc + countWords(b.generated_prose || ""), 0);
        ch.current_word_count = total;
        ch.updated_at = nowIso();
    }

    // =========================================================================
    // DETERMINISTIC PACING ENGINE & 4-TIER PROMPT ASSEMBLER
    // =========================================================================

    const PACING_RATIO_MAP = {
        SLOW_BURN: 3.0,
        BALANCED: 2.0,
        FAST_PACED: 1.0,
        FRENETIC_ACTION: 0.75,
    };

    function calculateChapterPlan(targetWords, pacingMode = "BALANCED", tMin = 15, tMax = 55) {
        const safeTarget = Math.max(350, Number(targetWords) || 3200);
        const mode = String(pacingMode || "BALANCED").toUpperCase();
        const totalBeats = Math.max(1, Math.round(safeTarget / 400));
        const wordsPerBeat = Math.max(250, Math.round(safeTarget / totalBeats));
        const ratio = PACING_RATIO_MAP[mode] || 2.0;
        const majorEvents = Math.max(1, Math.ceil(totalBeats / ratio));
        const safeMin = Math.max(5, Math.min(95, Number(tMin ?? 15)));
        const safeMax = Math.max(safeMin + 5, Math.min(100, Number(tMax ?? 55)));

        const tensionCurve = [];
        for (let i = 0; i < totalBeats; i++) {
            const progress = totalBeats === 1 ? 1.0 : i / (totalBeats - 1);
            const wave = Math.sin(progress * Math.PI * 1.5) * 5.0;
            let raw = safeMin + (safeMax - safeMin) * progress + wave;
            if (i === totalBeats - 1 && totalBeats > 1) raw = Math.max(raw, safeMax - 2);
            tensionCurve.push(Math.min(100, Math.max(5, Math.round(raw))));
        }

        return {
            total_micro_beats: totalBeats,
            total_beats: totalBeats,
            words_per_beat: wordsPerBeat,
            major_plot_events_needed: majorEvents,
            pacing_mode: mode,
            tension_min: safeMin,
            tension_max: safeMax,
            tension_curve: tensionCurve,
        };
    }

    function compileMixingDirectives(ch, tensionLevel = 45) {
        const wb = Number(ch.mix_world_building ?? 50);
        const psy = Number(ch.mix_psychology ?? 50);
        const sen = Number(ch.mix_sensory ?? 70);
        const dlg = Number(ch.mix_dialogue ?? 40);
        const act = Number(ch.mix_action ?? 30);
        const mode = String(ch.pacing_mode || "BALANCED").toUpperCase();

        const directives = [];
        directives.push(
            wb >= 65
                ? `World-Building ${wb}% (sisipkan detail ruang/budaya lewat objek fisik)`
                : wb <= 25
                  ? `World-Building ${wb}% (hindari eksposisi latar; fokus interaksi langsung)`
                  : `World-Building ${wb}% (latar secukupnya mendukung adegan)`
        );
        directives.push(
            psy >= 65
                ? `Psikologi ${psy}% (dalami keraguan, ingatan, & gejolak batin POV)`
                : psy <= 25
                  ? `Psikologi ${psy}% (minimalkan monolog; tunjukkan emosi lewat gestur)`
                  : `Psikologi ${psy}% (batin & aksi seimbang)`
        );
        directives.push(
            sen >= 65
                ? `Sensorik ${sen}% (wajib 3+ indra konkret: cahaya, suara, bau, suhu/tekstur)`
                : sen <= 25
                  ? `Sensorik ${sen}% (deskripsi indra ringkas)`
                  : `Sensorik ${sen}% (1-2 jangkar panca indra kuat)`
        );
        directives.push(
            dlg >= 65
                ? `Dialog ${dlg}% (dominan percakapan ber-subteks & jeda bahasa tubuh)`
                : dlg <= 30
                  ? `Dialog ${dlg}% (minim dialog, fokus narasi atmosferik & tindakan sunyi)`
                  : `Dialog ${dlg}% (dialog & narasi berimbang)`
        );
        directives.push(
            act >= 70 || tensionLevel >= 80 || mode === "FAST_PACED" || mode === "FRENETIC_ACTION"
                ? `Aksi ${act}%/Tension ${tensionLevel} (kalimat pendek tajam, urgensi cepat)`
                : `Aksi ${act}%/Tension ${tensionLevel} (ritme gerak alami)`
        );
        return directives.join("\n");
    }

    function buildDeterministicFallbackBeats(chapter, plan, codexItems) {
        const defaultChar = codexItems.find((c) => c.category === "CHARACTER");
        const defaultLoc = codexItems.find((c) => c.category === "LOCATION");
        const curve = plan.tension_curve || [];
        const total = plan.total_micro_beats || 6;
        const words = plan.words_per_beat || 400;
        const goal = String(chapter.chapter_goal || "Mendorong alur bab ke depan.").trim();
        const hookStyle = chapter.ending_hook_style || "CLIFFHANGER";
        const out = [];

        for (let idx = 0; idx < total; idx++) {
            const num = idx + 1;
            const tension = curve[idx] ?? 45;
            const isFirst = idx === 0;
            const isLast = idx === total - 1;
            let instr = "";
            let stop = "";
            let sensory = "Cahaya ruangan, suara latar sekitar, tekstur permukaan terdekat, suhu udara";
            let conflict = "Hambatan kecil yang memaksa karakter POV mengambil keputusan taktis.";

            if (isFirst) {
                instr = `Buka Bab ${chapter.chapter_number} secara imersif (${chapter.pacing_mode}): perkenalkan suasana ruang, kondisi fisik karakter POV, dan pemicu awal dari tujuan bab: "${goal.slice(0, 140)}".`;
                stop = "Berhenti tepat saat karakter menyadari petunjuk atau gangguan pertama yang mengubah ketenangannya.";
            } else if (isLast) {
                instr = `Bangun puncak ketegangan bab menuju akhir (${hookStyle}) berdasarkan peristiwa sebelumnya dan fokus tujuan bab: "${goal.slice(0, 140)}".`;
                stop = `Berhenti tepat pada kalimat aksi atau dialog tajam berjenis ${hookStyle} tanpa memberi rangkuman moral.`;
                conflict = "Konfrontasi atau temuan paling menentukan di penghujung bab.";
            } else {
                instr = `Lanjutkan eskalasi adegan ke-${num} dari ${total} menuju tujuan bab ("${goal.slice(0, 120)}"). Gunakan dialog ber-subteks atau langkah penyelidikan konkret (ketegangan ${tension}/100).`;
                stop = "Berhenti tepat pada reaksi fisik atau keputusan karakter menuju langkah berikutnya.";
            }

            out.push({
                beat_number: num,
                pov_character_id: defaultChar ? defaultChar.id : null,
                location_id: defaultLoc ? defaultLoc.id : null,
                tension_level: tension,
                target_words: words,
                sensory_anchor: sensory,
                conflict_focus: conflict,
                beat_instruction: instr,
                stopping_point: stop,
            });
        }
        return out;
    }

    function searchBm25Like(db, projectId, query, limit = 8) {
        const terms = String(query || "")
            .toLowerCase()
            .split(/[^a-z0-9\u00C0-\u024F]+/i)
            .map((s) => s.trim())
            .filter((s) => s.length >= 2);
        if (!terms.length) return { codex_matches: [], episodic_memories: [] };

        const scoreText = (haystack) => {
            const low = String(haystack || "").toLowerCase();
            if (!low) return 0;
            let s = 0;
            for (const t of terms) {
                if (low.includes(t)) s += 1 + Math.min(3, (low.match(new RegExp(t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "g")) || []).length * 0.35);
            }
            return s;
        };

        const codexMatches = db.codex_items
            .filter((c) => c.project_id === projectId)
            .map((c) => {
                const st = c.current_state || {};
                const blob = `${c.name} ${c.aliases_and_tags || ""} ${c.keywords_csv || ""} ${c.core_description || ""} ${JSON.stringify(st)}`;
                return { ...c, bm25_score: -scoreText(blob) };
            })
            .filter((c) => c.bm25_score < 0)
            .sort((a, b) => a.bm25_score - b.bm25_score)
            .slice(0, limit);

        const chMap = Object.fromEntries(db.chapters.filter((c) => c.project_id === projectId).map((c) => [c.id, c]));
        const episodic = db.micro_beats
            .filter((b) => chMap[b.chapter_id] && (b.extracted_summary || b.generated_prose))
            .map((b) => {
                const ch = chMap[b.chapter_id];
                const blob = `${b.extracted_summary || ""} ${b.beat_instruction || ""} ${(b.generated_prose || "").slice(0, 600)}`;
                const sc = scoreText(blob);
                return {
                    beat_id: b.id,
                    chapter_id: ch.id,
                    chapter_number: ch.chapter_number,
                    beat_number: b.beat_number,
                    summary_text: b.extracted_summary || (b.generated_prose || "").slice(0, 220),
                    bm25_score: -sc,
                };
            })
            .filter((x) => x.bm25_score < 0)
            .sort((a, b) => a.bm25_score - b.bm25_score)
            .slice(0, limit);

        return { codex_matches: codexMatches, episodic_memories: episodic };
    }

    function assembleBeatPrompts(db, beatId) {
        const t0 = performance.now();
        const beat = db.micro_beats.find((b) => b.id === beatId);
        if (!beat) throw new Error(`Micro-Beat ${beatId} tidak ditemukan.`);
        const rawChapter = db.chapters.find((c) => c.id === beat.chapter_id);
        if (!rawChapter) throw new Error("Bab induk tidak ditemukan.");
        const chapter = enrichChapter(db, rawChapter);
        const project = db.projects.find((p) => p.id === chapter.project_id);
        if (!project) throw new Error("Proyek novel tidak ditemukan.");

        const codex = db.codex_items.filter((c) => c.project_id === project.id);
        const pinnedRules = codex
            .filter((c) => c.is_pinned || c.category === "WORLD_RULE")
            .slice(0, 8)
            .map((c) => `- ${c.name}: ${c.core_description}`)
            .join("\n") || "(Belum ada aturan dunia pinned)";

        const banned = (Array.isArray(project.banned_phrases) && project.banned_phrases.length
            ? project.banned_phrases
            : DEFAULT_BANNED_PHRASES
        ).join(", ");

        const staticSystemPrompt = `Anda adalah THE LITERARY NOVELIST, novelis fiksi sastra profesional. Tulis adegan cerita dengan prosa yang hidup, panca indra konkret (Show, Don't Tell), dialog ber-subteks alami, dan hindari klise AI.

[IDENTITAS & KOMPAS NOVEL (TIER-1 STORY BIBLE)]
Judul: ${project.title} (${project.genre})
Logline: ${project.logline || "-"}
Tujuan Utama (North Star): ${project.main_objective}
Sudut Pandang & Tense: ${project.pov_style} | ${project.tense_style}
Tone & Gaya Bahasa: ${project.tone_style}
Contoh Ritme Kalimat Acuan:
"${project.style_sample || "-"}"

[ATURAN MUTLAK DUNIA & ENTITAS PINNED]
${pinnedRules}

[LARANGAN KERAS & ANTI-MORALIZING]
- DILARANG menggunakan frasa klise berikut: ${banned}
- DILARANG menutup adegan dengan kalimat kesimpulan moral atau rangkuman perasaan abstrak.
- WAJIB berhenti menulis tepat pada tindakan atau dialog di [TITIK BERHENTI BEAT].

[FASE STRUKTUR & BAB AKTIF]
Fase Saat Ini: ${chapter.phase_name || "Fase Bebas"} (Bab ${chapter.chapter_number}: "${chapter.title}")
Fokus Pembangunan Fase: ${chapter.building_focus || "-"}
Guardrails Fase: ${chapter.phase_guardrails || "-"}
Tujuan Bab: ${chapter.chapter_goal}

[TIER-2 MEMORI GLOBAL BERGULIR]
${project.rolling_global_summary || "(Cerita baru dimulai)"}`;

        const activeChar = codex.find((c) => c.id === beat.pov_character_id) || codex.find((c) => c.category === "CHARACTER");
        const activeLoc = codex.find((c) => c.id === beat.location_id) || codex.find((c) => c.category === "LOCATION");

        const query = `${beat.beat_instruction} ${beat.sensory_anchor} ${beat.conflict_focus} ${activeChar ? activeChar.name : ""} ${activeLoc ? activeLoc.name : ""}`;
        const retrieval = searchBm25Like(db, project.id, query, 5);

        const chapterBeats = db.micro_beats
            .filter((b) => b.chapter_id === chapter.id)
            .sort((a, b) => a.beat_number - b.beat_number);
        const prevBeats = chapterBeats.filter((b) => b.beat_number < beat.beat_number);
        const prevSummary = prevBeats
            .slice(-4)
            .map((b) => `- Beat ${b.beat_number}: ${b.extracted_summary || b.beat_instruction}`)
            .join("\n") || "(Ini adalah beat pembuka bab)";

        const allProseBefore = prevBeats.map((b) => String(b.generated_prose || "").trim()).filter(Boolean).join("\n\n");
        const verbatimTail = allProseBefore ? allProseBefore.slice(-1100) : "(Bab baru dimulai — bangun pembuka yang memikat)";
        const remainingWords = Math.max(0, Number(chapter.target_word_count || 3200) - Number(chapter.current_word_count || 0));

        const charDesc = activeChar
            ? `- ${activeChar.name} | Gaya Bicara: ${activeChar.speech_style || "-"} | State: ${JSON.stringify(activeChar.current_state || {})}`
            : "(Tidak ditentukan)";
        const locDesc = activeLoc
            ? `${activeLoc.name} — ${activeLoc.core_description}`
            : "(Lokasi adegan menyesuaikan instruksi)";
        const dynCodex = retrieval.codex_matches
            .slice(0, 4)
            .map((c) => `- [${c.category}] ${c.name}: ${c.core_description}`)
            .join("\n") || "-";
        const episodic = retrieval.episodic_memories
            .filter((e) => e.beat_id !== beat.id)
            .slice(0, 3)
            .map((e) => `- Bab ${e.chapter_number} Beat ${e.beat_number}: ${e.summary_text}`)
            .join("\n") || "-";

        const dynamicUserPrompt = `[TIER-3 KONTEKS ENTITAS & LOKASI]
Lokasi Aktif: ${locDesc}
Karakter POV & Kondisi Terkini:
${charDesc}
Referensi Codex Terkait:
${dynCodex}

[MEMORI EPISODIK TERKAIT]
${episodic}

[KONSOL PACING & NARRATIVE MIX - BEAT ${beat.beat_number} DARI ${chapterBeats.length || 1}]
- Mode Pacing: ${chapter.pacing_mode} | Ketegangan: ${beat.tension_level}/100
- Target Kata Beat Ini: ${beat.target_words} kata (Sisa Anggaran Bab: ${remainingWords} kata)
- Komposisi Narasi:
${compileMixingDirectives(chapter, beat.tension_level)}

[RINGKASAN BEAT SEBELUMNYA DI BAB INI]
${prevSummary}

[TIER-4 SAMBUNGAN TEKS TERAKHIR (VERBATIM CONTINUITY)]
...${verbatimTail}

[TUGAS PENULISAN BEAT ${beat.beat_number}]
Fokus Sensorik: ${beat.sensory_anchor || "-"}
Fokus Konflik Mikro: ${beat.conflict_focus || "-"}
Kejadian yang Harus Ditulis: ${beat.beat_instruction}
TITIK BERHENTI BEAT (Berhenti tepat di sini): ${beat.stopping_point}

Tuliskan langsung kelanjutan prosa naskah (~${beat.target_words} kata) tanpa judul bab, tanpa nomor beat, dan tanpa komentar pengantar:`;

        const elapsedMs = Number((performance.now() - t0).toFixed(2));
        return {
            beat,
            chapter,
            project,
            static_system_prompt: staticSystemPrompt,
            dynamic_user_prompt: dynamicUserPrompt,
            full_4tier_prompt: `${staticSystemPrompt}\n\n${dynamicUserPrompt}`,
            fts5_telemetry: {
                elapsed_ms: elapsedMs,
                codex_hits_count: retrieval.codex_matches.length,
                episodic_hits_count: retrieval.episodic_memories.length,
            },
            tiers_breakdown: {
                tier_1_story_bible_chars: staticSystemPrompt.length,
                tier_3_dynamic_codex_count: retrieval.codex_matches.length,
                tier_4_verbatim_tail_chars: verbatimTail.length,
            },
        };
    }

    function trimMoralizingTail(prose, bannedPhrases) {
        let text = String(prose || "").trim();
        const removed = [];
        if (!text) return { cleaned: "", removed };
        const extraCliches = [
            "baru saja dimulai",
            "hanya waktu yang bisa menjawab",
            "perjalanan mereka baru dimulai",
            "akankah mereka berhasil",
        ];
        const checks = [...(bannedPhrases || DEFAULT_BANNED_PHRASES), ...extraCliches]
            .map((x) => String(x).toLowerCase().trim())
            .filter(Boolean);

        const sentences = text.split(/(?<=[.!?])\s+/);
        while (sentences.length > 1) {
            const tail = sentences[sentences.length - 1].toLowerCase();
            if (checks.some((c) => tail.includes(c))) {
                removed.push(sentences.pop());
            } else {
                break;
            }
        }
        return { cleaned: sentences.join(" ").trim(), removed };
    }

    // =========================================================================
    // CLIENT-SIDE COMPILER (BACKUP JSON, MARKDOWN, PRINT HTML, & EPUB 3.0 ZIP)
    // =========================================================================

    function slugifyFilename(title, ext) {
        const slug = String(title || "novel")
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-+|-+$/g, "")
            .slice(0, 60) || "novel";
        return `${slug}.${ext}`;
    }

    function escapeHtml(str) {
        return String(str || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function collectCompiledChapters(db, projectId, approvedOnly = true) {
        const project = db.projects.find((p) => p.id === projectId);
        if (!project) throw new Error("Proyek novel tidak ditemukan.");
        const chapters = db.chapters
            .filter((c) => c.project_id === projectId)
            .sort((a, b) => a.chapter_number - b.chapter_number);
        const compiled = [];
        for (const ch of chapters) {
            const beats = db.micro_beats
                .filter((b) => b.chapter_id === ch.id)
                .sort((a, b) => a.beat_number - b.beat_number);
            const selectedBeats = approvedOnly
                ? beats.filter((b) => (b.generated_prose || "").trim() && (b.status === "COMPLETED" || b.status === "REVISED"))
                : beats.filter((b) => (b.generated_prose || "").trim());
            const finalBeats = selectedBeats.length ? selectedBeats : beats.filter((b) => (b.generated_prose || "").trim());
            const proseBlocks = finalBeats.map((b) => String(b.generated_prose || "").trim()).filter(Boolean);
            compiled.push({
                ...ch,
                prose_text: proseBlocks.join("\n\n"),
                word_count: proseBlocks.reduce((acc, p) => acc + countWords(p), 0),
            });
        }
        return { project, chapters: compiled };
    }

    // Minimal Standard-Compliant Stored ZIP Builder (Zero external dependency!)
    const CRC_TABLE = (() => {
        const tbl = new Uint32Array(256);
        for (let i = 0; i < 256; i++) {
            let c = i;
            for (let k = 0; k < 8; k++) {
                c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
            }
            tbl[i] = c >>> 0;
        }
        return tbl;
    })();

    function crc32(bytes) {
        let crc = 0xffffffff;
        for (let i = 0; i < bytes.length; i++) {
            crc = CRC_TABLE[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8);
        }
        return (crc ^ 0xffffffff) >>> 0;
    }

    function buildStoredZipBlob(entries) {
        const encoder = new TextEncoder();
        const fileRecords = [];
        let offset = 0;

        for (const entry of entries) {
            const nameBytes = encoder.encode(entry.path);
            const dataBytes = typeof entry.content === "string" ? encoder.encode(entry.content) : entry.content;
            const crc = crc32(dataBytes);

            const lfh = new ArrayBuffer(30 + nameBytes.length);
            const dv = new DataView(lfh);
            dv.setUint32(0, 0x04034b50, true);
            dv.setUint16(4, 20, true);
            dv.setUint16(6, 0x0800, true); // UTF-8 filename flag
            dv.setUint16(8, 0, true);      // STORE (method 0 — required for EPUB mimetype & valid everywhere)
            dv.setUint16(10, 0, true);
            dv.setUint16(12, 0x5421, true);
            dv.setUint32(14, crc, true);
            dv.setUint32(18, dataBytes.length, true);
            dv.setUint32(22, dataBytes.length, true);
            dv.setUint16(26, nameBytes.length, true);
            dv.setUint16(28, 0, true);
            new Uint8Array(lfh, 30).set(nameBytes);

            fileRecords.push({
                nameBytes,
                dataBytes,
                crc,
                offset,
                lfh: new Uint8Array(lfh),
            });
            offset += lfh.byteLength + dataBytes.length;
        }

        const centralParts = [];
        let centralSize = 0;
        for (const rec of fileRecords) {
            const cdh = new ArrayBuffer(46 + rec.nameBytes.length);
            const dv = new DataView(cdh);
            dv.setUint32(0, 0x02014b50, true);
            dv.setUint16(4, 20, true);
            dv.setUint16(6, 20, true);
            dv.setUint16(8, 0x0800, true);
            dv.setUint16(10, 0, true);
            dv.setUint16(12, 0, true);
            dv.setUint16(14, 0x5421, true);
            dv.setUint32(16, rec.crc, true);
            dv.setUint32(20, rec.dataBytes.length, true);
            dv.setUint32(24, rec.dataBytes.length, true);
            dv.setUint16(28, rec.nameBytes.length, true);
            dv.setUint16(30, 0, true);
            dv.setUint16(32, 0, true);
            dv.setUint16(34, 0, true);
            dv.setUint16(36, 0, true);
            dv.setUint32(38, 0, true);
            dv.setUint32(42, rec.offset, true);
            new Uint8Array(cdh, 46).set(rec.nameBytes);
            centralParts.push(new Uint8Array(cdh));
            centralSize += cdh.byteLength;
        }

        const eocd = new ArrayBuffer(22);
        const edv = new DataView(eocd);
        edv.setUint32(0, 0x06054b50, true);
        edv.setUint16(4, 0, true);
        edv.setUint16(6, 0, true);
        edv.setUint16(8, fileRecords.length, true);
        edv.setUint16(10, fileRecords.length, true);
        edv.setUint32(12, centralSize, true);
        edv.setUint32(16, offset, true);
        edv.setUint16(20, 0, true);

        const chunks = [];
        for (const rec of fileRecords) {
            chunks.push(rec.lfh, rec.dataBytes);
        }
        for (const cd of centralParts) chunks.push(cd);
        chunks.push(new Uint8Array(eocd));

        return new Blob(chunks, { type: "application/epub+zip" });
    }

    function downloadBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
            a.remove();
            URL.revokeObjectURL(url);
        }, 1200);
    }

    function buildBackupSnapshot(projectId) {
        const db = loadDb();
        const project = db.projects.find((p) => p.id === projectId);
        if (!project) throw new Error("Proyek tidak ditemukan.");
        const chapters = db.chapters
            .filter((c) => c.project_id === projectId)
            .sort((a, b) => a.chapter_number - b.chapter_number)
            .map((ch) => {
                const beats = db.micro_beats
                    .filter((b) => b.chapter_id === ch.id)
                    .sort((a, b) => a.beat_number - b.beat_number)
                    .map((b) => ({
                        ...b,
                        revisions: db.beat_revisions
                            .filter((r) => r.beat_id === b.id)
                            .sort((a, b2) => b2.revision_number - a.revision_number),
                    }));
                return { ...ch, beats };
            });
        return {
            backup_version: "1.0",
            exported_at: nowIso(),
            project,
            story_phases: db.story_phases.filter((p) => p.project_id === projectId),
            codex_items: db.codex_items.filter((c) => c.project_id === projectId),
            chapters,
        };
    }

    function triggerBackupDownload(projectId) {
        const snapshot = buildBackupSnapshot(projectId);
        const blob = new Blob([JSON.stringify(snapshot, null, 2)], { type: "application/json;charset=utf-8" });
        downloadBlob(blob, slugifyFilename(`${snapshot.project.title}-backup`, "json"));
    }

    function triggerExport(projectId, formatPath, params) {
        const db = loadDb();
        const author = (params && params.get("author")) || "";
        const approvedOnly = !params || params.get("approved_only") !== "false";
        const includeSynopsis = !params || params.get("include_synopsis") !== "false";
        const includeCodex = !params || params.get("include_codex_appendix") !== "false";
        const { project, chapters } = collectCompiledChapters(db, projectId, approvedOnly);
        const authorFinal = author.trim() || project.author_name || "Penulis Studio";

        if (formatPath === "markdown") {
            const lines = [
                "---",
                `title: "${project.title}"`,
                `author: "${authorFinal}"`,
                `genre: "${project.genre}"`,
                `exported_at: "${nowIso()}"`,
                "---",
                "",
                `# ${project.title}`,
                `*Oleh ${authorFinal} — ${project.genre}*`,
                "",
            ];
            if (includeSynopsis && project.logline) {
                lines.push("## Sinopsis", "", project.logline, "", "---", "");
            }
            for (const ch of chapters) {
                lines.push(`## Bab ${ch.chapter_number}: ${ch.title}`, "");
                lines.push(ch.prose_text || "*(Bab ini belum memiliki naskah prosa)*", "", "---", "");
            }
            if (includeCodex) {
                const codex = db.codex_items.filter((c) => c.project_id === projectId);
                if (codex.length) {
                    lines.push("## Lampiran Story Bible & Codex", "");
                    for (const c of codex) {
                        lines.push(`- **[${c.category}] ${c.name}**: ${c.core_description}`);
                    }
                    lines.push("");
                }
            }
            const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
            downloadBlob(blob, slugifyFilename(project.title, "md"));
            return;
        }

        if (formatPath === "print-html") {
            const chHtml = chapters
                .map((ch) => {
                    const paras = (ch.prose_text || "(Belum ada naskah)")
                        .split(/\n{2,}/)
                        .map((p) => `<p>${escapeHtml(p).replace(/\n/g, "<br/>")}</p>`)
                        .join("\n");
                    return `<section class="chapter"><div class="chapter-header"><div class="chapter-num">BAB ${ch.chapter_number}</div><h2>${escapeHtml(ch.title)}</h2></div>${paras}</section>`;
                })
                .join("\n");
            const htmlDoc = `<!DOCTYPE html><html lang="id"><head><meta charset="utf-8"><title>${escapeHtml(project.title)}</title>
<style>
body{font-family:"Georgia","Palatino Linotype",serif;line-height:1.75;color:#18181b;max-width:680px;margin:40px auto;padding:0 24px;text-align:justify}
.title-page{text-align:center;margin:90px 0 110px;page-break-after:always}
h1{font-size:2.2em;letter-spacing:.04em;text-transform:uppercase;margin-bottom:.25em}
.meta{color:#57534e;letter-spacing:.12em;text-transform:uppercase;font-size:.85em}
.author{margin-top:2em;font-weight:bold;font-size:1.15em}
.synopsis{font-style:italic;color:#44403c;margin:2em auto;max-width:520px}
.chapter{page-break-before:always;margin-top:2em}
.chapter-header{text-align:center;margin-bottom:2em}
.chapter-num{font-size:.8em;letter-spacing:.18em;color:#78716c}
p{text-indent:1.4em;margin:0 0 .9em}
.print-bar{position:fixed;top:12px;right:12px;background:#18181b;color:#fff;padding:8px 14px;border-radius:6px;font-family:sans-serif;font-size:13px;cursor:pointer;border:none}
@media print{.print-bar{display:none}}
</style></head><body>
<button class="print-bar" onclick="window.print()">🖨️ Cetak / Save PDF</button>
<div class="title-page">
<h1>${escapeHtml(project.title)}</h1>
<div class="meta">${escapeHtml(project.genre)}</div>
${includeSynopsis && project.logline ? `<p class="synopsis">${escapeHtml(project.logline)}</p>` : ""}
<div class="author">${escapeHtml(authorFinal)}</div>
</div>
${chHtml}
</body></html>`;
            const blob = new Blob([htmlDoc], { type: "text/html;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            global.open(url, "_blank", "noopener");
            return;
        }

        // Default: EPUB 3.0 ZIP langsung dari browser!
        const bookUuid = `urn:uuid:${project.id || uuid()}`;
        const cssContent = `body{font-family:Georgia,serif;line-height:1.75;margin:5% 6%;text-align:justify}h1,h2{text-align:center}p{text-indent:1.3em;margin:0 0 .8em}.title-page{text-align:center;margin-top:18%}`;
        const titleXhtml = `<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="id"><head><title>${escapeHtml(project.title)}</title><link rel="stylesheet" href="style.css"/></head>
<body><div class="title-page"><h1>${escapeHtml(project.title)}</h1><p><strong>${escapeHtml(authorFinal)}</strong></p><p><em>${escapeHtml(project.genre)}</em></p>${includeSynopsis && project.logline ? `<p>${escapeHtml(project.logline)}</p>` : ""}</div></body></html>`;

        const manifestItems = [
            `<item id="css" href="style.css" media-type="text/css"/>`,
            `<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>`,
            `<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>`,
            `<item id="title" href="title.xhtml" media-type="application/xhtml+xml"/>`,
        ];
        const spineItems = [`<itemref idref="title"/>`];
        const navLinks = [`<li><a href="title.xhtml">${escapeHtml(project.title)}</a></li>`];
        const ncxPoints = [`<navPoint id="np-0" playOrder="1"><navLabel><text>${escapeHtml(project.title)}</text></navLabel><content src="title.xhtml"/></navPoint>`];

        const zipEntries = [
            { path: "mimetype", content: "application/epub+zip" },
            {
                path: "META-INF/container.xml",
                content: `<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>`,
            },
            { path: "OEBPS/style.css", content: cssContent },
            { path: "OEBPS/title.xhtml", content: titleXhtml },
        ];

        chapters.forEach((ch, i) => {
            const fname = `chap_${i + 1}.xhtml`;
            const id = `chap_${i + 1}`;
            const paras = (ch.prose_text || "(Belum ada naskah)")
                .split(/\n{2,}/)
                .map((p) => `<p>${escapeHtml(p).replace(/\n/g, "<br/>")}</p>`)
                .join("\n");
            const xhtml = `<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="id"><head><title>Bab ${ch.chapter_number}: ${escapeHtml(ch.title)}</title><link rel="stylesheet" href="style.css"/></head>
<body><h2>Bab ${ch.chapter_number}: ${escapeHtml(ch.title)}</h2>${paras}</body></html>`;
            zipEntries.push({ path: `OEBPS/${fname}`, content: xhtml });
            manifestItems.push(`<item id="${id}" href="${fname}" media-type="application/xhtml+xml"/>`);
            spineItems.push(`<itemref idref="${id}"/>`);
            navLinks.push(`<li><a href="${fname}">Bab ${ch.chapter_number}: ${escapeHtml(ch.title)}</a></li>`);
            ncxPoints.push(`<navPoint id="np-${i + 1}" playOrder="${i + 2}"><navLabel><text>Bab ${ch.chapter_number}: ${escapeHtml(ch.title)}</text></navLabel><content src="${fname}"/></navPoint>`);
        });

        const navXhtml = `<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="id"><head><title>Daftar Isi</title></head>
<body><nav epub:type="toc"><h1>Daftar Isi</h1><ol>${navLinks.join("")}</ol></nav></body></html>`;

        const tocNcx = `<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
<head><meta name="dtb:uid" content="${bookUuid}"/></head>
<docTitle><text>${escapeHtml(project.title)}</text></docTitle>
<navMap>${ncxPoints.join("")}</navMap>
</ncx>`;

        const contentOpf = `<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="3.0">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:identifier id="BookId">${bookUuid}</dc:identifier>
  <dc:title>${escapeHtml(project.title)}</dc:title>
  <dc:creator>${escapeHtml(authorFinal)}</dc:creator>
  <dc:language>id</dc:language>
  <meta property="dcterms:modified">${nowIso()}</meta>
</metadata>
<manifest>${manifestItems.join("")}</manifest>
<spine toc="ncx">${spineItems.join("")}</spine>
</package>`;

        zipEntries.push(
            { path: "OEBPS/nav.xhtml", content: navXhtml },
            { path: "OEBPS/toc.ncx", content: tocNcx },
            { path: "OEBPS/content.opf", content: contentOpf }
        );

        const epubBlob = buildStoredZipBlob(zipEntries);
        downloadBlob(epubBlob, slugifyFilename(project.title, "epub"));
    }

    // =========================================================================
    // STREAMING & AI EXECUTION HANDLERS
    // =========================================================================

    function streamBeat(beatId, bodyObj, abortSignal) {
        const db = loadDb();
        let assembled;
        try {
            assembled = assembleBeatPrompts(db, beatId);
        } catch (err) {
            return Promise.resolve(
                new Response(
                    `data: ${JSON.stringify({ status: "ERROR", detail: err.message })}\n\n`,
                    { status: 200, headers: { "Content-Type": "text/event-stream" } }
                )
            );
        }

        const cfg = loadProviderConfig();
        if (cfg.provider_type === "local_llama" || !cfg.base_url) {
            const msg = "API AI belum dihubungkan di Browser Mode! Klik badge status AI di pojok kanan atas -> buka tab API Online -> masukkan API Key (OpenRouter / Google Gemini / Groq / Claude).";
            return Promise.resolve(
                new Response(
                    `data: ${JSON.stringify({ status: "ERROR", detail: msg })}\n\n`,
                    { status: 200, headers: { "Content-Type": "text/event-stream" } }
                )
            );
        }

        const beat = assembled.beat;
        const targetWords = Math.max(250, Number(beat.target_words) || 400);
        const maxTokens = Math.min(2600, Math.max(480, Math.round(targetWords * 2.2)));
        let userPrompt = assembled.dynamic_user_prompt;
        if (bodyObj && bodyObj.additional_author_note && String(bodyObj.additional_author_note).trim()) {
            userPrompt += `\n\n[CATATAN KHUSUS SUTRADARA]: ${String(bodyObj.additional_author_note).trim()}`;
        }

        const { url, headers, payload } = buildChatRequest(
            cfg,
            assembled.static_system_prompt,
            userPrompt,
            maxTokens,
            Number(bodyObj && bodyObj.temperature) || 0.75,
            true
        );

        const encoder = new TextEncoder();
        const emit = (controller, obj) => {
            controller.enqueue(encoder.encode(`data: ${JSON.stringify(obj)}\n\n`));
        };

        const stream = new ReadableStream({
            async start(controller) {
                emit(controller, { status: "STARTED", beat_id: beatId, beat_number: beat.beat_number });
                const chunks = [];
                try {
                    const resp = await fetch(url, {
                        method: "POST",
                        headers,
                        body: JSON.stringify(payload),
                        signal: abortSignal,
                    });
                    if (!resp.ok || !resp.body) {
                        const errBody = await resp.text().catch(() => "");
                        emit(controller, {
                            status: "ERROR",
                            detail: `Provider ${cfg.display_name || cfg.model_name} gagal (HTTP ${resp.status}): ${errBody.slice(0, 260)}`,
                        });
                        controller.close();
                        return;
                    }

                    const reader = resp.body.getReader();
                    const decoder = new TextDecoder("utf-8");
                    let buf = "";

                    while (true) {
                        const { value, done } = await reader.read();
                        if (done) break;
                        buf += decoder.decode(value, { stream: true });
                        const lines = buf.split("\n");
                        buf = lines.pop() || "";

                        for (const rawLine of lines) {
                            const line = rawLine.trim();
                            if (!line.startsWith("data:")) continue;
                            const dataStr = line.slice(5).trim();
                            if (!dataStr || dataStr === "[DONE]") continue;
                            let parsed;
                            try {
                                parsed = JSON.parse(dataStr);
                            } catch (_) {
                                continue;
                            }
                            const { token, error } = extractStreamToken(cfg.provider_type, parsed);
                            if (error) {
                                emit(controller, { status: "ERROR", detail: error });
                                controller.close();
                                return;
                            }
                            if (token) {
                                chunks.push(token);
                                emit(controller, { status: "STREAM", token });
                            }
                        }
                    }

                    const fullText = chunks.join("").trim();
                    const trimmed = trimMoralizingTail(fullText, assembled.project.banned_phrases);
                    const freshDb = loadDb();
                    const targetBeat = freshDb.micro_beats.find((b) => b.id === beatId);
                    if (targetBeat) {
                        targetBeat.generated_prose = trimmed.cleaned;
                        targetBeat.actual_words = countWords(trimmed.cleaned);
                        targetBeat.status = "COMPLETED";
                        targetBeat.updated_at = nowIso();
                        const prevRevs = freshDb.beat_revisions.filter((r) => r.beat_id === beatId);
                        const nextNum = prevRevs.length ? Math.max(...prevRevs.map((r) => r.revision_number)) + 1 : 1;
                        freshDb.beat_revisions.push({
                            id: uuid(),
                            beat_id: beatId,
                            revision_number: nextNum,
                            prose_content: trimmed.cleaned,
                            word_count: targetBeat.actual_words,
                            revision_note: `AI Generation (${cfg.model_name})`,
                            created_at: nowIso(),
                        });
                        recomputeChapterWordCount(freshDb, targetBeat.chapter_id);
                        saveDb(freshDb);
                    }

                    emit(controller, {
                        status: "DONE",
                        beat: targetBeat || beat,
                        actual_words: countWords(trimmed.cleaned),
                        trimmed_moralizing_sentences: trimmed.removed,
                    });
                    controller.close();
                } catch (err) {
                    if (err && err.name === "AbortError") {
                        const partial = chunks.join("").trim();
                        if (partial) {
                            const freshDb = loadDb();
                            const tb = freshDb.micro_beats.find((b) => b.id === beatId);
                            if (tb) {
                                tb.generated_prose = partial;
                                tb.actual_words = countWords(partial);
                                tb.status = "COMPLETED";
                                tb.updated_at = nowIso();
                                recomputeChapterWordCount(freshDb, tb.chapter_id);
                                saveDb(freshDb);
                            }
                        }
                        controller.close();
                        return;
                    }
                    const wrapped = wrapFetchError(err, cfg.base_url);
                    emit(controller, { status: "ERROR", detail: wrapped.message });
                    controller.close();
                }
            },
        });

        return Promise.resolve(
            new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } })
        );
    }

    // =========================================================================
    // REST API ROUTER IN BROWSER MODE (Maps FastAPI routes -> localStorage)
    // =========================================================================

    async function handleApiRequest(path, options = {}) {
        const method = String(options.method || "GET").toUpperCase();
        const urlObj = new URL(path, "https://browser.local");
        const pathname = urlObj.pathname;
        const params = urlObj.searchParams;
        const body = options.body ? JSON.parse(options.body) : {};
        const db = loadDb();

        // 1. System & Runtime
        if (pathname === "/api/system/health" || pathname === "/api/system/ram") {
            const devGb = Number(navigator.deviceMemory || 8);
            const totalMb = Math.round(devGb * 1024);
            const usedMb = Math.round(totalMb * 0.35);
            const summary = getPublicProviderSummary();
            const ramObj = {
                total_mb: totalMb,
                used_mb: usedMb,
                available_mb: totalMb - usedMb,
                usage_percent: 35.0,
                inference_busy: false,
                inference_waiting: 0,
                active_task: null,
            };
            if (pathname === "/api/system/ram") return ramObj;
            return {
                status: "ok",
                runtime_mode: "browser",
                llama_server_url: "",
                llama_server_online: false,
                ai_ready: summary.provider_type !== "local_llama",
                llama_binary_installed: false,
                active_model_filename: "",
                ai_provider: summary,
                ram: ramObj,
                security: { security_mode: "BROWSER_LOCAL_STORAGE" },
            };
        }

        if (pathname === "/api/models") {
            return {
                llama_server_online: false,
                browser_mode: true,
                models_dir: "Browser Storage (Tanpa File Lokal)",
                local_models: [],
                downloads_dir_candidates: [],
                curated_catalog: [],
                active_downloads: {},
                total_cpu_cores: Number(navigator.hardwareConcurrency || 4),
            };
        }

        // 2. AI Provider Configuration & Live Probing
        if (pathname === "/api/ai/provider" && method === "GET") {
            return getPublicProviderSummary();
        }
        if (pathname === "/api/ai/provider" && method === "POST") {
            const { saved, probeResult } = await resolveAndActivateProvider(
                body,
                body.verify_connection !== false
            );
            return {
                saved: true,
                provider: getPublicProviderSummary(),
                test: probeResult,
                stopped_local_llama: null,
                configured_model: saved.model_name,
                detected_provider: saved.display_name,
            };
        }
        if (pathname === "/api/ai/provider/test" && method === "POST") {
            const current = loadProviderConfig();
            const rawPtype = String(body.provider_type || "auto").trim().toLowerCase();
            const rawBase = String(body.base_url || "").trim();
            if (rawPtype === "auto" && !rawBase) {
                const key = body.api_key && String(body.api_key).trim()
                    ? String(body.api_key).trim()
                    : (current.provider_type !== "local_llama" ? current.api_key : "");
                const { probeResult } = await autoDetectAndProbe(key, body.model_name || "");
                return probeResult;
            }
            const effectivePtype = rawPtype === "auto"
                ? (rawBase.toLowerCase().includes("anthropic") ? "anthropic" : "openai_compatible")
                : rawPtype;
            const presetMeta = PRESET_MAP[body.preset_id] || {};
            const baseUrl = normalizeBaseUrl(rawBase || presetMeta.base_url || current.base_url);
            const sameTarget = body.preset_id === current.preset_id && baseUrl === String(current.base_url || "").replace(/\/+$/, "");
            const apiKey = body.api_key && String(body.api_key).trim() ? String(body.api_key).trim() : (sameTarget ? current.api_key : "");
            if (presetMeta.requires_api_key && !apiKey) {
                throw new Error(`Masukkan API Key untuk ${presetMeta.label || body.preset_id} terlebih dahulu.`);
            }
            const { probeResult } = await pickAndProbeCandidates(
                { provider_type: effectivePtype, preset_id: body.preset_id, base_url: baseUrl, api_key: apiKey },
                body.model_name || ""
            );
            return probeResult;
        }
        if (pathname === "/api/ai/provider/models" && method === "POST") {
            const current = loadProviderConfig();
            const key = body.api_key && String(body.api_key).trim() ? String(body.api_key).trim() : current.api_key;
            const models = await fetchRemoteModels(body.provider_type, body.base_url, key);
            return { count: models.length, models };
        }

        // 3. Projects CRUD + Restore
        if (pathname === "/api/projects" && method === "GET") {
            return [...db.projects].sort((a, b) => String(b.updated_at || "").localeCompare(String(a.updated_at || "")));
        }
        if (pathname === "/api/projects" && method === "POST") {
            const now = nowIso();
            const totalCh = Number(body.total_planned_chapters) || 24;
            const proj = {
                id: uuid(),
                title: body.title || "Novel Baru",
                author_name: (body.author_name || "").trim() || "Penulis Studio",
                genre: body.genre || "Fiction",
                logline: body.logline || "",
                main_objective: body.main_objective || "Menyelesaikan cerita utama.",
                pov_style: body.pov_style || "Third-Person Limited",
                tense_style: body.tense_style || "Lampau / Past Narrative",
                tone_style: body.tone_style || "Atmosferik, Show Don't Tell",
                style_sample: body.style_sample || "",
                banned_phrases: Array.isArray(body.banned_phrases) ? body.banned_phrases : [...DEFAULT_BANNED_PHRASES],
                total_planned_chapters: totalCh,
                default_chapter_words: Number(body.default_chapter_words) || 3200,
                rolling_global_summary: body.rolling_global_summary || "",
                active_model_profile: body.active_model_profile || "Cloud API",
                created_at: now,
                updated_at: now,
            };
            db.projects.push(proj);
            if (body.seed_default_phases !== false && totalCh >= 6) {
                buildDefaultPhases(totalCh).forEach((ph, idx) => {
                    db.story_phases.push({ id: uuid(), project_id: proj.id, phase_order: idx + 1, ...ph, created_at: now });
                });
            }
            saveDb(db);
            return proj;
        }
        if (pathname === "/api/projects/restore" && method === "POST") {
            const srcProj = body.project;
            if (!srcProj || !srcProj.title) throw new Error("Format file backup JSON tidak valid.");
            const newProjId = uuid();
            const now = nowIso();
            const newProj = { ...srcProj, id: newProjId, created_at: now, updated_at: now };
            db.projects.push(newProj);

            const phaseIdMap = {};
            for (const ph of body.story_phases || []) {
                const nid = uuid();
                phaseIdMap[ph.id] = nid;
                db.story_phases.push({ ...ph, id: nid, project_id: newProjId });
            }
            const codexIdMap = {};
            for (const c of body.codex_items || []) {
                const nid = uuid();
                codexIdMap[c.id] = nid;
                db.codex_items.push({ ...c, id: nid, project_id: newProjId });
            }
            const chIdMap = {};
            const beatIdMap = {};
            for (const ch of body.chapters || []) {
                const { beats: nestedBeats, ...chFields } = ch;
                const newChId = uuid();
                chIdMap[ch.id] = newChId;
                db.chapters.push({
                    ...chFields,
                    id: newChId,
                    project_id: newProjId,
                    phase_id: phaseIdMap[ch.phase_id] || ch.phase_id || null,
                });
                if (Array.isArray(nestedBeats)) {
                    for (const b of nestedBeats) {
                        const { revisions: nestedRevs, ...bFields } = b;
                        const newBeatId = uuid();
                        beatIdMap[b.id] = newBeatId;
                        db.micro_beats.push({
                            ...bFields,
                            id: newBeatId,
                            chapter_id: newChId,
                            pov_character_id: codexIdMap[b.pov_character_id] || null,
                            location_id: codexIdMap[b.location_id] || null,
                        });
                        if (Array.isArray(nestedRevs)) {
                            for (const r of nestedRevs) {
                                db.beat_revisions.push({ ...r, id: uuid(), beat_id: newBeatId });
                            }
                        }
                    }
                }
            }
            // Kompatibilitas format flat bila ada
            for (const b of body.micro_beats || []) {
                if (beatIdMap[b.id]) continue;
                const nid = uuid();
                beatIdMap[b.id] = nid;
                db.micro_beats.push({
                    ...b,
                    id: nid,
                    chapter_id: chIdMap[b.chapter_id] || b.chapter_id,
                    pov_character_id: codexIdMap[b.pov_character_id] || null,
                    location_id: codexIdMap[b.location_id] || null,
                });
            }
            for (const r of body.beat_revisions || []) {
                db.beat_revisions.push({
                    ...r,
                    id: uuid(),
                    beat_id: beatIdMap[r.beat_id] || r.beat_id,
                });
            }
            saveDb(db);
            return newProj;
        }

        let m = pathname.match(/^\/api\/projects\/([^/]+)$/);
        if (m) {
            const pid = decodeURIComponent(m[1]);
            const idx = db.projects.findIndex((p) => p.id === pid);
            if (idx === -1) throw new Error("Proyek tidak ditemukan.");
            if (method === "GET") return db.projects[idx];
            if (method === "PUT" || method === "PATCH") {
                db.projects[idx] = { ...db.projects[idx], ...body, updated_at: nowIso() };
                saveDb(db);
                return db.projects[idx];
            }
            if (method === "DELETE") {
                const chIds = new Set(db.chapters.filter((c) => c.project_id === pid).map((c) => c.id));
                const bIds = new Set(db.micro_beats.filter((b) => chIds.has(b.chapter_id)).map((b) => b.id));
                db.projects.splice(idx, 1);
                db.story_phases = db.story_phases.filter((p) => p.project_id !== pid);
                db.codex_items = db.codex_items.filter((c) => c.project_id !== pid);
                db.chapters = db.chapters.filter((c) => c.project_id !== pid);
                db.micro_beats = db.micro_beats.filter((b) => !chIds.has(b.chapter_id));
                db.beat_revisions = db.beat_revisions.filter((r) => !bIds.has(r.beat_id));
                saveDb(db);
                return { deleted: true, project_id: pid };
            }
        }

        // 4. Story Phases
        m = pathname.match(/^\/api\/projects\/([^/]+)\/phases$/);
        if (m) {
            const pid = decodeURIComponent(m[1]);
            if (method === "GET") {
                return db.story_phases
                    .filter((p) => p.project_id === pid)
                    .sort((a, b) => a.phase_order - b.phase_order || a.start_chapter - b.start_chapter);
            }
            if (method === "POST") {
                const ph = { id: uuid(), project_id: pid, ...body, created_at: nowIso() };
                db.story_phases.push(ph);
                saveDb(db);
                return ph;
            }
        }
        m = pathname.match(/^\/api\/phases\/([^/]+)$/);
        if (m) {
            const phId = decodeURIComponent(m[1]);
            const idx = db.story_phases.findIndex((p) => p.id === phId);
            if (idx === -1) throw new Error("Fase tidak ditemukan.");
            if (method === "PUT" || method === "PATCH") {
                db.story_phases[idx] = { ...db.story_phases[idx], ...body };
                saveDb(db);
                return db.story_phases[idx];
            }
            if (method === "DELETE") {
                db.story_phases.splice(idx, 1);
                saveDb(db);
                return { deleted: true };
            }
        }

        // 5. Codex & Search
        m = pathname.match(/^\/api\/projects\/([^/]+)\/codex\/search$/);
        if (m && method === "GET") {
            return searchBm25Like(db, decodeURIComponent(m[1]), params.get("q") || "", Number(params.get("limit")) || 8);
        }
        m = pathname.match(/^\/api\/projects\/([^/]+)\/codex$/);
        if (m) {
            const pid = decodeURIComponent(m[1]);
            if (method === "GET") {
                return db.codex_items.filter((c) => c.project_id === pid);
            }
            if (method === "POST") {
                const item = { id: uuid(), project_id: pid, ...body, created_at: nowIso(), updated_at: nowIso() };
                db.codex_items.push(item);
                saveDb(db);
                return item;
            }
        }
        m = pathname.match(/^\/api\/codex\/([^/]+)$/);
        if (m) {
            const cid = decodeURIComponent(m[1]);
            const idx = db.codex_items.findIndex((c) => c.id === cid);
            if (idx === -1) throw new Error("Entitas Codex tidak ditemukan.");
            if (method === "PUT" || method === "PATCH") {
                db.codex_items[idx] = { ...db.codex_items[idx], ...body, updated_at: nowIso() };
                saveDb(db);
                return db.codex_items[idx];
            }
            if (method === "DELETE") {
                db.codex_items.splice(idx, 1);
                saveDb(db);
                return { deleted: true };
            }
        }

        // 6. Chapters & Pacing Plan & Beat Generation
        m = pathname.match(/^\/api\/projects\/([^/]+)\/chapters$/);
        if (m) {
            const pid = decodeURIComponent(m[1]);
            if (method === "GET") {
                return db.chapters
                    .filter((c) => c.project_id === pid)
                    .sort((a, b) => a.chapter_number - b.chapter_number)
                    .map((c) => enrichChapter(db, c));
            }
            if (method === "POST") {
                const ch = {
                    id: uuid(),
                    project_id: pid,
                    chapter_number: Number(body.chapter_number) || 1,
                    title: body.title || "Bab Baru",
                    chapter_goal: body.chapter_goal || "",
                    target_word_count: Number(body.target_word_count) || 3200,
                    current_word_count: 0,
                    pacing_mode: body.pacing_mode || "BALANCED",
                    mix_world_building: Number(body.mix_world_building ?? 50),
                    mix_psychology: Number(body.mix_psychology ?? 50),
                    mix_sensory: Number(body.mix_sensory ?? 70),
                    mix_dialogue: Number(body.mix_dialogue ?? 40),
                    mix_action: Number(body.mix_action ?? 30),
                    ending_hook_style: body.ending_hook_style || "CLIFFHANGER",
                    chapter_summary: body.chapter_summary || "",
                    status: "PLANNED",
                    created_at: nowIso(),
                    updated_at: nowIso(),
                };
                db.chapters.push(ch);
                saveDb(db);
                return enrichChapter(db, ch);
            }
        }
        m = pathname.match(/^\/api\/chapters\/([^/]+)\/calculate-plan$/);
        if (m && method === "GET") {
            const raw = db.chapters.find((c) => c.id === decodeURIComponent(m[1]));
            if (!raw) throw new Error("Bab tidak ditemukan.");
            const ch = enrichChapter(db, raw);
            const plan = calculateChapterPlan(ch.target_word_count, ch.pacing_mode, ch.tension_min, ch.tension_max);
            const midT = Math.round(((ch.tension_min || 15) + (ch.tension_max || 55)) / 2);
            return {
                chapter_id: ch.id,
                chapter_number: ch.chapter_number,
                chapter_title: ch.title,
                phase_name: ch.phase_name,
                plan,
                mixing_directives: compileMixingDirectives(ch, midT),
            };
        }
        m = pathname.match(/^\/api\/chapters\/([^/]+)\/generate-beats$/);
        if (m && method === "POST") {
            const cid = decodeURIComponent(m[1]);
            const rawCh = db.chapters.find((c) => c.id === cid);
            if (!rawCh) throw new Error("Bab tidak ditemukan.");
            const ch = enrichChapter(db, rawCh);
            const codex = db.codex_items.filter((c) => c.project_id === ch.project_id);
            const plan = calculateChapterPlan(ch.target_word_count, ch.pacing_mode, ch.tension_min, ch.tension_max);
            const fallback = buildDeterministicFallbackBeats(ch, plan, codex);

            let finalPayload = fallback;
            let source = "deterministic_pacing_engine";
            const cfg = loadProviderConfig();
            if (cfg.provider_type !== "local_llama" && cfg.base_url) {
                try {
                    const sysP = `Anda adalah THE PLOT ARCHITECT. Pecah Tujuan Bab menjadi tepat ${plan.total_micro_beats} Micro-Beats JSON valid dengan key "beats": [{beat_number, tension_level, target_words, pov_character_name, location_name, sensory_anchor, conflict_focus, beat_instruction, stopping_point}].`;
                    const usrP = `Bab ${ch.chapter_number}: "${ch.title}"\nTujuan: ${ch.chapter_goal}\nPacing: ${ch.pacing_mode}\nTarget Kata: ${ch.target_word_count}\nKarakter: ${codex.filter((c) => c.category === "CHARACTER").map((c) => c.name).join(", ")}\nLokasi: ${codex.filter((c) => c.category === "LOCATION").map((c) => c.name).join(", ")}`;
                    const { url, headers, payload } = buildChatRequest(cfg, sysP, usrP, Math.min(2400, plan.total_micro_beats * 220), 0.4, false);
                    const resp = await fetch(url, { method: "POST", headers, body: JSON.stringify(payload) });
                    if (resp.ok) {
                        const txt = extractNonStreamText(cfg.provider_type, await resp.json());
                        const jMatch = txt.match(/\{[\s\S]*\}/);
                        if (jMatch) {
                            const parsed = JSON.parse(jMatch[0]);
                            if (Array.isArray(parsed.beats) && parsed.beats.length) {
                                const charByName = Object.fromEntries(codex.filter((c) => c.category === "CHARACTER").map((c) => [c.name.toLowerCase(), c.id]));
                                const locByName = Object.fromEntries(codex.filter((c) => c.category === "LOCATION").map((c) => [c.name.toLowerCase(), c.id]));
                                finalPayload = fallback.map((fb, idx) => {
                                    const item = parsed.beats[idx] || {};
                                    return {
                                        ...fb,
                                        pov_character_id: charByName[String(item.pov_character_name || "").toLowerCase()] || fb.pov_character_id,
                                        location_id: locByName[String(item.location_name || "").toLowerCase()] || fb.location_id,
                                        tension_level: Number(item.tension_level) || fb.tension_level,
                                        target_words: Number(item.target_words) || fb.target_words,
                                        sensory_anchor: String(item.sensory_anchor || fb.sensory_anchor),
                                        conflict_focus: String(item.conflict_focus || fb.conflict_focus),
                                        beat_instruction: String(item.beat_instruction || fb.beat_instruction),
                                        stopping_point: String(item.stopping_point || fb.stopping_point),
                                    };
                                });
                                source = "llama_server_architect";
                            }
                        }
                    }
                } catch (_) {
                    // Fallback mulus ke engine deterministik jika AI offline/gagal
                }
            }

            const oldIds = new Set(db.micro_beats.filter((b) => b.chapter_id === cid).map((b) => b.id));
            db.micro_beats = db.micro_beats.filter((b) => b.chapter_id !== cid);
            db.beat_revisions = db.beat_revisions.filter((r) => !oldIds.has(r.beat_id));
            const created = finalPayload.map((item) => ({
                id: uuid(),
                chapter_id: cid,
                ...item,
                generated_prose: "",
                extracted_summary: "",
                actual_words: 0,
                status: "PENDING",
                created_at: nowIso(),
                updated_at: nowIso(),
            }));
            db.micro_beats.push(...created);
            rawCh.status = "DRAFTING";
            recomputeChapterWordCount(db, cid);
            saveDb(db);
            return {
                chapter_id: cid,
                chapter_number: rawCh.chapter_number,
                generation_source: source,
                pacing_plan: plan,
                beats: created,
            };
        }
        m = pathname.match(/^\/api\/chapters\/([^/]+)\/beats$/);
        if (m) {
            const cid = decodeURIComponent(m[1]);
            const existing = db.micro_beats.filter((b) => b.chapter_id === cid).sort((a, b) => a.beat_number - b.beat_number);
            if (method === "GET") return existing;
            if (method === "POST") {
                const nextNum = existing.length ? Math.max(...existing.map((b) => b.beat_number)) + 1 : 1;
                const beat = {
                    id: uuid(),
                    chapter_id: cid,
                    beat_number: nextNum,
                    pov_character_id: body.pov_character_id || null,
                    location_id: body.location_id || null,
                    tension_level: Number(body.tension_level) || 45,
                    target_words: Number(body.target_words) || 400,
                    beat_instruction: body.beat_instruction || "Lanjutkan adegan berikutnya secara konkret dan atmosferik.",
                    stopping_point: body.stopping_point || "Hentikan tepat pada dialog atau tindakan mikro penutup.",
                    sensory_anchor: body.sensory_anchor || "",
                    conflict_focus: body.conflict_focus || "",
                    generated_prose: "",
                    extracted_summary: "",
                    actual_words: 0,
                    status: "PENDING",
                    created_at: nowIso(),
                    updated_at: nowIso(),
                };
                db.micro_beats.push(beat);
                saveDb(db);
                return beat;
            }
        }
        m = pathname.match(/^\/api\/chapters\/([^/]+)$/);
        if (m) {
            const cid = decodeURIComponent(m[1]);
            const idx = db.chapters.findIndex((c) => c.id === cid);
            if (idx === -1) throw new Error("Bab tidak ditemukan.");
            if (method === "GET") {
                const beats = db.micro_beats.filter((b) => b.chapter_id === cid).sort((a, b) => a.beat_number - b.beat_number);
                return { ...enrichChapter(db, db.chapters[idx]), beats };
            }
            if (method === "PUT" || method === "PATCH") {
                db.chapters[idx] = { ...db.chapters[idx], ...body, updated_at: nowIso() };
                saveDb(db);
                return enrichChapter(db, db.chapters[idx]);
            }
            if (method === "DELETE") {
                const bIds = new Set(db.micro_beats.filter((b) => b.chapter_id === cid).map((b) => b.id));
                db.chapters.splice(idx, 1);
                db.micro_beats = db.micro_beats.filter((b) => b.chapter_id !== cid);
                db.beat_revisions = db.beat_revisions.filter((r) => !bIds.has(r.beat_id));
                saveDb(db);
                return { deleted: true };
            }
        }

        // 7. Micro-Beats, Move, Revisions, Memory Context, Extract State
        m = pathname.match(/^\/api\/beats\/([^/]+)\/move$/);
        if (m && method === "POST") {
            const bid = decodeURIComponent(m[1]);
            const beat = db.micro_beats.find((b) => b.id === bid);
            if (!beat) throw new Error("Beat tidak ditemukan.");
            const list = db.micro_beats.filter((b) => b.chapter_id === beat.chapter_id).sort((a, b) => a.beat_number - b.beat_number);
            const cur = list.findIndex((b) => b.id === bid);
            const target = body.direction === "up" ? cur - 1 : cur + 1;
            if (target >= 0 && target < list.length) {
                const tmp = list[cur].beat_number;
                list[cur].beat_number = list[target].beat_number;
                list[target].beat_number = tmp;
                saveDb(db);
            }
            return list.sort((a, b) => a.beat_number - b.beat_number);
        }
        m = pathname.match(/^\/api\/beats\/([^/]+)\/revisions$/);
        if (m) {
            const bid = decodeURIComponent(m[1]);
            const beat = db.micro_beats.find((b) => b.id === bid);
            if (!beat) throw new Error("Beat tidak ditemukan.");
            if (method === "GET") {
                return db.beat_revisions.filter((r) => r.beat_id === bid).sort((a, b) => b.revision_number - a.revision_number);
            }
            if (method === "POST") {
                const prose = String(body.prose_content || "");
                const words = countWords(prose);
                beat.generated_prose = prose;
                beat.actual_words = words;
                beat.status = words > 0 ? "REVISED" : "PENDING";
                beat.updated_at = nowIso();
                const revs = db.beat_revisions.filter((r) => r.beat_id === bid);
                const nextNum = revs.length ? Math.max(...revs.map((r) => r.revision_number)) + 1 : 1;
                db.beat_revisions.push({
                    id: uuid(),
                    beat_id: bid,
                    revision_number: nextNum,
                    prose_content: prose,
                    word_count: words,
                    revision_note: body.revision_note || "Manual Author Polish",
                    created_at: nowIso(),
                });
                recomputeChapterWordCount(db, beat.chapter_id);
                saveDb(db);
                return beat;
            }
        }
        m = pathname.match(/^\/api\/beats\/([^/]+)\/memory-context$/);
        if (m && method === "GET") {
            const ctx = assembleBeatPrompts(db, decodeURIComponent(m[1]));
            return {
                beat_number: ctx.beat.beat_number,
                fts5_telemetry: ctx.fts5_telemetry,
                tiers_breakdown: ctx.tiers_breakdown,
                static_system_prompt: ctx.static_system_prompt,
                dynamic_user_prompt: ctx.dynamic_user_prompt,
                full_4tier_prompt: ctx.full_4tier_prompt,
            };
        }
        m = pathname.match(/^\/api\/beats\/([^/]+)\/extract-state$/);
        if (m && method === "POST") {
            const bid = decodeURIComponent(m[1]);
            const beat = db.micro_beats.find((b) => b.id === bid);
            if (!beat) throw new Error("Beat tidak ditemukan.");
            const prose = String(beat.generated_prose || "").trim();
            if (!prose) throw new Error("Beat belum memiliki teks prosa.");
            const ch = db.chapters.find((c) => c.id === beat.chapter_id);
            const proj = ch ? db.projects.find((p) => p.id === ch.project_id) : null;
            const sents = prose.split(/(?<=[.!?])\s+/).filter(Boolean);
            let beatSummary = sents.length >= 2 ? `${sents[0]} ${sents[sents.length - 1]}` : prose.slice(0, 220);
            let src = "fast_local";

            const mode = params.get("mode") || "auto";
            const cfg = loadProviderConfig();
            if (mode !== "fast_local" && cfg.provider_type !== "local_llama" && cfg.base_url) {
                try {
                    const { url, headers, payload } = buildChatRequest(
                        cfg,
                        'Ringkas kejadian faktual adegan ini menjadi JSON {"summary": "..."} maksimal 2 kalimat.',
                        prose.slice(0, 3500),
                        180,
                        0.2,
                        false
                    );
                    const r = await fetch(url, { method: "POST", headers, body: JSON.stringify(payload) });
                    if (r.ok) {
                        const txt = extractNonStreamText(cfg.provider_type, await r.json());
                        const jm = txt.match(/\{[\s\S]*\}/);
                        if (jm) {
                            const parsed = JSON.parse(jm[0]);
                            if (parsed.summary) {
                                beatSummary = String(parsed.summary).trim();
                                src = "llama_server_extractor";
                            }
                        }
                    }
                } catch (_) {
                    // Fallback lokal instan
                }
            }

            beat.extracted_summary = beatSummary.slice(0, 420);
            beat.updated_at = nowIso();
            if (ch) {
                const chBeats = db.micro_beats.filter((b) => b.chapter_id === ch.id).sort((a, b) => a.beat_number - b.beat_number);
                ch.chapter_summary = chBeats.map((b) => b.extracted_summary).filter(Boolean).slice(-4).join(" ");
            }
            if (proj) {
                const projChs = db.chapters.filter((c) => c.project_id === proj.id).sort((a, b) => a.chapter_number - b.chapter_number);
                proj.rolling_global_summary = projChs.map((c) => c.chapter_summary ? `Bab ${c.chapter_number}: ${c.chapter_summary}` : "").filter(Boolean).slice(-4).join("\n");
            }
            saveDb(db);
            return {
                beat_summary: beat.extracted_summary,
                chapter_summary: ch ? ch.chapter_summary : "",
                rolling_global_summary: proj ? proj.rolling_global_summary : "",
                updated_characters: [],
                extraction_source: src,
            };
        }
        m = pathname.match(/^\/api\/beats\/([^/]+)$/);
        if (m) {
            const bid = decodeURIComponent(m[1]);
            const idx = db.micro_beats.findIndex((b) => b.id === bid);
            if (idx === -1) throw new Error("Beat tidak ditemukan.");
            if (method === "PUT" || method === "PATCH") {
                const updated = { ...db.micro_beats[idx], ...body, updated_at: nowIso() };
                if ("generated_prose" in body) {
                    updated.actual_words = countWords(updated.generated_prose);
                }
                db.micro_beats[idx] = updated;
                recomputeChapterWordCount(db, updated.chapter_id);
                saveDb(db);
                return updated;
            }
            if (method === "DELETE") {
                const chId = db.micro_beats[idx].chapter_id;
                db.micro_beats.splice(idx, 1);
                db.beat_revisions = db.beat_revisions.filter((r) => r.beat_id !== bid);
                db.micro_beats
                    .filter((b) => b.chapter_id === chId)
                    .sort((a, b) => a.beat_number - b.beat_number)
                    .forEach((b, i) => {
                        b.beat_number = i + 1;
                    });
                recomputeChapterWordCount(db, chId);
                saveDb(db);
                return { deleted: true };
            }
        }

        throw new Error(`Endpoint browser mode tidak dikenal: ${method} ${pathname}`);
    }

    global.ZenWebRuntime = {
        PROVIDER_PRESETS,
        handleApiRequest,
        streamBeat,
        triggerBackupDownload,
        triggerExport,
        getPublicProviderSummary,
    };
})(window);
