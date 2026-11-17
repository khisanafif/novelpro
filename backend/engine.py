import json
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from database import (
    DEFAULT_BANNED_PHRASES,
    count_words,
    get_chapter,
    get_codex_item,
    get_micro_beat,
    get_story_bible_bundle,
    list_codex_items,
    list_micro_beats,
)


# ============================================================================
# 1. SYSTEM PROMPTS UNTUK 3 PERSONA UTAMA (HEMAT TOKEN & KONTEKS 8K)
# ============================================================================

LITERARY_NOVELIST_STATIC_SYSTEM_PROMPT = """Anda adalah THE LITERARY NOVELIST, novelis fiksi sastra profesional. Tulis adegan cerita dengan prosa yang hidup, panca indra yang konkret (Show, Don't Tell), dialog yang memiliki subteks alami, serta hindari klise AI.

[IDENTITAS & KOMPAS NOVEL (TIER-1 IMMUTABLE STORY BIBLE)]
Judul: {title} ({genre})
Logline: {logline}
Tujuan Utama (North Star): {main_objective}
Sudut Pandang & Tense: {pov_style} | {tense_style}
Tone & Gaya Bahasa: {tone_style}
Contoh Ritme Kalimat & Gaya Bahasa Acuan (Tirulah kepadatan dan ritme prosa ini):
"{style_sample}"

[ATURAN MUTLAK DUNIA & ENTITAS PINNED]
{pinned_world_rules}

[LARANGAN KERAS & ANTI-MORALIZING]
- DILARANG menggunakan frasa klise berikut: {banned_phrases}
- DILARANG menutup adegan dengan kalimat kesimpulan moral, refleksi masa depan ("perjalanan mereka baru dimulai", "hanya waktu yang akan menjawab"), atau rangkuman perasaan.
- Tunjukkan emosi melalui reaksi fisik, tarikan napas, perubahan suhu kulit, atau tindakan mikro, bukan dengan menyebut nama emosinya secara abstrak.
- WAJIB berhenti menulis tepat pada tindakan atau dialog di [TITIK BERHENTI BEAT]. Jangan melompati atau membocorkan kejadian beat berikutnya.

[FASE STRUKTUR & BAB AKTIF (PHASE-RANGE GUARDRAILS)]
Fase Saat Ini: {phase_name} (Rentang Bab {start_chapter} s.d. Bab {end_chapter})
Fokus Pembangunan Fase Ini: {building_focus}
Aturan Pengunci Fase (WAJIB DIPATUHI): {phase_guardrails}
Bab Aktif: Bab {chapter_number} - "{chapter_title}"
Tujuan Utama Bab Ini: {chapter_goal}

[TIER-2 MEMORI GLOBAL BERGULIR (ROLLING GLOBAL SUMMARY)]
{rolling_global_summary}"""

LITERARY_NOVELIST_DYNAMIC_USER_PROMPT = """[TIER-3 KONTEKS ENTITAS & LOKASI DI ADEGAN INI (FTS5 BM25 RETRIEVAL)]
Lokasi Aktif: {active_location}
Karakter yang Terlibat & Kondisi Terkini:
{active_characters_status}
Referensi Codex & Lore Tambahan:
{dynamic_codex_context}

[FAKTA & KEJADIAN MASA LALU YANG RELEVAN]
{fts5_retrieved_memories}

[KONSOL PENGATUR PACING & NARRATIVE MIX - BEAT {beat_number} DARI {total_beats}]
- Mode Pacing: {pacing_mode} | Ketegangan (Tension): {tension_level}/100
- Target Kata Beat Ini: {target_words} kata (Sisa Anggaran Kata Bab: {remaining_words} kata)
- Instruksi Komposisi Narasi (5 Sliders):
{mixing_directives}

[RINGKASAN BEAT SEBELUMNYA DI BAB INI]
{previous_beats_summary}

[TIER-4 SAMBUNGAN TEKS TERAKHIR (VERBATIM CONTINUITY)]
...{last_verbatim_tail}

[TUGAS PENULISAN BEAT {beat_number}]
Fokus Sensorik: {sensory_anchor}
Fokus Konflik Mikro: {conflict_focus}
Kejadian yang Harus Ditulis: {beat_instruction}
TITIK BERHENTI BEAT (Berhenti tepat di sini): {stopping_point}

Tuliskan langsung kelanjutan prosa naskah ({target_words} kata) tanpa judul bab, tanpa nomor beat, dan tanpa komentar pengantar:"""


