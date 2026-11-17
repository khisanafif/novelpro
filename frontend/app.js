/**
 * THE ZEN LITERARY STUDIO - FRONTEND APPLICATION CONTROLLER (Alpine.js + Fetch SSE)
 * Terhubung penuh ke seluruh endpoint FastAPI Tahap 1:
 * - /api/system/ram & /api/system/health
 * - /api/projects, /api/projects/{id}/story-bible
 * - /api/projects/{id}/phases, /api/phases/{id}, /api/projects/{id}/active-phase/{num}
 * - /api/projects/{id}/codex, /api/codex/{id}, /api/projects/{id}/codex/search (FTS5 BM25)
 * - /api/projects/{id}/chapters, /api/chapters/{id}, /api/chapters/{id}/calculate-plan
 * - /api/chapters/{id}/generate-beats, /api/chapters/{id}/beats
 * - /api/beats/{id}, /api/beats/{id}/stream (SSE), /api/beats/{id}/extract-state
 * - /api/beats/{id}/revisions
 */

function novelStudioApp() {
    return {
        // Konfigurasi URL API (Otomatis menyesuaikan origin saat dibuka dari localhost atau Wi-Fi LAN)
        apiBase: window.NOVEL_API_BASE || "",

        // Tema & Mode Layar
        darkMode: localStorage.getItem("zen_novel_theme") === "dark",
        zenMode: false,
        leftDrawerOpen: window.innerWidth >= 1024,
        rightDrawerOpen: window.innerWidth >= 1280,
        leftTab: "chapters", // 'chapters' | 'bible' | 'codex'

        // Status Sistem & RAM Linux Mint 8 GB
        systemHealth: {
            llama_server_online: false,
            ai_ready: false,
            llama_server_url: "http://127.0.0.1:8080",
            ai_provider: {
                provider_type: "local_llama",
                preset_id: "local_llama",
                display_name: "Lokal llama-server (GGUF)",
                base_url: "",
                model_name: "",
                has_api_key: false,
                api_key_masked: "",
            },
            ram: {
                total_mb: 8192,
                used_mb: 0,
                available_mb: 8192,
                usage_percent: 0,
                inference_busy: false,
                inference_waiting: 0,
                active_task: null,
            },
        },
        ramPollTimer: null,

        // Notifikasi Toast Ringan
        toast: {
            visible: false,
            message: "",
            type: "info", // 'info' | 'success' | 'warning' | 'error'
            timer: null,
        },

        // Daftar Project & Project Aktif (Story Bible)
        projects: [],
        activeProjectId: null,
        activeProject: {
            id: "",
            title: "",
            author_name: "Penulis Studio",
            genre: "",
            logline: "",
            main_objective: "",
            pov_style: "Third-Person Limited",
            tense_style: "Lampau / Past Narrative",
            tone_style: "Atmosferik, Imersif, Show Dont Tell",
            style_sample: "",
            banned_phrases: [],
            total_planned_chapters: 24,
            default_chapter_words: 3200,
            rolling_global_summary: "",
            active_model_profile: "Qwen2.5-3B-Instruct-Q4_K_M",
        },
        bannedPhrasesText: "",
        showNewProjectModal: false,
        isRestoringBackup: false,
        newProjectForm: {
            title: "",
            author_name: "Penulis Studio",
            genre: "Literary Mystery / Historical Fiction",
            logline: "",
            main_objective: "",
            pov_style: "Third-Person Limited",
            tense_style: "Lampau / Past Narrative",
            tone_style: "Atmosferik, Imersif, Show Dont Tell",
            style_sample: "Hujan belum benar-benar turun, tetapi bau tanah basah dan cengkeh tua sudah merayap dari sela papan gudang.",
            total_planned_chapters: 24,
            default_chapter_words: 3200,
            active_model_profile: "Qwen2.5-3B-Instruct-Q4_K_M",
        },

        // 1. Interactive Phase-Range Timeline Bar
        phases: [],
        selectedPhase: null,
        showPhaseModal: false,
        editingPhaseId: null,
        phaseForm: {
            phase_order: 1,
            phase_name: "",
            start_chapter: 1,
            end_chapter: 4,
            default_pacing: "SLOW_BURN",
            tension_min: 15,
            tension_max: 35,
            building_focus: "",
            phase_guardrails: "",
        },

        // 2. Codex & Lorebook + FTS5 BM25 Search
        codexItems: [],
        codexFilterCategory: "ALL",
        bm25SearchQuery: "",
        bm25SearchResults: {
            codex_matches: [],
            episodic_memories: [],
        },
        isSearchingBm25: false,
        showCodexModal: false,
        editingCodexId: null,
        codexForm: {
            category: "CHARACTER",
            name: "",
            aliases_and_tags: "",
            keywords_csv: "",
            is_pinned: 0,
            core_description: "",
            speech_style: "",
            current_state: {
                location: "",
                condition: "Sehat",
                emotional_state: "Stabil",
                knowledge: "",
            },
        },

        // 3. Chapters & Micro-Beats Canvas
        chapters: [],
        activeChapterId: null,
        activeChapter: null,
        beats: [],
        pacingPlan: {
            total_micro_beats: 8,
            words_per_beat: 400,
            major_plot_events_needed: 4,
            pacing_mode: "BALANCED",
            tension_min: 15,
            tension_max: 50,
            tension_curve: [15, 22, 29, 34, 38, 42, 46, 50],
        },
        compiledMixingDirectives: "",
        showNewChapterModal: false,
        newChapterForm: {
            chapter_number: 1,
            title: "",
            chapter_goal: "",
            target_word_count: 3200,
            pacing_mode: "BALANCED",
            ending_hook_style: "CLIFFHANGER",
        },

        // Status Generasi & Streaming SSE per Micro-Beat
        isGeneratingBeats: false,
        streamingBeatId: null,
        streamStatusLabel: "",
        streamAbortController: null,
        extractingBeatId: null,
        autoExtractAfterStream: true,
        extractMode: "fast_local", // 'fast_local' (<1ms jaga KV Cache Slot 0) | 'auto' (LLM Extractor)
        activeBeatEditId: null,
        readerMode: false,
        readerFontSize: localStorage.getItem("zen_reader_size") || "md",
        beatAutoSaveTimers: {},
        beatSaveStatus: {}, // beatId -> 'saving' | 'saved' | 'error'

        // Produktivitas Penulis: Target Kata Harian, Cari & Ganti, Modal Ekspor
        dailyGoalWords: Number(localStorage.getItem("zen_daily_goal_words") || 1000),
        todayWordsWritten: 0,
        showFindReplaceBar: false,
        findQuery: "",
        replaceQuery: "",
        findCaseSensitive: false,
        showExportModal: false,
        exportOptions: {
            format: "epub",
            author_name: "",
            approved_only: false,
            include_synopsis: true,
            include_codex_appendix: true,
        },

        // Modal 4-Tier Memory & FTS5 Inspector
        showMemoryInspectorModal: false,
        memoryInspectorData: null,

        // Sampler Parameters (Otomatis disesuaikan saat memakai model 3B vs 7B+)
        samplerConfig: {
            endpoint_mode: "chat",
            temperature: 0.75,
            min_p: 0.06,
            dry_multiplier: 0.50,
            xtc_probability: 0.0,
            additional_author_note: "",
        },

        // Modal Riwayat Revisi Beat
        showRevisionModal: false,
        revisionBeatTarget: null,
        beatRevisions: [],

        // Modal Dual/Multi-Model Runtime Switcher & Downloader (/api/models)
        showModelModal: false,
        modelModalTab: "local", // 'local' | 'catalog' | 'custom'
        isSwitchingModel: false,
        isSubmittingCustomModel: false,
        modelPollTimer: null,
        modelRuntime: {
            llama_binary_installed: false,
            llama_server_online: false,
            active_model_filename: null,
            models_dir: "",
            downloads_dir: "",
            local_models: [],
            downloads_gguf: [],
            curated_catalog: [],
            custom_download_jobs: [],
            total_cpu_cores: 2,
        },
        customModelForm: {
            url_or_repo: "",
            filename: "",
            display_name: "",
            notes: "",
        },
        // Konfigurasi API Model Online / Sumber Kompatibel Lain (/api/ai/provider)
        aiProviderPresets: [],
        aiProviderSummary: {
            provider_type: "local_llama",
            preset_id: "local_llama",
            display_name: "Lokal llama-server (GGUF)",
            has_api_key: false,
            api_key_masked: "",
            model_name: "",
            base_url: "",
        },
        aiProviderForm: {
            provider_type: "openai_compatible",
            preset_id: "openrouter",
            display_name: "OpenRouter (Banyak Model & Gratis Tier)",
            base_url: "https://openrouter.ai/api/v1",
            model_name: "",
            api_key: "",
            stop_local_llama: true,
        },
        showAdvancedProviderOptions: false,
        remoteFetchedModels: [],
        isFetchingRemoteModels: false,
        isTestingProvider: false,
        isSavingProvider: false,
        providerTestResult: null,

        _numOr(val, fallback) {
            const n = Number(val);
            return Number.isFinite(n) ? n : fallback;
        },

        // ====================================================================
        // LIFECYCLE INITIALIZATION
        // ====================================================================
        async init() {
            this.applyTheme();
            this.loadDailyWordTracker();
            await Promise.all([this.fetchSystemHealth(), this.loadModelsStatus(), this.loadAiProviderConfig()]);
            this.ramPollTimer = setInterval(() => {
                if (!document.hidden) {
                    this.fetchSystemHealth();
                }
            }, 5000);

            document.addEventListener("visibilitychange", () => {
                if (!document.hidden) {
                    this.fetchSystemHealth();
                }
            });

            // Pengaman agar suntingan belum tersimpan atau streaming aktif tidak hilang saat menutup tab
            window.addEventListener("beforeunload", (e) => {
                const hasPendingTimers = Object.keys(this.beatAutoSaveTimers || {}).length > 0;
                if (hasPendingTimers) {
                    this.flushPendingBeatSaves();
                }
                if (this.streamingBeatId || hasPendingTimers) {
                    e.preventDefault();
                    e.returnValue = "";
                }
            });

            // Shortcut Keyboard (Alt+Z Zen Mode, Alt+R Mode Baca, Alt+F Cari & Ganti)
            window.addEventListener("keydown", (e) => {
                if (e.altKey && e.key.toLowerCase() === "z") {
                    e.preventDefault();
                    this.toggleZenMode();
                } else if (e.altKey && e.key.toLowerCase() === "r") {
                    e.preventDefault();
                    this.readerMode = !this.readerMode;
                } else if (e.altKey && e.key.toLowerCase() === "f") {
                    e.preventDefault();
                    this.showFindReplaceBar = !this.showFindReplaceBar;
                }
            });

            await this.loadProjects();
        },

        _todayIsoDate() {
            const d = new Date();
            const yyyy = d.getFullYear();
            const mm = String(d.getMonth() + 1).padStart(2, "0");
            const dd = String(d.getDate()).padStart(2, "0");
            return `${yyyy}-${mm}-${dd}`;
        },

        loadDailyWordTracker() {
            const key = `zen_daily_words_${this._todayIsoDate()}`;
            this.todayWordsWritten = Math.max(0, Number(localStorage.getItem(key) || 0));
        },

        recordDailyWordsDelta(deltaWords) {
            const delta = Math.round(Number(deltaWords) || 0);
            if (delta <= 0) return;
            this.todayWordsWritten += delta;
            localStorage.setItem(`zen_daily_words_${this._todayIsoDate()}`, String(this.todayWordsWritten));
        },

        updateDailyGoalPrompt() {
            const raw = prompt("Masukkan target kata harian Anda (misal 1000):", String(this.dailyGoalWords || 1000));
            if (raw === null) return;
            const parsed = Math.max(100, Math.min(20000, Number(raw) || 1000));
            this.dailyGoalWords = parsed;
            localStorage.setItem("zen_daily_goal_words", String(parsed));
            this.notify(`Target kata harian disetel ke ${parsed.toLocaleString("id-ID")} kata.`, "success");
        },

        setReaderFontSize(size) {
            this.readerFontSize = size;
            localStorage.setItem("zen_reader_size", size);
        },

        applyTheme() {
            if (this.darkMode) {
                document.documentElement.classList.add("dark");
                localStorage.setItem("zen_novel_theme", "dark");
            } else {
                document.documentElement.classList.remove("dark");
                localStorage.setItem("zen_novel_theme", "light");
            }
        },

        toggleTheme() {
            this.darkMode = !this.darkMode;
            this.applyTheme();
        },

        toggleZenMode() {
            this.zenMode = !this.zenMode;
            if (this.zenMode) {
                this.leftDrawerOpen = false;
                this.rightDrawerOpen = false;
                this.notify("Zen Mode Aktif (Tekan Alt+Z untuk kembali)", "info");
            } else {
                this.leftDrawerOpen = window.innerWidth >= 1024;
                this.rightDrawerOpen = window.innerWidth >= 1280;
            }
        },

        notify(message, type = "info") {
            if (this.toast.timer) clearTimeout(this.toast.timer);
            this.toast.message = message;
            this.toast.type = type;
            this.toast.visible = true;
            this.toast.timer = setTimeout(() => {
                this.toast.visible = false;
            }, 4200);
        },

        async apiRequest(path, options = {}) {
            const headers = {
                "Content-Type": "application/json",
                ...(options.headers || {}),
            };
            const response = await fetch(`${this.apiBase}${path}`, {
                ...options,
                headers,
            });
            if (!response.ok) {
                let errDetail = `HTTP ${response.status}`;
                try {
                    const errJson = await response.json();
                    errDetail = errJson.detail || JSON.stringify(errJson);
                } catch (_) {
                    errDetail = await response.text();
                }
                throw new Error(errDetail);
            }
            return await response.json();
        },

        async fetchSystemHealth() {
            try {
                const data = await this.apiRequest("/api/system/health");
                this.systemHealth = data;
            } catch (_) {
                try {
                    const ram = await this.apiRequest("/api/system/ram");
                    this.systemHealth.ram = ram;
                } catch (__) {
                    // Biarkan status terakhir jika sedang offline
                }
            }
        },

        // ====================================================================
        // PROJECTS & STORY BIBLE MANAGEMENT
        // ====================================================================
        async loadProjects() {
            try {
                this.projects = await this.apiRequest("/api/projects");
                if (this.projects.length === 0) {
                    // Buat project sampel awal agar langsung siap digunakan saat pertama kali dibuka
                    const seeded = await this.apiRequest("/api/projects", {
                        method: "POST",
                        body: JSON.stringify({
                            title: "Senja di Pelabuhan Sunda",
                            genre: "Historical Literary Mystery",
                            logline: "Seorang juru tulis pelabuhan menemukan manifes kapal yang sengaja dibakar untuk menutupi penyelundupan senjata kolonial.",
                            main_objective: "Mengungkap dalang sindikat dermaga tanpa kehilangan nyawa dan menjaga bukti buku sandi.",
                            pov_style: "Third-Person Limited",
                            tense_style: "Lampau / Past Narrative",
                            tone_style: "Atmosferik, Imersif, Show Dont Tell, Puitis Tajam",
                            style_sample: "Lentera minyak di ujung dermaga berayun pelan, memantulkan kilau kuning pucat di atas genangan air asin yang berbau cengkeh basah dan karat besi.",
                            total_planned_chapters: 24,
                            default_chapter_words: 3200,
                            active_model_profile: "Qwen2.5-3B-Instruct-Q4_K_M",
                            seed_default_phases: true,
                        }),
                    });
                    // Tambahkan 2 entitas Codex awal (Karakter POV & Lokasi)
                    await this.apiRequest(`/api/projects/${seeded.id}/codex`, {
                        method: "POST",
                        body: JSON.stringify({
                            category: "CHARACTER",
                            name: "Arya Wiratmaja",
                            aliases_and_tags: "Arya, Juru Tulis",
                            keywords_csv: "Arya, juru tulis, buku sandi, tinta, pelabuhan",
                            is_pinned: 1,
                            core_description: "Juru tulis muda di kantor syahbandar yang memiliki ingatan fotografis terhadap angka dan tulisan tangan.",
                            speech_style: "Tenang, hemat kata, memilih diksi formal namun menyimpan ironi halus.",
                            current_state: {
                                location: "Kantor Syahbandar Lama",
                                condition: "Sehat, lengan baju basah oleh hujan",
                                emotional_state: "Waspada & curiga",
                                knowledge: "Menemukan halaman manifes nomor 14 yang robek",
                            },
                        }),
                    });
                    await this.apiRequest(`/api/projects/${seeded.id}/codex`, {
                        method: "POST",
                        body: JSON.stringify({
                            category: "LOCATION",
                            name: "Gudang Cengkeh Nomor 4",
                            aliases_and_tags: "Gudang 4, Dermaga Barat",
                            keywords_csv: "gudang, cengkeh, dermaga barat, gembok kuningan",
                            is_pinned: 1,
                            core_description: "Gudang kayu jati tua beratap seng berkarat di Dermaga Barat. Lembap, penuh karung rempah dan bayangan tiang pancang.",
                            speech_style: "",
                            current_state: {
                                location: "Dermaga Barat",
                                condition: "Terkunci dari luar saat jam malam",
                                emotional_state: "Gelap dan pengap",
                                knowledge: "Tempat penyimpanan peti kayu tanpa cap resmi",
                            },
                        }),
                    });
                    await this.apiRequest(`/api/projects/${seeded.id}/codex`, {
                        method: "POST",
                        body: JSON.stringify({
                            category: "WORLD_RULE",
                            name: "Aturan Jam Malam Pelabuhan 1892",
                            aliases_and_tags: "Patroli Lentera Merah",
                            keywords_csv: "jam malam, patroli, lentera merah, lonceng",
                            is_pinned: 1,
                            core_description: "Setiap pukul sepuluh malam lonceng menara berbunyi tiga kali; siapa pun di dermaga tanpa surat jalan berlapis segel lilin akan ditangkap patroli.",
                        }),
                    });
                    await this.apiRequest(`/api/projects/${seeded.id}/chapters`, {
                        method: "POST",
                        body: JSON.stringify({
                            chapter_number: 1,
                            title: "Abu di Sela Buku Manifes",
                            chapter_goal: "Arya memeriksa pembukuan malam hari saat hujan deras, menemukan sisa kertas manifes yang baru dibakar di tungku belakang, lalu menyelinap menuju Gudang Cengkeh Nomor 4 sebelum patroli tiba.",
                            target_word_count: 2400,
                            pacing_mode: "SLOW_BURN",
                            mix_world_building: 65,
                            mix_psychology: 60,
                            mix_sensory: 80,
                            mix_dialogue: 35,
                            mix_action: 30,
                            ending_hook_style: "CLIFFHANGER",
                        }),
                    });
                    this.projects = await this.apiRequest("/api/projects");
                }
                if (this.projects.length > 0) {
                    const lastPid = localStorage.getItem("zen_last_project_id");
                    const chosen = this.projects.find((p) => p.id === lastPid) || this.projects[0];
                    await this.selectProject(chosen.id);
                }
            } catch (err) {
                this.notify(`Gagal memuat project: ${err.message}`, "error");
            }
        },

        async selectProject(projectId) {
            if (!projectId) return;
            try {
                await this.flushPendingBeatSaves();
                this.activeProjectId = projectId;
                localStorage.setItem("zen_last_project_id", projectId);
                const proj = await this.apiRequest(`/api/projects/${projectId}`);
                if (!proj.author_name) proj.author_name = "Penulis Studio";
                this.activeProject = proj;
                this.bannedPhrasesText = (proj.banned_phrases || []).join(", ");

                await Promise.all([
                    this.loadPhases(),
                    this.loadCodex(),
                    this.loadChapters(),
                ]);
            } catch (err) {
                this.notify(`Gagal membuka project: ${err.message}`, "error");
            }
        },

        async createNewProject() {
            if (!this.newProjectForm.title.trim() || !this.newProjectForm.main_objective.trim()) {
                this.notify("Judul dan Tujuan Utama (North Star) wajib diisi.", "warning");
                return;
            }
            try {
                const created = await this.apiRequest("/api/projects", {
                    method: "POST",
                    body: JSON.stringify({
                        ...this.newProjectForm,
                        seed_default_phases: true,
                    }),
                });
                this.projects.unshift(created);
                this.showNewProjectModal = false;
                await this.selectProject(created.id);
                this.notify(`Novel "${created.title}" berhasil dibuat beserta 6 Fase Struktur!`, "success");
            } catch (err) {
                this.notify(`Gagal membuat project: ${err.message}`, "error");
            }
        },

        async saveStoryBible() {
            if (!this.activeProjectId) return;
            try {
                const phrasesArray = this.bannedPhrasesText
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean);

                const updated = await this.apiRequest(`/api/projects/${this.activeProjectId}`, {
                    method: "PUT",
                    body: JSON.stringify({
                        title: this.activeProject.title,
                        author_name: this.activeProject.author_name || "Penulis Studio",
                        genre: this.activeProject.genre,
                        logline: this.activeProject.logline,
                        main_objective: this.activeProject.main_objective,
                        pov_style: this.activeProject.pov_style,
                        tense_style: this.activeProject.tense_style,
                        tone_style: this.activeProject.tone_style,
                        style_sample: this.activeProject.style_sample,
                        banned_phrases: phrasesArray,
                        total_planned_chapters: Number(this.activeProject.total_planned_chapters) || 24,
                        default_chapter_words: Number(this.activeProject.default_chapter_words) || 3200,
                        rolling_global_summary: this.activeProject.rolling_global_summary,
                        active_model_profile: this.activeProject.active_model_profile,
                    }),
                });
                this.activeProject = updated;
                const idx = this.projects.findIndex((p) => p.id === updated.id);
                if (idx !== -1) this.projects[idx] = updated;
                this.notify("Core Compass & Story Bible berhasil disimpan ke SQLite!", "success");
            } catch (err) {
                this.notify(`Gagal menyimpan Story Bible: ${err.message}`, "error");
            }
        },

        async deleteActiveProject() {
            if (!this.activeProjectId || !this.activeProject) return;
            const title = this.activeProject.title || "Proyek Ini";
            if (!confirm(`Hapus PERMANEN proyek "${title}" beserta seluruh Bab, Beat, & Codex-nya? Tindakan ini tidak bisa dibatalkan!`)) {
                return;
            }
            if (this.projects.length <= 1) {
                if (!confirm("Ini adalah satu-satunya proyek Anda saat ini. Setelah dihapus, proyek Starter baru akan dibuat otomatis jika daftar kosong. Lanjutkan hapus?")) {
                    return;
                }
            }
            try {
                const deletedId = this.activeProjectId;
                await this.apiRequest(`/api/projects/${deletedId}`, { method: "DELETE" });
                localStorage.removeItem(`zen_last_chapter_id_${deletedId}`);
                this.activeProjectId = null;
                this.activeChapterId = null;
                this.activeChapter = null;
                this.beats = [];
                this.notify(`Novel "${title}" telah dihapus.`, "info");
                await this.loadProjects();
            } catch (err) {
                this.notify(`Gagal menghapus novel: ${err.message}`, "error");
            }
        },

        async restoreProjectFromBackupFile(event) {
            const file = event?.target?.files?.[0];
            if (!file) return;
            this.isRestoringBackup = true;
            try {
                const rawText = await file.text();
                const parsed = JSON.parse(rawText);
                const restored = await this.apiRequest("/api/projects/restore", {
                    method: "POST",
                    body: JSON.stringify(parsed),
                });
                this.projects.unshift(restored);
                this.showNewProjectModal = false;
                await this.selectProject(restored.id);
                this.notify(`Backup "${restored.title}" berhasil dipulihkan utuh ke SQLite!`, "success");
            } catch (err) {
                this.notify(`Gagal memulihkan backup JSON: ${err.message}`, "error");
            } finally {
                this.isRestoringBackup = false;
                if (event?.target) event.target.value = "";
            }
        },

        // ====================================================================
        // 1. INTERACTIVE PHASE-RANGE TIMELINE BAR (ATAS)
        // ====================================================================
        async loadPhases() {
            if (!this.activeProjectId) return;
            this.phases = await this.apiRequest(`/api/projects/${this.activeProjectId}/phases`);
            this.syncSelectedPhaseWithActiveChapter();
        },

        syncSelectedPhaseWithActiveChapter() {
            if (!this.phases.length) {
                this.selectedPhase = null;
                return;
            }
            if (this.activeChapter) {
                const match = this.phases.find(
                    (p) =>
                        this.activeChapter.chapter_number >= p.start_chapter &&
                        this.activeChapter.chapter_number <= p.end_chapter
                );
                if (match) {
                    this.selectedPhase = match;
                    return;
                }
            }
            this.selectedPhase = this.phases[0];
        },

        selectPhaseOnTimeline(phase) {
            this.selectedPhase = phase;
            // Jika ada bab di rentang fase ini dan bab aktif berada di luar fase ini, tawarkan fokus
            const chapterInPhase = this.chapters.find(
                (c) => c.chapter_number >= phase.start_chapter && c.chapter_number <= phase.end_chapter
            );
            if (chapterInPhase && (!this.activeChapter || this.activeChapter.id !== chapterInPhase.id)) {
                this.selectChapter(chapterInPhase.id);
            }
        },

        isPhaseActiveForCurrentChapter(phase) {
            if (!this.activeChapter) return false;
            return (
                this.activeChapter.chapter_number >= phase.start_chapter &&
                this.activeChapter.chapter_number <= phase.end_chapter
            );
        },

        openNewPhaseModal() {
            const nextOrder = this.phases.length + 1;
            const lastEnd = this.phases.length
                ? Math.max(...this.phases.map((p) => p.end_chapter))
                : 0;
            this.editingPhaseId = null;
            this.phaseForm = {
                phase_order: nextOrder,
                phase_name: `Fase ${nextOrder}: Pengembangan Baru`,
                start_chapter: lastEnd + 1,
                end_chapter: lastEnd + 4,
                default_pacing: "BALANCED",
                tension_min: 30,
                tension_max: 65,
                building_focus: "Pengembangan konflik dan pendalaman hubungan karakter.",
                phase_guardrails: "Jangan membuka klimaks utama sebelum bab akhir fase ini.",
            };
            this.showPhaseModal = true;
        },

        openEditPhaseModal(phase) {
            this.editingPhaseId = phase.id;
            this.phaseForm = {
                phase_order: phase.phase_order,
                phase_name: phase.phase_name,
                start_chapter: phase.start_chapter,
                end_chapter: phase.end_chapter,
                default_pacing: phase.default_pacing || "BALANCED",
                tension_min: phase.tension_min,
                tension_max: phase.tension_max,
                building_focus: phase.building_focus,
                phase_guardrails: phase.phase_guardrails,
            };
            this.showPhaseModal = true;
        },

        async savePhaseForm() {
            if (!this.activeProjectId) return;
            try {
                const payload = {
                    ...this.phaseForm,
                    phase_order: Number(this.phaseForm.phase_order),
                    start_chapter: Number(this.phaseForm.start_chapter),
                    end_chapter: Number(this.phaseForm.end_chapter),
                    tension_min: Number(this.phaseForm.tension_min),
                    tension_max: Number(this.phaseForm.tension_max),
                };

                if (this.editingPhaseId) {
                    await this.apiRequest(`/api/phases/${this.editingPhaseId}`, {
                        method: "PUT",
                        body: JSON.stringify(payload),
                    });
                    this.notify("Rentang Fase & Guardrails diperbarui!", "success");
                } else {
                    await this.apiRequest(`/api/projects/${this.activeProjectId}/phases`, {
                        method: "POST",
                        body: JSON.stringify(payload),
                    });
                    this.notify("Fase baru berhasil ditambahkan ke garis waktu!", "success");
                }

                this.showPhaseModal = false;
                await this.loadPhases();
                if (this.activeChapterId) {
                    await this.selectChapter(this.activeChapterId);
                }
            } catch (err) {
                this.notify(`Gagal menyimpan Fase: ${err.message}`, "error");
            }
        },

        async deletePhase(phaseId) {
            if (!phaseId) return;
            try {
                await this.apiRequest(`/api/phases/${phaseId}`, { method: "DELETE" });
                this.showPhaseModal = false;
                await this.loadPhases();
                this.notify("Fase berhasil dihapus.", "info");
            } catch (err) {
                this.notify(`Gagal menghapus fase: ${err.message}`, "error");
            }
        },

        // ====================================================================
        // 2. CODEX & LOREBOOK + FTS5 BM25 LIVE SEARCH
        // ====================================================================
        async loadCodex() {
            if (!this.activeProjectId) return;
            this.codexItems = await this.apiRequest(`/api/projects/${this.activeProjectId}/codex`);
        },

        get filteredCodexItems() {
            if (this.codexFilterCategory === "ALL") return this.codexItems;
            return this.codexItems.filter((item) => item.category === this.codexFilterCategory);
        },

        get characterCodexList() {
            return this.codexItems.filter((item) => item.category === "CHARACTER");
        },

        get locationCodexList() {
            return this.codexItems.filter((item) => item.category === "LOCATION");
        },

        async runBm25Search() {
            if (!this.activeProjectId || !this.bm25SearchQuery.trim()) {
                this.bm25SearchResults = { codex_matches: [], episodic_memories: [] };
                return;
            }
            this.isSearchingBm25 = true;
            try {
                const q = encodeURIComponent(this.bm25SearchQuery.trim());
                this.bm25SearchResults = await this.apiRequest(
                    `/api/projects/${this.activeProjectId}/codex/search?q=${q}&limit=8`
                );
            } catch (err) {
                this.notify(`Pencarian FTS5 gagal: ${err.message}`, "error");
            } finally {
                this.isSearchingBm25 = false;
            }
        },

        openNewCodexModal(defaultCategory = "CHARACTER") {
            this.editingCodexId = null;
            this.codexForm = {
                category: defaultCategory,
                name: "",
                aliases_and_tags: "",
                keywords_csv: "",
                is_pinned: defaultCategory === "WORLD_RULE" ? 1 : 0,
                core_description: "",
                speech_style: "",
                current_state: {
                    location: "",
                    condition: "Sehat",
                    emotional_state: "Stabil",
                    knowledge: "",
                },
            };
            this.showCodexModal = true;
        },

        openEditCodexModal(item) {
            this.editingCodexId = item.id;
            const st = item.current_state || {};
            this.codexForm = {
                category: item.category || "CHARACTER",
                name: item.name || "",
                aliases_and_tags: item.aliases_and_tags || "",
                keywords_csv: item.keywords_csv || "",
                is_pinned: item.is_pinned ? 1 : 0,
                core_description: item.core_description || "",
                speech_style: item.speech_style || "",
                current_state: {
                    location: st.location || "",
                    condition: st.condition || "Sehat",
                    emotional_state: st.emotional_state || "Stabil",
                    knowledge: st.knowledge || "",
                },
            };
            this.showCodexModal = true;
        },

        async saveCodexForm() {
            if (!this.activeProjectId) return;
            if (!this.codexForm.name.trim() || !this.codexForm.core_description.trim()) {
                this.notify("Nama entitas dan deskripsi inti wajib diisi.", "warning");
                return;
            }
            try {
                const payload = {
                    ...this.codexForm,
                    is_pinned: this.codexForm.is_pinned ? 1 : 0,
                };
                if (this.editingCodexId) {
                    await this.apiRequest(`/api/codex/${this.editingCodexId}`, {
                        method: "PUT",
                        body: JSON.stringify(payload),
                    });
                    this.notify(`Entitas Codex "${payload.name}" diperbarui & diindeks ke FTS5!`, "success");
                } else {
                    await this.apiRequest(`/api/projects/${this.activeProjectId}/codex`, {
                        method: "POST",
                        body: JSON.stringify(payload),
                    });
                    this.notify(`Entitas Codex "${payload.name}" ditambahkan ke SQLite FTS5!`, "success");
                }
                this.showCodexModal = false;
                await this.loadCodex();
            } catch (err) {
                this.notify(`Gagal menyimpan Codex: ${err.message}`, "error");
            }
        },

        async deleteCodex(codexId) {
            if (!codexId) return;
            try {
                await this.apiRequest(`/api/codex/${codexId}`, { method: "DELETE" });
                this.showCodexModal = false;
                await this.loadCodex();
                this.notify("Entitas Codex dihapus.", "info");
            } catch (err) {
                this.notify(`Gagal menghapus Codex: ${err.message}`, "error");
            }
        },

        // ====================================================================
        // 3 & 4. CHAPTERS, MIXING CONSOLE, & MICRO-BEATS CANVAS
        // ====================================================================
        async loadChapters() {
            if (!this.activeProjectId) return;
            this.chapters = await this.apiRequest(`/api/projects/${this.activeProjectId}/chapters`);
            if (this.chapters.length > 0) {
                const rememberedId = localStorage.getItem(`zen_last_chapter_id_${this.activeProjectId}`);
                const targetId =
                    (this.activeChapterId && this.chapters.some((c) => c.id === this.activeChapterId) && this.activeChapterId) ||
                    (rememberedId && this.chapters.some((c) => c.id === rememberedId) && rememberedId) ||
                    this.chapters[0].id;
                await this.selectChapter(targetId);
            } else {
                this.activeChapterId = null;
                this.activeChapter = null;
                this.beats = [];
            }
        },

        async selectChapter(chapterId) {
            if (!chapterId) return;
            try {
                await this.flushPendingBeatSaves();
                this.activeChapterId = chapterId;
                if (this.activeProjectId) {
                    localStorage.setItem(`zen_last_chapter_id_${this.activeProjectId}`, chapterId);
                }
                const ch = await this.apiRequest(`/api/chapters/${chapterId}`);
                this.activeChapter = ch;
                this.beats = ch.beats || [];
                this.syncSelectedPhaseWithActiveChapter();
                await this.refreshChapterPacingPlan();

                // Jika bab belum punya Micro-Beats sama sekali, otomatis bangkitkan rencana awal
                if (this.beats.length === 0) {
                    await this.generateBeatPlan(true);
                }
            } catch (err) {
                this.notify(`Gagal memuat bab: ${err.message}`, "error");
            }
        },

        async navigateChapter(offset) {
            if (!this.chapters.length || !this.activeChapterId) return;
            const curIdx = this.chapters.findIndex((c) => c.id === this.activeChapterId);
            if (curIdx === -1) return;
            const nextIdx = curIdx + offset;
            if (nextIdx >= 0 && nextIdx < this.chapters.length) {
                await this.selectChapter(this.chapters[nextIdx].id);
            }
        },

        get hasPrevChapter() {
            const idx = this.chapters.findIndex((c) => c.id === this.activeChapterId);
            return idx > 0;
        },

        get hasNextChapter() {
            const idx = this.chapters.findIndex((c) => c.id === this.activeChapterId);
            return idx !== -1 && idx < this.chapters.length - 1;
        },

        openNewChapterModal() {
            const nextNum = this.chapters.length
                ? Math.max(...this.chapters.map((c) => c.chapter_number)) + 1
                : 1;
            const matchingPhase = this.phases.find(
                (p) => nextNum >= p.start_chapter && nextNum <= p.end_chapter
            );
            this.newChapterForm = {
                chapter_number: nextNum,
                title: `Bab ${nextNum}`,
                chapter_goal: "",
                target_word_count: this.activeProject.default_chapter_words || 3200,
                pacing_mode: matchingPhase ? matchingPhase.default_pacing : "BALANCED",
                ending_hook_style: "CLIFFHANGER",
            };
            this.showNewChapterModal = true;
        },

        async createNewChapter() {
            if (!this.activeProjectId) return;
            if (!this.newChapterForm.title.trim() || !this.newChapterForm.chapter_goal.trim()) {
                this.notify("Judul bab dan Tujuan Bab (Chapter Goal) wajib diisi.", "warning");
                return;
            }
            try {
                const created = await this.apiRequest(
                    `/api/projects/${this.activeProjectId}/chapters`,
                    {
                        method: "POST",
                        body: JSON.stringify({
                            ...this.newChapterForm,
                            chapter_number: Number(this.newChapterForm.chapter_number),
                            target_word_count: Number(this.newChapterForm.target_word_count) || 3200,
                        }),
                    }
                );
                this.showNewChapterModal = false;
                await this.loadChapters();
                await this.selectChapter(created.id);
                this.notify(`Bab ${created.chapter_number}: "${created.title}" berhasil dibuat!`, "success");
            } catch (err) {
                this.notify(`Gagal membuat bab: ${err.message}`, "error");
            }
        },

        async deleteActiveChapter() {
            if (!this.activeChapterId) return;
            try {
                await this.apiRequest(`/api/chapters/${this.activeChapterId}`, {
                    method: "DELETE",
                });
                this.activeChapterId = null;
                await this.loadChapters();
                this.notify("Bab berhasil dihapus.", "info");
            } catch (err) {
                this.notify(`Gagal menghapus bab: ${err.message}`, "error");
            }
        },

        async saveChapterConfig() {
            if (!this.activeChapter) return;
            try {
                const updated = await this.apiRequest(`/api/chapters/${this.activeChapter.id}`, {
                    method: "PUT",
                    body: JSON.stringify({
                        title: this.activeChapter.title,
                        chapter_goal: this.activeChapter.chapter_goal,
                        target_word_count: Number(this.activeChapter.target_word_count) || 3200,
                        pacing_mode: this.activeChapter.pacing_mode,
                        mix_world_building: Number(this.activeChapter.mix_world_building),
                        mix_psychology: Number(this.activeChapter.mix_psychology),
                        mix_sensory: Number(this.activeChapter.mix_sensory),
                        mix_dialogue: Number(this.activeChapter.mix_dialogue),
                        mix_action: Number(this.activeChapter.mix_action),
                        ending_hook_style: this.activeChapter.ending_hook_style,
                        chapter_summary: this.activeChapter.chapter_summary,
                        status: this.activeChapter.status,
                    }),
                });
                this.activeChapter = { ...updated, beats: this.beats };
                const idx = this.chapters.findIndex((c) => c.id === updated.id);
                if (idx !== -1) this.chapters[idx] = updated;
                await this.refreshChapterPacingPlan();
                this.notify("Konfigurasi Chapter Mixing Console disimpan!", "success");
            } catch (err) {
                this.notify(`Gagal menyimpan konfigurasi bab: ${err.message}`, "error");
            }
        },

        async refreshChapterPacingPlan() {
            if (!this.activeChapter) return;
            try {
                const res = await this.apiRequest(
                    `/api/chapters/${this.activeChapter.id}/calculate-plan`
                );
                this.pacingPlan = res.plan;
                this.compiledMixingDirectives = res.mixing_directives;
            } catch (_) {
                // Kalkulasi instan lokal jika belum tersimpan
            }
        },

        // Kalkulasi instan saat penulis menggeser target kata di Right Drawer
        get liveCalculatedBeatCount() {
            if (!this.activeChapter) return 8;
            const words = Math.max(350, Number(this.activeChapter.target_word_count) || 3200);
            return Math.max(1, Math.round(words / 400));
        },

        get liveWordsPerBeat() {
            if (!this.activeChapter) return 400;
            const words = Math.max(350, Number(this.activeChapter.target_word_count) || 3200);
            return Math.round(words / this.liveCalculatedBeatCount);
        },

        get actualChapterWordCount() {
            return this.beats.reduce((acc, b) => acc + (Number(b.actual_words) || 0), 0);
        },

        get totalProjectWordCount() {
            return (this.chapters || []).reduce((acc, ch) => {
                if (ch.id === this.activeChapterId) {
                    return acc + this.actualChapterWordCount;
                }
                return acc + (Number(ch.current_word_count) || 0);
            }, 0);
        },

        get totalProjectPlannedWords() {
            const chCount = Math.max(1, Number(this.activeProject?.total_planned_chapters) || 24);
            const chWords = Math.max(400, Number(this.activeProject?.default_chapter_words) || 3200);
            return chCount * chWords;
        },

        get dailyGoalProgressPercent() {
            const goal = Math.max(100, Number(this.dailyGoalWords) || 1000);
            return Math.min(100, Math.round((this.todayWordsWritten / goal) * 100));
        },

        get wordBudgetProgressPercent() {
            if (!this.activeChapter || !this.activeChapter.target_word_count) return 0;
            return Math.min(
                100,
                Math.round((this.actualChapterWordCount / this.activeChapter.target_word_count) * 100)
            );
        },

        syncActiveChapterWordCountCache() {
            if (!this.activeChapterId) return;
            const total = this.actualChapterWordCount;
            if (this.activeChapter) {
                this.activeChapter.current_word_count = total;
            }
            const idx = this.chapters.findIndex((c) => c.id === this.activeChapterId);
            if (idx !== -1) {
                this.chapters[idx].current_word_count = total;
            }
        },

        async generateBeatPlan(silent = false) {
            if (!this.activeChapter) return;
            const hasWrittenProse = this.beats.some(
                (b) => (b.generated_prose || "").trim().length > 0
            );
            if (
                !silent &&
                hasWrittenProse &&
                !confirm(
                    "Bab ini sudah memiliki naskah prosa yang ditulis! Menyusun ulang Beat Plan akan mengganti kartu beat yang ada di bab ini. Lanjutkan?"
                )
            ) {
                return;
            }
            this.isGeneratingBeats = true;
            try {
                // Pastikan perubahan slider/target kata disimpan lebih dulu
                await this.apiRequest(`/api/chapters/${this.activeChapter.id}`, {
                    method: "PUT",
                    body: JSON.stringify({
                        title: this.activeChapter.title,
                        chapter_goal: this.activeChapter.chapter_goal,
                        target_word_count: this._numOr(this.activeChapter.target_word_count, 3200),
                        pacing_mode: this.activeChapter.pacing_mode,
                        mix_world_building: this._numOr(this.activeChapter.mix_world_building, 50),
                        mix_psychology: this._numOr(this.activeChapter.mix_psychology, 50),
                        mix_sensory: this._numOr(this.activeChapter.mix_sensory, 70),
                        mix_dialogue: this._numOr(this.activeChapter.mix_dialogue, 40),
                        mix_action: this._numOr(this.activeChapter.mix_action, 30),
                        ending_hook_style: this.activeChapter.ending_hook_style,
                    }),
                });

                const res = await this.apiRequest(
                    `/api/chapters/${this.activeChapter.id}/generate-beats`,
                    { method: "POST" }
                );
                this.beats = res.beats || [];
                this.pacingPlan = res.pacing_plan || this.pacingPlan;
                if (!silent) {
                    const srcLabel =
                        res.generation_source === "llama_server_architect"
                            ? "AI Plot Architect (llama-server)"
                            : "Deterministic Pacing Engine";
                    this.notify(
                        `Berhasil menyusun ${this.beats.length} Micro-Beats via ${srcLabel}!`,
                        "success"
                    );
                }
            } catch (err) {
                this.notify(`Gagal menyusun Micro-Beats: ${err.message}`, "error");
            } finally {
                this.isGeneratingBeats = false;
            }
        },

        async addSingleBeat() {
            if (!this.activeChapter) return;
            try {
                const created = await this.apiRequest(`/api/chapters/${this.activeChapter.id}/beats`, {
                    method: "POST",
                    body: JSON.stringify({
                        target_words: this.liveWordsPerBeat || 400,
                        tension_level: 45,
                    }),
                });
                this.beats.push(created);
                this.notify(`Beat #${created.beat_number} ditambahkan.`, "success");
            } catch (err) {
                this.notify(`Gagal menambah Beat: ${err.message}`, "error");
            }
        },

        async deleteSingleBeat(beat) {
            if (!beat || !beat.id) return;
            if ((beat.generated_prose || "").trim().length > 0) {
                if (!confirm(`Hapus Beat #${beat.beat_number} beserta ${beat.actual_words || 0} kata prosanya?`)) {
                    return;
                }
            }
            try {
                await this.apiRequest(`/api/beats/${beat.id}`, { method: "DELETE" });
                this.beats = await this.apiRequest(`/api/chapters/${this.activeChapter.id}/beats`);
                this.syncActiveChapterWordCountCache();
                this.notify(`Beat #${beat.beat_number} dihapus.`, "info");
            } catch (err) {
                this.notify(`Gagal menghapus Beat: ${err.message}`, "error");
            }
        },

        async moveBeat(beat, direction) {
            if (!beat || !beat.id || this.streamingBeatId) return;
            try {
                await this.flushPendingBeatSaves();
                this.beats = await this.apiRequest(`/api/beats/${beat.id}/move`, {
                    method: "POST",
                    body: JSON.stringify({ direction }),
                });
                this.notify(
                    `Urutan Beat dipindahkan ke ${direction === "up" ? "atas" : "bawah"}.`,
                    "info"
                );
            } catch (err) {
                this.notify(`Gagal memindahkan posisi Beat: ${err.message}`, "error");
            }
        },

        async setBeatStatus(beat, newStatus) {
            if (!beat || !beat.id) return;
            try {
                const updated = await this.apiRequest(`/api/beats/${beat.id}`, {
                    method: "PATCH",
                    body: JSON.stringify({ status: newStatus }),
                });
                const idx = this.beats.findIndex((b) => b.id === beat.id);
                if (idx !== -1) this.beats[idx] = updated;
                this.notify(`Status Beat #${beat.beat_number} diubah menjadi ${newStatus}.`, "success");
            } catch (err) {
                this.notify(`Gagal mengubah status Beat: ${err.message}`, "error");
            }
        },

        async saveBeatMetadata(beat, silent = false) {
            if (!beat || !beat.id) return;
            try {
                const updated = await this.apiRequest(`/api/beats/${beat.id}`, {
                    method: "PUT",
                    body: JSON.stringify({
                        pov_character_id: beat.pov_character_id || null,
                        location_id: beat.location_id || null,
                        tension_level: this._numOr(beat.tension_level, 35),
                        target_words: this._numOr(beat.target_words, 400),
                        beat_instruction: beat.beat_instruction,
                        stopping_point: beat.stopping_point,
                        sensory_anchor: beat.sensory_anchor,
                        conflict_focus: beat.conflict_focus,
                    }),
                });
                const idx = this.beats.findIndex((b) => b.id === beat.id);
                if (idx !== -1) this.beats[idx] = updated;
                if (!silent) {
                    this.notify(`Instruksi Beat #${beat.beat_number} disimpan!`, "success");
                }
            } catch (err) {
                this.notify(`Gagal menyimpan Beat: ${err.message}`, "error");
            }
        },

        async flushPendingBeatSaves() {
            const entries = Object.entries(this.beatAutoSaveTimers || {});
            if (entries.length === 0) return;
            for (const [beatId, timer] of entries) {
                clearTimeout(timer);
                delete this.beatAutoSaveTimers[beatId];
                const beat = this.beats.find((b) => b.id === beatId);
                if (!beat) continue;
                try {
                    await this.apiRequest(`/api/beats/${beatId}`, {
                        method: "PATCH",
                        body: JSON.stringify({
                            generated_prose: beat.generated_prose || "",
                        }),
                    });
                    this.beatSaveStatus[beatId] = "saved";
                } catch (_) {
                    this.beatSaveStatus[beatId] = "error";
                }
            }
            this.syncActiveChapterWordCountCache();
        },

        scheduleAutoSaveBeat(beat) {
            if (!beat || !beat.id || this.streamingBeatId === beat.id) return;
            const prevWords = Number(beat.actual_words) || 0;
            const newWords = this.countWordsClient(beat.generated_prose);
            beat.actual_words = newWords;
            if (newWords > prevWords) {
                this.recordDailyWordsDelta(newWords - prevWords);
            }
            if (newWords > 0 && beat.status === "PENDING") {
                beat.status = "COMPLETED";
            }
            this.syncActiveChapterWordCountCache();
            this.beatSaveStatus[beat.id] = "saving";
            if (this.beatAutoSaveTimers[beat.id]) {
                clearTimeout(this.beatAutoSaveTimers[beat.id]);
            }
            this.beatAutoSaveTimers[beat.id] = setTimeout(async () => {
                delete this.beatAutoSaveTimers[beat.id];
                try {
                    await this.apiRequest(`/api/beats/${beat.id}`, {
                        method: "PATCH",
                        body: JSON.stringify({
                            generated_prose: beat.generated_prose || "",
                            status: beat.status || "COMPLETED",
                        }),
                    });
                    this.beatSaveStatus[beat.id] = "saved";
                } catch (_) {
                    this.beatSaveStatus[beat.id] = "error";
                }
            }, 1500);
        },

        // ====================================================================
        // SSE STREAMING GENERATION PER MICRO-BEAT (/api/beats/{id}/stream)
        // ====================================================================
        async streamWriteBeat(beat) {
            if (!beat || !beat.id || this.streamingBeatId) return;

            const rawExistingProse = beat.generated_prose || "";
            const existingProse = rawExistingProse.trim();
            const wordsBeforeStream = Number(beat.actual_words) || 0;

            this.streamingBeatId = beat.id;
            this.streamStatusLabel = "⏳ Menyimpan instruksi & menyiapkan Memori 4-Tier...";
            this.streamAbortController = new AbortController();

            // Pengaman naskah: simpan otomatis versi sebelumnya sebelum Rewrite
            if (existingProse.length > 0) {
                try {
                    await this.apiRequest(`/api/beats/${beat.id}/revisions`, {
                        method: "POST",
                        body: JSON.stringify({
                            prose_content: rawExistingProse,
                            revision_note: "Auto-Snapshot Sebelum Rewrite",
                        }),
                    });
                } catch (_) {
                    // Tetap lanjutkan bila gagal membuat snapshot opsional
                }
            }

            // Simpan instruksi beat terkini secara senyap sebelum mulai streaming
            await this.saveBeatMetadata(beat, true);
            this.streamStatusLabel = "⏳ Menghubungkan ke Single-Slot AI (Port 8080)...";

            const beatIndex = this.beats.findIndex((b) => b.id === beat.id);
            if (beatIndex !== -1) {
                this.beats[beatIndex].generated_prose = "";
                this.beats[beatIndex].status = "STREAMING";
            }

            try {
                const response = await fetch(`${this.apiBase}/api/beats/${beat.id}/stream`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        endpoint_mode: this.samplerConfig.endpoint_mode,
                        temperature: this._numOr(this.samplerConfig.temperature, 0.75),
                        min_p: this._numOr(this.samplerConfig.min_p, 0.06),
                        dry_multiplier: this._numOr(this.samplerConfig.dry_multiplier, 0.50),
                        xtc_probability: this._numOr(this.samplerConfig.xtc_probability, 0.0),
                        additional_author_note: this.samplerConfig.additional_author_note || "",
                        save_on_complete: true,
                    }),
                    signal: this.streamAbortController.signal,
                });

                if (!response.ok || !response.body) {
                    throw new Error(`HTTP ${response.status} saat membuka SSE stream.`);
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder("utf-8");
                let buffer = "";

                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, { stream: true });

                    const events = buffer.split("\n\n");
                    buffer = events.pop() || "";

                    for (const evtBlock of events) {
                        const lines = evtBlock.split("\n");
                        for (const line of lines) {
                            if (!line.startsWith("data: ")) continue;
                            const rawJson = line.slice(6).trim();
                            if (!rawJson) continue;

                            let payload;
                            try {
                                payload = JSON.parse(rawJson);
                            } catch (_) {
                                continue;
                            }

                            if (payload.status === "QUEUED") {
                                this.streamStatusLabel = payload.detail || "Dalam antrian memori AI...";
                            } else if (payload.status === "STARTED") {
                                this.streamStatusLabel = "⏳ AI sedang membaca Memori 4-Tier (0 dtk)... Mohon tunggu";
                            } else if (payload.status === "PROCESSING_PROMPT") {
                                const sec = Number(payload.elapsed_seconds) || 0;
                                this.streamStatusLabel = `⏳ AI sedang membaca konteks 4-Tier (${sec} dtk)... Kata pertama segera muncul`;
                            } else if (payload.status === "STREAM" && payload.token) {
                                if (beatIndex !== -1) {
                                    this.beats[beatIndex].generated_prose += payload.token;
                                    const wCount = this.countWordsClient(
                                        this.beats[beatIndex].generated_prose
                                    );
                                    this.beats[beatIndex].actual_words = wCount;
                                    this.streamStatusLabel = `✍️ Menulis prosa real-time... (${wCount} kata)`;
                                }
                            } else if (payload.status === "ERROR") {
                                this.notify(payload.detail || "Gagal melakukan streaming dari llama-server.", "error");
                                if (beatIndex !== -1) {
                                    if (!this.beats[beatIndex].generated_prose.trim() && existingProse) {
                                        this.beats[beatIndex].generated_prose = rawExistingProse;
                                        this.beats[beatIndex].actual_words = wordsBeforeStream;
                                    }
                                    this.beats[beatIndex].status = existingProse ? "COMPLETED" : "PENDING";
                                }
                            } else if (payload.status === "DONE") {
                                if (beatIndex !== -1 && payload.beat) {
                                    this.beats[beatIndex] = payload.beat;
                                }
                                const wordsAfter = Number(payload.actual_words) || 0;
                                if (wordsAfter > wordsBeforeStream) {
                                    this.recordDailyWordsDelta(wordsAfter - wordsBeforeStream);
                                }
                                this.syncActiveChapterWordCountCache();
                                const trimmedCount = (payload.trimmed_moralizing_sentences || []).length;
                                if (trimmedCount > 0) {
                                    this.notify(
                                        `Beat #${beat.beat_number} selesai! (${trimmedCount} kalimat klise penutup otomatis dipotong oleh Anti-Summary Filter)`,
                                        "success"
                                    );
                                } else {
                                    this.notify(
                                        `Beat #${beat.beat_number} selesai ditulis (${payload.actual_words} kata)!`,
                                        "success"
                                    );
                                }

                                if (this.autoExtractAfterStream && payload.actual_words > 0) {
                                    await this.extractBeatState(beat);
                                }
                            }
                        }
                    }
                }
            } catch (err) {
                if (beatIndex !== -1 && !this.beats[beatIndex].generated_prose.trim() && existingProse) {
                    this.beats[beatIndex].generated_prose = rawExistingProse;
                    this.beats[beatIndex].actual_words = wordsBeforeStream;
                }
                if (err.name === "AbortError") {
                    this.notify("Streaming dihentikan oleh penulis.", "info");
                } else {
                    this.notify(`Streaming terputus: ${err.message}`, "error");
                }
            } finally {
                this.streamingBeatId = null;
                this.streamStatusLabel = "";
                this.streamAbortController = null;
                await this.fetchSystemHealth();
            }
        },

        stopStreaming() {
            if (this.streamAbortController) {
                this.streamAbortController.abort();
            }
        },

        countWordsClient(text) {
            if (!text || !text.trim()) return 0;
            return text.trim().split(/\s+/).length;
        },

        // Simpan Edit Manual Naskah Prosa & Buat Revisi Baru
        async saveManualProseRevision(beat, note = "Manual Author Polish") {
            if (!beat || !beat.id) return;
            try {
                const updated = await this.apiRequest(`/api/beats/${beat.id}/revisions`, {
                    method: "POST",
                    body: JSON.stringify({
                        prose_content: beat.generated_prose || "",
                        revision_note: note,
                    }),
                });
                const idx = this.beats.findIndex((b) => b.id === beat.id);
                if (idx !== -1) this.beats[idx] = updated;
                this.notify(
                    `Naskah Beat #${beat.beat_number} (${updated.actual_words} kata) disimpan ke riwayat revisi!`,
                    "success"
                );
            } catch (err) {
                this.notify(`Gagal menyimpan revisi: ${err.message}`, "error");
            }
        },

        // ====================================================================
        // POST-BEAT STATE EXTRACTOR (/api/beats/{id}/extract-state)
        // ====================================================================
        async extractBeatState(beat, forceMode = null) {
            if (!beat || !beat.id) return;
            if (!beat.generated_prose || !beat.generated_prose.trim()) {
                this.notify("Tulis atau isi teks prosa pada Beat ini terlebih dahulu.", "warning");
                return;
            }
            this.extractingBeatId = beat.id;
            const mode = forceMode || this.extractMode || "fast_local";
            try {
                const res = await this.apiRequest(`/api/beats/${beat.id}/extract-state?mode=${encodeURIComponent(mode)}`, {
                    method: "POST",
                });
                const idx = this.beats.findIndex((b) => b.id === beat.id);
                if (idx !== -1) {
                    this.beats[idx].extracted_summary = res.beat_summary;
                }
                if (this.activeChapter) {
                    this.activeChapter.chapter_summary = res.chapter_summary;
                }
                if (this.activeProject) {
                    this.activeProject.rolling_global_summary = res.rolling_global_summary;
                }
                await this.loadCodex();
                const srcTag = res.extraction_source === "llama_server_extractor" ? "AI Extractor" : "Lokal <1ms (Slot 0 Utuh)";
                this.notify(
                    `State diekstrak (${srcTag})! Ringkasan & ${res.updated_characters.length} karakter Codex diperbarui.`,
                    "success"
                );
            } catch (err) {
                this.notify(`Gagal mengekstrak state: ${err.message}`, "error");
            } finally {
                this.extractingBeatId = null;
            }
        },

        async inspectBeatMemoryContext(beat) {
            if (!beat || !beat.id) return;
            try {
                this.memoryInspectorData = await this.apiRequest(`/api/beats/${beat.id}/memory-context`);
                this.showMemoryInspectorModal = true;
            } catch (err) {
                this.notify(`Gagal memuat 4-Tier Memory: ${err.message}`, "error");
            }
        },

        downloadProjectBackup() {
            if (!this.activeProjectId) return;
            window.open(`${this.apiBase}/api/projects/${encodeURIComponent(this.activeProjectId)}/backup`, "_blank", "noopener");
            this.notify("Mengunduh cadangan proyek lengkap (.json)...", "info");
        },

        // ====================================================================
        // REVISION HISTORY MODAL (/api/beats/{id}/revisions)
        // ====================================================================
        async openRevisionHistory(beat) {
            if (!beat || !beat.id) return;
            try {
                this.revisionBeatTarget = beat;
                this.beatRevisions = await this.apiRequest(`/api/beats/${beat.id}/revisions`);
                this.showRevisionModal = true;
            } catch (err) {
                this.notify(`Gagal memuat riwayat revisi: ${err.message}`, "error");
            }
        },

        async restoreRevision(rev) {
            if (!this.revisionBeatTarget || !rev) return;
            this.revisionBeatTarget.generated_prose = rev.prose_content;
            await this.saveManualProseRevision(
                this.revisionBeatTarget,
                `Restored from Revision #${rev.revision_number}`
            );
            this.showRevisionModal = false;
        },

        // Export Naskah Bab ke File Markdown / TXT
        exportChapterManuscript() {
            if (!this.activeChapter) return;
            const proseBlocks = this.beats
                .map((b) => (b.generated_prose || "").trim())
                .filter(Boolean);
            const fullText = `# Bab ${this.activeChapter.chapter_number}: ${this.activeChapter.title}\n\n${proseBlocks.join("\n\n***\n\n")}\n`;
            const blob = new Blob([fullText], { type: "text/markdown;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `Bab_${this.activeChapter.chapter_number}_${this.activeChapter.title.replace(/\s+/g, "_")}.md`;
            a.click();
            URL.revokeObjectURL(url);
            this.notify("Naskah bab berhasil diunduh (.md)!", "success");
        },

        async copyChapterProse() {
            if (!this.activeChapter) return;
            const proseBlocks = this.beats
                .map((b) => (b.generated_prose || "").trim())
                .filter(Boolean);
            if (!proseBlocks.length) {
                this.notify("Belum ada prosa di bab ini untuk disalin.", "warning");
                return;
            }
            const cleanText = `Bab ${this.activeChapter.chapter_number}: ${this.activeChapter.title}\n\n${proseBlocks.join("\n\n* * *\n\n")}`;
            try {
                if (navigator.clipboard && window.isSecureContext) {
                    await navigator.clipboard.writeText(cleanText);
                } else {
                    const ta = document.createElement("textarea");
                    ta.value = cleanText;
                    ta.style.position = "fixed";
                    ta.style.left = "-9999px";
                    document.body.appendChild(ta);
                    ta.select();
                    document.execCommand("copy");
                    document.body.removeChild(ta);
                }
                this.notify(`Prosa Bab ${this.activeChapter.chapter_number} (${this.actualChapterWordCount} kata) disalin ke clipboard!`, "success");
            } catch (err) {
                this.notify(`Gagal menyalin naskah: ${err.message}`, "error");
            }
        },

        // Cari & Ganti Lintas Micro-Beats di Bab Aktif
        get findMatchStats() {
            const q = this.findQuery || "";
            if (!q) return { totalMatches: 0, affectedBeats: 0 };
            const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
            const re = new RegExp(escaped, this.findCaseSensitive ? "g" : "gi");
            let totalMatches = 0;
            let affectedBeats = 0;
            for (const b of this.beats) {
                const prose = b.generated_prose || "";
                const m = prose.match(re);
                if (m && m.length > 0) {
                    totalMatches += m.length;
                    affectedBeats += 1;
                }
            }
            return { totalMatches, affectedBeats };
        },

        async replaceAllInChapter() {
            const q = this.findQuery || "";
            if (!q) {
                this.notify("Masukkan teks yang ingin dicari terlebih dahulu.", "warning");
                return;
            }
            const stats = this.findMatchStats;
            if (stats.totalMatches === 0) {
                this.notify(`Tidak ditemukan kemunculan "${q}" di bab ini.`, "info");
                return;
            }
            if (!confirm(`Ganti seluruh ${stats.totalMatches} kemunculan "${q}" dengan "${this.replaceQuery}" di ${stats.affectedBeats} Beat? Snapshot riwayat otomatis akan dibuat sebelum mengganti.`)) {
                return;
            }
            await this.flushPendingBeatSaves();
            const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
            const re = new RegExp(escaped, this.findCaseSensitive ? "g" : "gi");
            let updatedCount = 0;
            try {
                for (let i = 0; i < this.beats.length; i++) {
                    const b = this.beats[i];
                    const oldProse = b.generated_prose || "";
                    if (!re.test(oldProse)) continue;
                    re.lastIndex = 0;
                    // Buat snapshot revisi sebelum bulk replace
                    await this.apiRequest(`/api/beats/${b.id}/revisions`, {
                        method: "POST",
                        body: JSON.stringify({
                            prose_content: oldProse,
                            revision_note: `Sebelum Find & Replace (${q} -> ${this.replaceQuery})`,
                        }),
                    });
                    const newProse = oldProse.replace(re, () => this.replaceQuery);
                    const updated = await this.apiRequest(`/api/beats/${b.id}/revisions`, {
                        method: "POST",
                        body: JSON.stringify({
                            prose_content: newProse,
                            revision_note: `Find & Replace: "${q}" -> "${this.replaceQuery}"`,
                        }),
                    });
                    this.beats[i] = updated;
                    updatedCount += 1;
                }
                this.syncActiveChapterWordCountCache();
                this.notify(`Berhasil mengganti ${stats.totalMatches} kemunculan pada ${updatedCount} Beat!`, "success");
            } catch (err) {
                this.notify(`Gagal melakukan Cari & Ganti: ${err.message}`, "error");
            }
        },

        async openExportModal(defaultFormat = "epub") {
            await this.flushPendingBeatSaves();
            this.exportOptions.format = defaultFormat;
            this.exportOptions.author_name = (this.activeProject && this.activeProject.author_name) || "Penulis Studio";
            this.showExportModal = true;
        },

        async executeExport() {
            await this.flushPendingBeatSaves();
            if (this.exportOptions.format === "chapter_md") {
                this.exportChapterManuscript();
                this.showExportModal = false;
                return;
            }
            if (!this.activeProjectId) {
                this.notify("Pilih proyek novel terlebih dahulu.", "warning");
                return;
            }
            const params = new URLSearchParams({
                author: (this.exportOptions.author_name || "").trim(),
                approved_only: String(Boolean(this.exportOptions.approved_only)),
            });
            let pathSeg = "epub";
            if (this.exportOptions.format === "markdown") {
                pathSeg = "markdown";
                params.set("include_codex_appendix", String(Boolean(this.exportOptions.include_codex_appendix)));
            } else if (this.exportOptions.format === "print_html") {
                pathSeg = "print-html";
                params.set("include_synopsis", String(Boolean(this.exportOptions.include_synopsis)));
            } else {
                params.set("include_synopsis", String(Boolean(this.exportOptions.include_synopsis)));
            }
            const url = `${this.apiBase}/api/projects/${encodeURIComponent(this.activeProjectId)}/export/${pathSeg}?${params.toString()}`;
            window.open(url, "_blank", "noopener");
            this.showExportModal = false;
            this.notify("Menyiapkan hasil kompilasi naskah...", "success");
        },

        // Export Seluruh Novel Standar Penerbit (.EPUB atau .MD via Backend Compiler)
        exportFullNovel(format = "epub") {
            if (!this.activeProjectId) {
                this.notify("Pilih proyek novel terlebih dahulu.", "warning");
                return;
            }
            this.openExportModal(format);
        },

        // ====================================================================
        // MODEL AI RUNTIME SWITCHER & DOWNLOADER (/api/models)
        // ====================================================================
        async loadModelsStatus() {
            try {
                const data = await this.apiRequest("/api/models");
                this.modelRuntime = data;
            } catch (err) {
                this.notify(`Gagal memuat status model AI: ${err.message}`, "error");
            }
        },

        async openModelManager() {
            this.showModelModal = true;
            await Promise.all([this.loadModelsStatus(), this.loadAiProviderConfig()]);
            if (this.aiProviderSummary?.provider_type && this.aiProviderSummary.provider_type !== "local_llama") {
                this.modelModalTab = "online";
            }
            if (!this.modelPollTimer) {
                this.modelPollTimer = setInterval(() => {
                    if (this.showModelModal && !document.hidden) {
                        this.loadModelsStatus();
                    }
                }, 2000);
            }
        },

        closeModelManager() {
            this.showModelModal = false;
            if (this.modelPollTimer) {
                clearInterval(this.modelPollTimer);
                this.modelPollTimer = null;
            }
        },

        async switchActiveModel(modelIdentifier) {
            if (!modelIdentifier || this.isSwitchingModel) return;
            this.isSwitchingModel = true;
            this.notify(`Memuat model "${modelIdentifier}" ke RAM Linux Mint...`, "info");
            try {
                const res = await this.apiRequest("/api/models/switch", {
                    method: "POST",
                    body: JSON.stringify({
                        model_identifier: modelIdentifier,
                        project_id: this.activeProjectId || null,
                        ctx_size: 8192,
                    }),
                });
                if (this.activeProject && res.profile_name) {
                    this.activeProject.active_model_profile = res.profile_name;
                }
                // Penyesuaian otomatis parameter sampler sastra untuk model 3B vs 7B+
                if ((res.model_filename || "").toLowerCase().includes("3b")) {
                    this.samplerConfig.temperature = 0.75;
                    this.samplerConfig.min_p = 0.06;
                    this.samplerConfig.dry_multiplier = 0.50;
                    this.samplerConfig.xtc_probability = 0.0;
                } else {
                    this.samplerConfig.temperature = 0.92;
                    this.samplerConfig.min_p = 0.07;
                    this.samplerConfig.dry_multiplier = 0.65;
                    this.samplerConfig.xtc_probability = 0.08;
                }
                await Promise.all([this.fetchSystemHealth(), this.loadModelsStatus()]);
                this.notify(
                    `Model aktif beralih ke ${res.model_filename} (PID ${res.pid}, ${res.threads} thread)!`,
                    "success"
                );
            } catch (err) {
                this.notify(`Gagal mengganti model: ${err.message}`, "error");
            } finally {
                this.isSwitchingModel = false;
            }
        },

        async stopAiEngine() {
            this.isSwitchingModel = true;
            try {
                const res = await this.apiRequest("/api/models/stop", { method: "POST" });
                await Promise.all([this.fetchSystemHealth(), this.loadModelsStatus()]);
                this.notify(res.detail || "llama-server dihentikan; RAM dibebaskan.", "info");
            } catch (err) {
                this.notify(`Gagal menghentikan llama-server: ${err.message}`, "error");
            } finally {
                this.isSwitchingModel = false;
            }
        },

        async downloadCuratedModel(catalogId) {
            try {
                const job = await this.apiRequest("/api/models/download", {
                    method: "POST",
                    body: JSON.stringify({ catalog_id: catalogId }),
                });
                await this.loadModelsStatus();
                if (job.status === "ALREADY_EXISTS") {
                    this.notify(`Model ${job.filename} sudah ada di folder models/.`, "info");
                } else {
                    this.notify(`Mengunduh ${job.filename} di background...`, "success");
                }
            } catch (err) {
                this.notify(`Gagal memulai unduhan: ${err.message}`, "error");
            }
        },

        async cancelModelDownload(catalogId) {
            try {
                await this.apiRequest(`/api/models/downloads/${encodeURIComponent(catalogId)}/cancel`, {
                    method: "POST",
                });
                await this.loadModelsStatus();
                this.notify("Unduhan model dibatalkan.", "warning");
            } catch (err) {
                this.notify(`Gagal membatalkan unduhan: ${err.message}`, "error");
            }
        },

        async downloadCustomModel() {
            if (!this.customModelForm.url_or_repo || !this.customModelForm.url_or_repo.trim()) {
                this.notify("Masukkan URL HTTPS `.gguf` atau Repo ID HuggingFace.", "warning");
                return;
            }
            this.isSubmittingCustomModel = true;
            try {
                const job = await this.apiRequest("/api/models/download-custom", {
                    method: "POST",
                    body: JSON.stringify(this.customModelForm),
                });
                await this.loadModelsStatus();
                if (job.status === "ALREADY_EXISTS") {
                    this.notify(`Model ${job.filename} sudah ada di folder models/.`, "info");
                    this.modelModalTab = "local";
                } else {
                    this.notify(`Berhasil memulai unduhan ${job.filename}!`, "success");
                    this.customModelForm = { url_or_repo: "", filename: "", display_name: "", notes: "" };
                }
            } catch (err) {
                this.notify(`Gagal memvalidasi/mengunduh model kustom: ${err.message}`, "error");
            } finally {
                this.isSubmittingCustomModel = false;
            }
        },

        async importModelFromDownloads(filename) {
            try {
                const res = await this.apiRequest("/api/models/import-local", {
                    method: "POST",
                    body: JSON.stringify({ filename, move_file: true }),
                });
                await this.loadModelsStatus();
                this.notify(`Model ${res.filename} (${res.size_gb} GB) dipindahkan ke models/ dan siap dipakai!`, "success");
            } catch (err) {
                this.notify(`Gagal mengimpor model: ${err.message}`, "error");
            }
        },

        async deleteLocalModel(filename) {
            if (!confirm(`Hapus file model "${filename}" dari disk untuk menghemat ruang penyimpanan?`)) return;
            try {
                await this.apiRequest(`/api/models/local/${encodeURIComponent(filename)}`, {
                    method: "DELETE",
                });
                await this.loadModelsStatus();
                this.notify(`Model ${filename} berhasil dihapus dari disk.`, "info");
            } catch (err) {
                this.notify(`Gagal menghapus model: ${err.message}`, "error");
            }
        },

        // ====================================================================
        // ONLINE / EXTERNAL COMPATIBLE AI PROVIDERS (/api/ai/provider)
        // ====================================================================
        get aiHeaderOnline() {
            const ptype = this.systemHealth?.ai_provider?.provider_type || "local_llama";
            if (ptype !== "local_llama") return true;
            return Boolean(this.systemHealth.llama_server_online);
        },

        get aiHeaderBadgeText() {
            const prov = this.systemHealth?.ai_provider;
            if (prov && prov.provider_type !== "local_llama") {
                const mName = prov.model_name || prov.display_name || "API Online";
                return `🌐 API: ${mName}`;
            }
            if (this.systemHealth.llama_server_online) {
                if (this.systemHealth.active_model_filename) {
                    return `AI: ${this.systemHealth.active_model_filename.replace(/\.gguf$/i, "")}`;
                }
                return "llama-server:8080 READY";
            }
            return "Model AI OFFLINE • Pilih";
        },

        get selectedPresetMeta() {
            return (this.aiProviderPresets || []).find((p) => p.preset_id === this.aiProviderForm.preset_id) || null;
        },

        async loadAiProviderConfig() {
            try {
                const data = await this.apiRequest("/api/ai/provider");
                this.aiProviderPresets = data.presets || [];
                this.aiProviderSummary = data;
                if (data.provider_type !== "local_llama") {
                    this.aiProviderForm.provider_type = data.provider_type;
                    this.aiProviderForm.preset_id = data.preset_id || "custom_openai";
                    this.aiProviderForm.display_name = data.display_name || "";
                    this.aiProviderForm.base_url = data.base_url || "";
                    this.aiProviderForm.model_name = this.showAdvancedProviderOptions ? (data.model_name || "") : "";
                    this.aiProviderForm.api_key = "";
                }
            } catch (_) {
                // Abaikan jika backend belum merespons
            }
        },

        selectProviderPreset(preset) {
            if (!preset) return;
            this.aiProviderForm.preset_id = preset.preset_id;
            this.aiProviderForm.provider_type = preset.provider_type;
            this.aiProviderForm.display_name = preset.label;
            this.aiProviderForm.base_url = preset.base_url;
            // Kosongkan agar backend memilih & menguji model aktif terbaik otomatis dari API
            this.aiProviderForm.model_name = "";
            this.remoteFetchedModels = [];
            this.providerTestResult = null;
        },

        _validateProviderInputs() {
            const normalizedUrl = (this.aiProviderForm.base_url || "").trim().replace(/\/+$/, "");
            if (!normalizedUrl) {
                return "Base URL API wajib terisi (buka Pengaturan Lanjutan jika memakai URL kustom).";
            }
            const meta = this.selectedPresetMeta;
            const needsKey = meta ? Boolean(meta.requires_api_key) : false;
            const hasTypedKey = Boolean((this.aiProviderForm.api_key || "").trim());
            const savedBase = (this.aiProviderSummary?.base_url || "").trim().replace(/\/+$/, "");
            const hasSavedSameKey = Boolean(
                this.aiProviderSummary?.has_api_key &&
                this.aiProviderSummary?.preset_id === this.aiProviderForm.preset_id &&
                savedBase === normalizedUrl
            );
            if (needsKey && !hasTypedKey && !hasSavedSameKey) {
                return `Masukkan API Key untuk ${this.aiProviderForm.display_name || this.aiProviderForm.preset_id} terlebih dahulu.`;
            }
            return null;
        },

        async fetchRemoteModelsList() {
            if (!this.aiProviderForm.base_url || !this.aiProviderForm.base_url.trim()) {
                this.notify("Isi Base URL API terlebih dahulu.", "warning");
                return;
            }
            this.isFetchingRemoteModels = true;
            try {
                const res = await this.apiRequest("/api/ai/provider/models", {
                    method: "POST",
                    body: JSON.stringify({
                        provider_type: this.aiProviderForm.provider_type,
                        base_url: this.aiProviderForm.base_url.trim(),
                        api_key: this.aiProviderForm.api_key || null,
                    }),
                });
                this.remoteFetchedModels = res.models || [];
                if (this.remoteFetchedModels.length > 0 && !this.aiProviderForm.model_name) {
                    this.aiProviderForm.model_name = this.remoteFetchedModels[0];
                }
                this.notify(`Berhasil mengambil ${this.remoteFetchedModels.length} model dari server API.`, "success");
            } catch (err) {
                this.notify(`Gagal mengambil daftar model: ${err.message}`, "error");
            } finally {
                this.isFetchingRemoteModels = false;
            }
        },

        async testAiProviderConnection() {
            const validationError = this._validateProviderInputs();
            if (validationError) {
                this.providerTestResult = { ok: false, message: validationError };
                this.notify(validationError, "warning");
                return;
            }
            this.isTestingProvider = true;
            this.providerTestResult = null;
            try {
                const res = await this.apiRequest("/api/ai/provider/test", {
                    method: "POST",
                    body: JSON.stringify({
                        provider_type: this.aiProviderForm.provider_type,
                        preset_id: this.aiProviderForm.preset_id,
                        display_name: this.aiProviderForm.display_name,
                        base_url: this.aiProviderForm.base_url.trim(),
                        model_name: (this.aiProviderForm.model_name || "").trim(),
                        api_key: this.aiProviderForm.api_key || null,
                    }),
                });
                const modelLabel = res.model_name ? `Model aktif: ${res.model_name} • ` : "";
                this.providerTestResult = { ok: true, message: res.detail || `${modelLabel}Sukses (${res.latency_ms} ms)` };
                this.notify(`Uji koneksi berhasil (${res.latency_ms} ms)!`, "success");
            } catch (err) {
                this.providerTestResult = { ok: false, message: err.message };
                this.notify(`Uji koneksi gagal: ${err.message}`, "error");
            } finally {
                this.isTestingProvider = false;
            }
        },

        async saveAndActivateAiProvider(clearApiKey = false) {
            if (clearApiKey) {
                await this.switchBackToLocalAi(true);
                return;
            }
            const validationError = this._validateProviderInputs();
            if (validationError) {
                this.providerTestResult = { ok: false, message: validationError };
                this.notify(validationError, "warning");
                return;
            }
            this.isSavingProvider = true;
            this.providerTestResult = null;
            try {
                const res = await this.apiRequest("/api/ai/provider", {
                    method: "POST",
                    body: JSON.stringify({
                        provider_type: this.aiProviderForm.provider_type,
                        preset_id: this.aiProviderForm.preset_id,
                        display_name: this.aiProviderForm.display_name || this.aiProviderForm.preset_id,
                        base_url: this.aiProviderForm.base_url.trim(),
                        model_name: (this.aiProviderForm.model_name || "").trim(),
                        api_key: this.aiProviderForm.api_key || null,
                        clear_api_key: false,
                        verify_connection: true,
                        stop_local_llama: Boolean(this.aiProviderForm.stop_local_llama),
                    }),
                });
                this.aiProviderForm.api_key = "";
                if (res.test) {
                    this.providerTestResult = {
                        ok: Boolean(res.test.ok),
                        message: res.test.detail || `Aktif: ${res.configured_model} (${res.test.latency_ms || 0} ms)`,
                    };
                } else {
                    this.providerTestResult = { ok: true, message: `Aktif: ${res.configured_model}` };
                }
                await Promise.all([this.fetchSystemHealth(), this.loadModelsStatus(), this.loadAiProviderConfig()]);
                this.notify(
                    `🚀 Sumber AI aktif & terverifikasi: 🌐 ${res.configured_model}! Siap langsung menulis.`,
                    "success"
                );
            } catch (err) {
                this.providerTestResult = { ok: false, message: err.message };
                this.notify(`Gagal menjalankan API AI: ${err.message}`, "error");
            } finally {
                this.isSavingProvider = false;
            }
        },

        async switchBackToLocalAi(clearApiKey = false) {
            this.isSavingProvider = true;
            try {
                await this.apiRequest("/api/ai/provider", {
                    method: "POST",
                    body: JSON.stringify({
                        provider_type: "local_llama",
                        preset_id: "local_llama",
                        clear_api_key: Boolean(clearApiKey),
                        stop_local_llama: false,
                    }),
                });
                this.aiProviderForm.api_key = "";
                this.providerTestResult = null;
                await Promise.all([this.fetchSystemHealth(), this.loadModelsStatus(), this.loadAiProviderConfig()]);
                this.notify(
                    clearApiKey
                        ? "API Key dihapus & Studio kembali ke Mode Lokal (llama-server GGUF)."
                        : "Beralih kembali ke mode Mesin Lokal (llama-server GGUF).",
                    "info"
                );
            } catch (err) {
                this.notify(`Gagal kembali ke mode lokal: ${err.message}`, "error");
            } finally {
                this.isSavingProvider = false;
            }
        },

        get availableProfileOptions() {
            const seen = new Set();
            const list = [];
            for (const m of (this.modelRuntime.local_models || [])) {
                if (!seen.has(m.profile_name)) {
                    seen.add(m.profile_name);
                    list.push({
                        value: m.profile_name,
                        label: `✓ ${m.display_name} (${m.size_gb}GB • Lokal)`,
                    });
                }
            }
            for (const c of (this.modelRuntime.curated_catalog || [])) {
                if (!seen.has(c.profile_name)) {
                    seen.add(c.profile_name);
                    list.push({
                        value: c.profile_name,
                        label: `${c.display_name} (${(c.size_mb / 1024).toFixed(1)}GB • Belum diunduh)`,
                    });
                }
            }
            if (this.activeProject && this.activeProject.active_model_profile && !seen.has(this.activeProject.active_model_profile)) {
                list.unshift({
                    value: this.activeProject.active_model_profile,
                    label: this.activeProject.active_model_profile,
                });
            }
            return list;
        },
    };
}