PLOT_ARCHITECT_SYSTEM_PROMPT = """Anda adalah THE PLOT ARCHITECT, perancang struktur adegan novel deterministik.
Tugas Anda adalah memecah Tujuan Bab (Chapter Goal) menjadi tepat {total_micro_beats} Micro-Beats berurutan yang mematuhi mode pacing, kurva ketegangan (tension_curve), dan pengunci fase (Phase Guardrails).

ATURAN STRUKTUR PACING:
- Mode Pacing Aktif: {pacing_mode}
- Target Total Kata Bab: {target_word_count} kata ({total_micro_beats} Micro-Beats @ ~{words_per_beat} kata per beat).
- Estimasi Poin Kejadian Utama: {major_plot_events_needed} kejadian utama.
  * Jika SLOW_BURN: 1 Kejadian Utama dipecah menjadi 3 Micro-Beats (Beat A: Atmosfer, sensorik & bahasa tubuh; Beat B: Dialog ber-subteks, psikologi & observasi objek; Beat C: Tindakan konkret & transisi menggantung).
  * Jika BALANCED: 1 Kejadian Utama dipecah menjadi 2 Micro-Beats (Beat A: Pembangunan situasi & interaksi; Beat B: Eskalasi konflik & keputusan tindakan).
  * Jika FAST_PACED: 1 Kejadian Utama = 1 Micro-Beat padat aksi, tempo cepat, kalimat tajam, dan pertaruhan langsung.

ATURAN OUTPUT WAJIB:
Keluarkan HANYA JSON valid berupa objek dengan key `"beats"` yang berisi array tepat {total_micro_beats} objek.
Setiap objek di dalam `"beats"` WAJIB memiliki field berikut:
- `"beat_number"`: integer (1 sampai {total_micro_beats})
- `"tension_level"`: integer sesuai daftar distribusi kurva ketegangan: {tension_curve_json}
- `"target_words"`: integer ({words_per_beat})
- `"pov_character_name"`: string nama karakter POV di beat ini
- `"location_name"`: string nama lokasi spesifik adegan
- `"sensory_anchor"`: string detail panca indra konkret (cahaya, suara, bau, suhu, tekstur) yang wajib hadir
- `"conflict_focus"`: string ketegangan batin atau gesekan antar-karakter di beat ini
- `"beat_instruction"`: string instruksi konkret langkah demi langkah apa yang terjadi di beat ini (2-4 kalimat padat)
- `"stopping_point"`: string tindakan fisik, dialog spesifik, atau citra sensorik tempat AI penulis WAJIB berhenti menulis agar tidak bocor ke beat berikutnya."""


PLOT_ARCHITECT_USER_PROMPT = """[KONTEKS NOVEL & FASE AKTIF]
Judul Novel: {title} ({genre})
Tujuan Utama Novel: {main_objective}
Fase Saat Ini: {phase_name} (Bab {start_chapter} - {end_chapter})
Fokus Pembangunan Fase: {building_focus}
Aturan Pengunci Fase (Guardrails): {phase_guardrails}
Ringkasan Cerita Sejauh Ini:
{rolling_global_summary}

[DAFTAR ENTITAS CODEX (KARAKTER & LOKASI TERSEDIA)]
{available_entities}

[SPESIFIKASI BAB YANG AKAN DIPECAH]
Nomor & Judul Bab: Bab {chapter_number} - "{chapter_title}"
Tujuan Bab (Chapter Goal): {chapter_goal}
Gaya Hook Akhir Bab: {ending_hook_style}
Instruksi Komposisi Narasi Bab Ini:
{mixing_directives}

Hasilkan tepat {total_micro_beats} Micro-Beats dalam format JSON murni sekarang:"""


POST_BEAT_STATE_EXTRACTOR_SYSTEM_PROMPT = """Anda adalah POST-BEAT STATE EXTRACTOR, mesin analitik kontinuitas naskah fiksi.
Tugas Anda adalah membaca teks prosa Micro-Beat yang baru selesai ditulis dan mengekstrak fakta kontinuitas secara objektif tanpa opini sastrawi.

Keluarkan HANYA JSON valid dengan skema persis berikut:
{
  "beat_summary": "Ringkasan padat 1-2 kalimat tentang kejadian faktual di beat ini.",
  "episodic_keywords": "kata, kunci, penting, nama, objek, lokasi",
  "character_updates": [
    {
      "name": "Nama Karakter",
      "location": "Lokasi baru jika berpindah, atau kosongkan jika tetap",
      "condition": "Kondisi fisik saat ini (misal: Terluka di bahu kiri / Kelelahan / Sehat)",
      "emotional_state": "Kondisi psikologis/emosi terkini",
      "knowledge": "Fakta atau rahasia baru yang baru saja diketahui karakter di beat ini"
    }
  ],
  "world_fact_delta": "Perubahan status objek/lokasi penting jika ada (opsional, string kosong jika tidak ada)"
}"""


POST_BEAT_STATE_EXTRACTOR_USER_PROMPT = """[KONTEKS BAB & BEAT]
Bab {chapter_number}: "{chapter_title}" - Beat #{beat_number}
Instruksi Asli Beat: {beat_instruction}

[STATUS KARAKTER SEBELUM BEAT INI]
{known_characters_json}

[TEKS PROSA BEAT YANG BARU DITULIS]
{generated_prose}

Ekstrak pembaruan state ke dalam JSON valid sekarang:"""


# ============================================================================
# 2. DETERMINISTIC PACING ENGINE (BAGIAN 5, 6, & 9 BLUEPRINT)
# ============================================================================

class DeterministicPacingEngine:
    """
    Mesin Deterministik Pengatur Jumlah Micro-Beats, Kurva Ketegangan (Tension Curve),
    dan Penerjemah 5 Slider Komposisi Narasi (Narrative Mix) menjadi Direktif Prompt Presisi.
    """

    DEFAULT_BEAT_WORD_SIZE = 400
    MIN_BEAT_WORD_SIZE = 350
    MAX_BEAT_WORD_SIZE = 420

    PACING_RATIO_MAP = {
        "SLOW_BURN": 3.0,        # 1 Kejadian Utama = 3 Micro-Beats (~1200 kata)
        "BALANCED": 2.0,         # 1 Kejadian Utama = 2 Micro-Beats (~800 kata)
        "FAST_PACED": 1.0,       # 1 Kejadian Utama = 1 Micro-Beat (~400 kata)
        "FRENETIC_ACTION": 0.75, # Tempo sangat cepat & intens (~1.3 kejadian per beat)
    }

    @classmethod
    def calculate_chapter_plan(
        cls,
        target_words: int,
        pacing_mode: str = "BALANCED",
        t_min: int = 15,
        t_max: int = 50,
        beat_size: int = DEFAULT_BEAT_WORD_SIZE,
    ) -> Dict[str, Any]:
        """
        Menghitung total_micro_beats, target kata per beat, jumlah kejadian utama,
        dan distribusi tension_curve sinusoidal bertahap sesuai fase bab.
        """
        safe_target_words = max(350, int(target_words or 3200))
        safe_beat_size = max(cls.MIN_BEAT_WORD_SIZE, min(cls.MAX_BEAT_WORD_SIZE, int(beat_size)))
        mode = (pacing_mode or "BALANCED").upper()

        total_micro_beats = max(1, round(safe_target_words / safe_beat_size))
        words_per_beat = max(250, round(safe_target_words / total_micro_beats))

        beats_per_event = cls.PACING_RATIO_MAP.get(mode, 2.0)
        major_events = max(1, math.ceil(total_micro_beats / beats_per_event))

        safe_t_min = max(5, min(95, int(t_min if t_min is not None else 15)))
        safe_t_max = max(safe_t_min + 5, min(100, int(t_max if t_max is not None else 50)))

        tension_curve: List[int] = []
        for i in range(total_micro_beats):
            if total_micro_beats == 1:
                progress = 1.0
            else:
                progress = i / (total_micro_beats - 1)
            # Gelombang mikro agar napas ketegangan terasa organik (naik-turun-naik ke puncak bab)
            wave = math.sin(progress * math.pi * 1.5) * 5.0
            raw_tension = safe_t_min + (safe_t_max - safe_t_min) * progress + wave
            # Beat terakhir di bab didorong mendekati batas atas ketegangan bab untuk hook akhir
            if i == total_micro_beats - 1 and total_micro_beats > 1:
                raw_tension = max(raw_tension, safe_t_max - 2)
            t_val = int(min(100, max(5, round(raw_tension))))
            tension_curve.append(t_val)

        return {
            "total_micro_beats": total_micro_beats,
            "total_beats": total_micro_beats,  # Alias kompatibilitas Bagian 9 Blueprint
            "words_per_beat": words_per_beat,
            "major_plot_events_needed": major_events,
            "pacing_mode": mode,
            "tension_min": safe_t_min,
            "tension_max": safe_t_max,
            "tension_curve": tension_curve,
        }

    @classmethod
    def compile_narrative_mix_directives(
        cls,
        mix_world_building: int = 50,
        mix_psychology: int = 50,
        mix_sensory: int = 70,
        mix_dialogue: int = 40,
        mix_action: int = 30,
        tension_level: int = 35,
        pacing_mode: str = "BALANCED",
    ) -> str:
        """
        Menerjemahkan 5 slider Narrative Mix (World-Building, Internal Monologue/Psychology,
        Sensory, Dialogue, Action) + Tension Level menjadi instruksi prompt presisi.
        """
        wb = max(0, min(100, int(mix_world_building)))
        psy = max(0, min(100, int(mix_psychology)))
        sen = max(0, min(100, int(mix_sensory)))
        dlg = max(0, min(100, int(mix_dialogue)))
        act = max(0, min(100, int(mix_action)))
        tension = max(0, min(100, int(tension_level)))
        mode = (pacing_mode or "BALANCED").upper()

        directives: List[str] = []

        # 1. Slider World-Building
        if wb >= 65:
            directives.append(f"World-Building {wb}% (sisipkan detail ruang/budaya lewat objek fisik)")
        elif wb <= 25:
            directives.append(f"World-Building {wb}% (hindari eksposisi latar; fokus interaksi langsung)")
        else:
            directives.append(f"World-Building {wb}% (latar secukupnya mendukung adegan)")

        # 2. Slider Internal Monologue / Psychology
        if psy >= 65:
            directives.append(f"Psikologi {psy}% (dalami keraguan, ingatan, & gejolak batin POV)")
        elif psy <= 25:
            directives.append(f"Psikologi {psy}% (minimalkan monolog; tunjukkan emosi lewat gestur)")
        else:
            directives.append(f"Psikologi {psy}% (batin & aksi seimbang)")

        # 3. Slider Sensory Detail
        if sen >= 65:
            directives.append(f"Sensorik {sen}% (wajib 3+ indra konkret: cahaya, suara, bau, suhu/tekstur)")
        elif sen <= 25:
            directives.append(f"Sensorik {sen}% (deskripsi indra ringkas)")
        else:
            directives.append(f"Sensorik {sen}% (1-2 jangkar panca indra kuat)")

        # 4. Slider Dialogue
        if dlg >= 65:
            directives.append(f"Dialog {dlg}% (dominan percakapan ber-subteks & jeda bahasa tubuh)")
        elif dlg <= 30:
            directives.append(f"Dialog {dlg}% (minim dialog, fokus narasi atmosferik & tindakan sunyi)")
        else:
            directives.append(f"Dialog {dlg}% (dialog & narasi berimbang)")

        # 5. Slider Action & Tension Curve Integration
        if act >= 70 or tension >= 80 or mode in ("FAST_PACED", "FRENETIC_ACTION"):
            directives.append(f"Aksi {act}%/Tension {tension} (kalimat pendek tajam, urgensi cepat)")
        elif act <= 25 and tension <= 35:
            directives.append(f"Ritme Tenang {act}%/Tension {tension} (kalimat mengalir, atmosferik)")
        else:
            directives.append(f"Ritme Dinamis {act}%/Tension {tension} (progresi fisik terukur)")

        return " | ".join(directives)

    @classmethod
    def compile_mixing_directives(
        cls, chapter_data: Dict[str, Any], tension: int
    ) -> str:
        """Helper langsung dari dict/row chapter (kompatibel penuh dengan Bagian 9 Blueprint)."""
        return cls.compile_narrative_mix_directives(
            mix_world_building=int(chapter_data.get("mix_world_building", 50)),
            mix_psychology=int(chapter_data.get("mix_psychology", 50)),
            mix_sensory=int(chapter_data.get("mix_sensory", 70)),
            mix_dialogue=int(chapter_data.get("mix_dialogue", 40)),
            mix_action=int(chapter_data.get("mix_action", 30)),
            tension_level=int(tension),
            pacing_mode=str(chapter_data.get("pacing_mode", "BALANCED")),
        )


# Alias agar kode yang mengimpor PacingCompiler tetap kompatibel
PacingCompiler = DeterministicPacingEngine


# ============================================================================
# 3. CONTEXT ASSEMBLER (4-TIER MEMORY + ANTI-SUMMARY TAIL TRIMMING + SAMPLER)
# ============================================================================

class ContextAssembler:
    """
    Perakit Konteks 4-Tier untuk Kapasitas Konteks 8.192 Token di Linux Mint RAM 8 GB:
    - Tier 1: Immutable Story Bible + Phase Guardrails + Pinned Codex (Dikunci di Slot 0 KV Cache)
    - Tier 2: Rolling Global Summary + Previous Beats Summary di Bab Aktif
    - Tier 3: Auto-Retrieved Codex Entities & Episodic Memories via SQLite FTS5 BM25
    - Tier 4: Verbatim Tail (250-320 kata terakhir dari beat sebelumnya untuk kontinuitas kalimat)
    Dilengkapi Anti-Summary / Anti-Moralizing Tail Trimming dan Profil Sampler Khusus Sastra.
    """

    MORALIZING_PATTERNS = [
        r"[^.!?]*\btanpa mereka sadari\b[^.!?]*[.!?]",
        r"[^.!?]*\bwaktu seakan berhenti\b[^.!?]*[.!?]",
        r"[^.!?]*\bperjalanan\b[^.!?]*\bbaru saja dimulai\b[^.!?]*[.!?]",
        r"[^.!?]*\bperjuangan\b[^.!?]*\bbaru saja dimulai\b[^.!?]*[.!?]",
        r"[^.!?]*\bhanya waktu yang (bisa|akan) menjawab\b[^.!?]*[.!?]",
        r"[^.!?]*\bsatu hal yang pasti\b[^.!?]*[.!?]",
        r"[^.!?]*\bmalam itu menjadi saksi\b[^.!?]*[.!?]",
        r"[^.!?]*\btakdir telah memilih\b[^.!?]*[.!?]",
        r"[^.!?]*\bsebuah babak baru\b[^.!?]*[.!?]",
    ]

    @classmethod
    def get_literary_sampler_params(
        cls,
        target_words: int = 400,
        temperature: float = 1.02,
        min_p: float = 0.07,
        dry_multiplier: float = 0.8,
        xtc_probability: float = 0.1,
        id_slot: int = 0,
    ) -> Dict[str, Any]:
        """
        Menghasilkan parameter sampler native C++ llama-server sesuai spesifikasi:
        - min_p: 0.07 (menjaga koherensi logika cerita sambil mengizinkan diksi kreatif)
        - dry_multiplier: 0.8 (DRY Sampler anti-pengulangan frasa/kalimat)
        - xtc_probability: 0.1 (XTC Sampler untuk membuang klise & memilih sinonim sastrawi)
        - id_slot: 0 & cache_prompt: True (KV Cache Pinning di RAM 8 GB)
        """
        max_tokens = max(250, min(1200, int(round(target_words * 1.55))))
        return {
            "cache_prompt": True,
            "id_slot": int(id_slot),
            "max_tokens": max_tokens,
            "temperature": float(temperature),
            "min_p": float(min_p),
            "dry_multiplier": float(dry_multiplier),
            "dry_base": 1.75,
            "dry_allowed_length": 3,
            "dry_penalty_last_n": 1024,
            "xtc_probability": float(xtc_probability),
            "xtc_threshold": 0.1,
            "repeat_penalty": 1.04,
        }

    @classmethod
    def trim_moralizing_tail(
        cls,
        prose_text: str,
        custom_banned_phrases: Optional[List[str]] = None,
    ) -> Tuple[str, List[str]]:
        """
        Anti-Summary Tail Trimming:
        Memeriksa paragraf/kalimat paling akhir dari prosa hasil generasi.
        Jika kalimat penutup terdeteksi mengandung kesimpulan moralistik AI atau banned phrases,
        kalimat tersebut dipotong agar beat selalu berakhir pada tindakan, dialog, atau citra sensorik.
        """
        if not prose_text or not prose_text.strip():
            return "", []

        cleaned = prose_text.strip()
        removed_sentences: List[str] = []
        banned_list = list(DEFAULT_BANNED_PHRASES)
        if custom_banned_phrases:
            for p in custom_banned_phrases:
                if p and p.lower() not in [b.lower() for b in banned_list]:
                    banned_list.append(p)

        # 1. Hapus kemunculan kalimat di bagian ekor (2 kalimat terakhir) yang memuat kesimpulan klise
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", cleaned) if p.strip()]
        if not paragraphs:
            return cleaned, removed_sentences

        last_para = paragraphs[-1]
        # Pisahkan kalimat dengan tetap mempertahankan tanda baca termasuk tanda kutip penutup
        sentence_regex = r'[^.!?]+[.!?]+["”’\']?'
        sentences = [s.strip() for s in re.findall(sentence_regex, last_para) if s.strip()]

        if len(sentences) >= 2:
            tail_candidates = sentences[-2:]
            kept_sentences = sentences[:-2]
            for sent in tail_candidates:
                lower_sent = sent.lower()
                is_moralizing = False
                for pat in cls.MORALIZING_PATTERNS:
                    if re.search(pat, lower_sent, flags=re.IGNORECASE):
                        is_moralizing = True
                        break
                if not is_moralizing:
                    for phrase in banned_list:
                        if phrase.lower() in lower_sent:
                            is_moralizing = True
                            break
                if is_moralizing:
                    removed_sentences.append(sent)
                else:
                    kept_sentences.append(sent)

            if kept_sentences:
                paragraphs[-1] = " ".join(kept_sentences)
            else:
                paragraphs.pop()

        result_text = "\n\n".join(paragraphs).strip()
        return (result_text if result_text else cleaned), removed_sentences

    @staticmethod
    def extract_verbatim_tail(text: str, max_words: int = 400) -> str:
        """Mengambil N kata terakhir dari naskah sebelumnya (Tier-3 400 Kata Verbatim Continuity)."""
        if not text or not text.strip():
            return "(Awal Bab - Belum ada teks sebelumnya)"
        words = text.strip().split()
        if len(words) <= max_words:
            return " ".join(words)
        return " ".join(words[-max_words:])

    @classmethod
    def assemble_beat_prompts(
        cls,
        beat_id: str,
        db_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Merakit Static System Prompt (Tier 1 & Tier 2) dan Dynamic User Prompt (Tier 3 & Tier 4)
        untuk satu Micro-Beat secara deterministik menggunakan FourTierMemoryAssembler (FTS5 BM25 <1ms).
        """
        from memory_manager import FourTierMemoryAssembler

        assembled = FourTierMemoryAssembler.assemble_four_tier_prompt(beat_id=beat_id, db_path=db_path)
        beat = assembled["beat"]
        sampler_params = cls.get_literary_sampler_params(
            target_words=int(beat.get("target_words", 400)),
            min_p=0.07,
            dry_multiplier=0.8,
            xtc_probability=0.1,
            id_slot=0,
        )
        assembled["sampler_params"] = sampler_params
        return assembled


    @classmethod
    def assemble_plot_architect_prompts(
        cls,
        chapter_id: str,
        db_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Merakit System & User Prompt untuk Persona 2: THE PLOT ARCHITECT
        guna memecah Chapter Goal menjadi daftar Micro-Beats JSON sesuai Pacing Engine.
        """
        chapter = get_chapter(chapter_id, db_path=db_path)
        if not chapter:
            raise ValueError(f"Chapter {chapter_id} tidak ditemukan.")

        bundle = get_story_bible_bundle(
            project_id=chapter["project_id"],
            chapter_number=chapter["chapter_number"],
            query_context=f"{chapter['title']} {chapter['chapter_goal']}",
            db_path=db_path,
        )
        project = bundle["project"]
        active_phase = bundle["active_phase"] or {}
        codex_all = list_codex_items(chapter["project_id"], db_path=db_path)

        t_min = chapter.get("tension_min") or active_phase.get("tension_min") or 15
        t_max = chapter.get("tension_max") or active_phase.get("tension_max") or 55

        plan = DeterministicPacingEngine.calculate_chapter_plan(
            target_words=int(chapter.get("target_word_count", 3200)),
            pacing_mode=str(chapter.get("pacing_mode", "BALANCED")),
            t_min=int(t_min),
            t_max=int(t_max),
        )

        entity_lines: List[str] = []
        for item in codex_all:
            if item["category"] in ("CHARACTER", "LOCATION"):
                entity_lines.append(
                    f"- [{item['category']}] {item['name']}: {item['core_description']}"
                )
        available_entities_str = (
            "\n".join(entity_lines)
            if entity_lines
            else "- Gunakan karakter dan lokasi yang disebutkan di tujuan bab."
        )

        mixing_directives = DeterministicPacingEngine.compile_mixing_directives(
            chapter, int(round((t_min + t_max) / 2))
        )

        system_prompt = PLOT_ARCHITECT_SYSTEM_PROMPT.format(
            total_micro_beats=plan["total_micro_beats"],
            pacing_mode=plan["pacing_mode"],
            target_word_count=chapter["target_word_count"],
            words_per_beat=plan["words_per_beat"],
            major_plot_events_needed=plan["major_plot_events_needed"],
            tension_curve_json=json.dumps(plan["tension_curve"]),
        )

        user_prompt = PLOT_ARCHITECT_USER_PROMPT.format(
            title=project["title"],
            genre=project["genre"],
            main_objective=project["main_objective"],
            phase_name=chapter.get("phase_name") or active_phase.get("phase_name") or "Fase Aktif",
            start_chapter=chapter.get("phase_start_chapter") or active_phase.get("start_chapter") or 1,
            end_chapter=chapter.get("phase_end_chapter") or active_phase.get("end_chapter") or project.get("total_planned_chapters", 24),
            building_focus=chapter.get("building_focus") or active_phase.get("building_focus") or "Pengembangan cerita bertahap.",
            phase_guardrails=chapter.get("phase_guardrails") or active_phase.get("phase_guardrails") or "Patuhi batas konflik fase ini.",
            rolling_global_summary=project.get("rolling_global_summary") or "Awal cerita.",
            available_entities=available_entities_str,
            chapter_number=chapter["chapter_number"],
            chapter_title=chapter["title"],
            chapter_goal=chapter["chapter_goal"],
            ending_hook_style=chapter.get("ending_hook_style") or "CLIFFHANGER",
            mixing_directives=mixing_directives,
            total_micro_beats=plan["total_micro_beats"],
        )

        return {
            "chapter": chapter,
            "project": project,
            "plan": plan,
            "codex_items": codex_all,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        }

    @classmethod
    def assemble_state_extractor_prompts(
        cls,
        beat_id: str,
        db_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Merakit System & User Prompt untuk Persona 3: POST-BEAT STATE EXTRACTOR
        guna memperbarui ringkasan bergulir dan current_state karakter pasca-penulisan beat.
        """
        beat = get_micro_beat(beat_id, db_path=db_path)
        if not beat:
            raise ValueError(f"Micro-Beat {beat_id} tidak ditemukan.")

        chapter = get_chapter(beat["chapter_id"], db_path=db_path)
        if not chapter:
            raise ValueError(f"Chapter {beat['chapter_id']} tidak ditemukan.")

        characters = list_codex_items(
            project_id=chapter["project_id"], category="CHARACTER", db_path=db_path
        )
        known_chars = [
            {
                "id": c["id"],
                "name": c["name"],
                "current_state": c.get("current_state", {}),
            }
            for c in characters
        ]

        user_prompt = POST_BEAT_STATE_EXTRACTOR_USER_PROMPT.format(
            chapter_number=chapter["chapter_number"],
            chapter_title=chapter["title"],
            beat_number=beat["beat_number"],
            beat_instruction=beat["beat_instruction"],
            known_characters_json=json.dumps(known_chars, ensure_ascii=False, indent=2),
            generated_prose=beat.get("generated_prose") or "",
        )

        return {
            "beat": beat,
            "chapter": chapter,
            "characters": characters,
            "system_prompt": POST_BEAT_STATE_EXTRACTOR_SYSTEM_PROMPT,
            "user_prompt": user_prompt,
        }

    @classmethod
    def build_deterministic_fallback_beats(
        cls,
        chapter: Dict[str, Any],
        plan: Dict[str, Any],
        codex_items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Fallback deterministik jika llama-server sedang offline atau mengembalikan JSON parsial,
        memastikan pembagian Micro-Beats sesuai mode pacing (SLOW_BURN / BALANCED / FAST_PACED)
        tetap terstruktur rapi tanpa kegagalan sistem.
        """
        total_beats = int(plan["total_micro_beats"])
        words_per_beat = int(plan["words_per_beat"])
        tension_curve = plan["tension_curve"]
        mode = plan["pacing_mode"]

        characters = [c for c in codex_items if c["category"] == "CHARACTER"]
        locations = [c for c in codex_items if c["category"] == "LOCATION"]
        default_pov_id = characters[0]["id"] if characters else None
        default_loc_id = locations[0]["id"] if locations else None

        goal_sentences = [
            s.strip()
            for s in re.split(r"[.;\n]+", chapter.get("chapter_goal", ""))
            if s.strip()
        ]
        if not goal_sentences:
            goal_sentences = [chapter.get("chapter_goal", "Pengembangan adegan utama bab ini.")]

        phase_roles = {
            "SLOW_BURN": [
                (
                    "Pembukaan Atmosfer & Jangkar Sensorik",
                    "Hadirkan suasana ruang secara imersif (cahaya, aroma, suara latar) dan bahasa tubuh awal karakter POV.",
                    "Karakter POV menyadari detail ganjil atau tanda pertama pemicu adegan.",
                ),
                (
                    "Interaksi Ber-Subteks & Observasi Psikologis",
                    "Bangun dialog pembuka yang penuh subteks atau penyelidikan objek sekitar sambil menggali reaksi batin.",
                    "Sebuah kalimat dialog atau temuan fisik mengubah arah percakapan secara tiba-tiba.",
                ),
                (
                    "Tindakan Konkret & Transisi Menggantung",
                    "Eksekusi keputusan utama karakter dalam kejadian ini dan hadirkan konsekuensi langsungnya.",
                    "Tindakan fisik menggantung tepat sebelum respons lawan bicara atau perubahan situasi berikutnya.",
                ),
            ],
            "BALANCED": [
                (
                    "Pembangunan Situasi & Gesekan Awal",
                    "Tempatkan karakter langsung di tengah situasi aktif dengan detail sensorik tajam dan pemicu konflik.",
                    "Ketegangan meningkat saat hambatan atau ketidaksepakatan muncul secara nyata.",
                ),
                (
                    "Eskalasi Konflik & Keputusan Tindakan",
                    "Pertajam benturan kepentingan melalui dialog dan aksi terukur yang mendorong plot maju.",
                    "Karakter mengambil langkah berisiko yang membuka jalan ke adegan selanjutnya.",
                ),
            ],
            "FAST_PACED": [
                (
                    "Aksi Langsung & Pertaruhan Cepat",
                    "Fokus pada pergerakan fisik cepat, keputusan instan, dan dampak langsung tanpa eksposisi lambat.",
                    "Benturan atau kejutan taktis tepat pada detik krusial.",
                )
            ],
            "FRENETIC_ACTION": [
                (
                    "Benturan Klimaks & Tempo Frenetik",
                    "Kalimat staccato pendek, pertukaran serangan/keputusan detik demi detik, adrenalin puncak tanpa jeda kontemplasi.",
                    "Potong tepat di puncak benturan fisik atau ancaman mematikan seketika.",
                )
            ],
        }

        role_templates = phase_roles.get(mode, phase_roles["BALANCED"])
        beats_out: List[Dict[str, Any]] = []

        for idx in range(total_beats):
            beat_num = idx + 1
            role_title, role_desc, stop_desc = role_templates[idx % len(role_templates)]
            event_idx = min(len(goal_sentences) - 1, int(idx * len(goal_sentences) / total_beats))
            focus_goal = goal_sentences[event_idx]

            if beat_num == total_beats:
                stop_desc = (
                    f"Berhenti tepat pada momen {chapter.get('ending_hook_style', 'CLIFFHANGER')} "
                    f"berupa tindakan fisik atau kalimat menggantung tanpa kesimpulan moral."
                )

            beats_out.append(
                {
                    "beat_number": beat_num,
                    "pov_character_id": default_pov_id,
                    "location_id": default_loc_id,
                    "tension_level": tension_curve[idx],
                    "target_words": words_per_beat,
                    "sensory_anchor": f"Pencahayaan kontras, tekstur objek sekitar, dan suara latar pada tahap {role_title.lower()}.",
                    "conflict_focus": f"{role_title}: {focus_goal}",
                    "beat_instruction": f"[{role_title}] Fokus pada bagian tujuan bab: '{focus_goal}'. {role_desc}",
                    "stopping_point": stop_desc,
                }
            )

        return beats_out


def parse_json_safely(raw_text: str) -> Optional[Any]:
    """Mengekstrak dan mem-parsing objek/array JSON dari respons LLM secara tahan banting."""
    if not raw_text:
        return None
    cleaned = raw_text.strip()
    # Bersihkan blok markdown ```json ... ``` jika ada
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned, flags=re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Cari kurung kurawal atau siku terluar
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(cleaned[first_brace : last_brace + 1])
        except json.JSONDecodeError:
            pass

    first_bracket = cleaned.find("[")
    last_bracket = cleaned.rfind("]")
    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        try:
            return json.loads(cleaned[first_bracket : last_bracket + 1])
        except json.JSONDecodeError:
            pass

    return None
