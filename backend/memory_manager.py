import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

from database import (
    DEFAULT_BANNED_PHRASES,
    add_episodic_memory,
    count_words,
    db_session,
    get_active_phase_for_chapter,
    get_chapter,
    get_codex_item,
    get_micro_beat,
    get_project,
    list_chapters,
    list_codex_items,
    list_micro_beats,
    update_chapter,
    update_codex_item,
    update_micro_beat,
    update_project,
)
from ai_provider import (
    build_chat_request,
    extract_nonstream_text,
    load_provider_config,
)
from engine import DeterministicPacingEngine, parse_json_safely


# ============================================================================
# 1. SQLITE FTS5 BM25 ENGINE (<1ms LATENCY, 0 MB RAM OVERHEAD)
# ============================================================================

INDONESIAN_AND_ENGLISH_STOPWORDS = {
    "yang", "dan", "di", "ke", "dari", "ini", "itu", "dengan", "untuk",
    "pada", "adalah", "dalam", "tidak", "akan", "atau", "juga", "sudah",
    "telah", "saat", "ketika", "karena", "namun", "tetapi", "mereka",
    "dia", "ia", "kami", "kita", "anda", "saya", "aku", "sebuah", "seorang",
    "para", "tersebut", "bisa", "dapat", "harus", "lebih", "sangat", "masih",
    "hanya", "baru", "រ", "lalu", "kemudian", "seperti", "oleh", "atas",
    "bawah", "depan", "belakang", "antara", "tanpa", "hingga", "sampai",
    "sebelum", "sesudah", "setelah", "tentang", "menjadi", "membuat",
    "fokus", "bagian", "tujuan", "bab", "beat", "adegan", "karakter",
    "the", "and", "for", "with", "from", "that", "this", "into", "upon",
}


class FTS5MemoryRetriever:
    """
    Mesin Pencarian Memori Teks Kilat berbasis SQLite FTS5 BM25.
    Mengekstrak kata kunci penting dari Micro-Beat (nama karakter, lokasi, artefak,
    kata benda konkret) dan melakukan pencarian BM25 pada:
    1. codex_fts (Karakter, Lokasi, Artefak/Item, Aturan Dunia, Lore)
    2. episodic_memory_fts (Memori kejadian spesifik per Beat lintas Bab)
    3. Ringkasan Bab Sebelumnya (chapters.chapter_summary)
    """

    @classmethod
    def extract_beat_keywords(
        cls,
        beat: Dict[str, Any],
        chapter: Dict[str, Any],
        known_entity_names: Optional[List[str]] = None,
        max_keywords: int = 22,
    ) -> List[str]:
        """
        Mengekstrak kata kunci berprioritas tinggi dari Micro-Beat yang akan ditulis:
        - Prioritas 1: Nama Karakter, Lokasi, atau Artefak yang disebut di instruksi beat.
        - Prioritas 2: Kata bermodifikasi huruf kapital (Proper Nouns) di instruksi beat & stopping point.
        - Prioritas 3: Kata benda / kata kerja kunci dari sensory_anchor, conflict_focus, dan chapter_goal.
        """
        raw_segments = [
            str(beat.get("pov_character_name") or ""),
            str(beat.get("location_name") or ""),
            str(beat.get("beat_instruction") or ""),
            str(beat.get("stopping_point") or ""),
            str(beat.get("sensory_anchor") or ""),
            str(beat.get("conflict_focus") or ""),
            str(chapter.get("title") or ""),
            str(chapter.get("chapter_goal") or ""),
        ]
        combined_text = " ".join(s for s in raw_segments if s)
        lower_combined = combined_text.lower()

        prioritized_tokens: List[str] = []
        seen: set = set()

        def _add_token(tok: str) -> None:
            clean = re.sub(r"[^a-z0-9_à-ÿ]", "", tok.lower())
            if len(clean) >= 3 and clean not in INDONESIAN_AND_ENGLISH_STOPWORDS and clean not in seen:
                seen.add(clean)
                prioritized_tokens.append(clean)

        # 1. Cek kecocokan langsung dengan nama entitas di Codex
        if known_entity_names:
            for name in known_entity_names:
                for part in re.findall(r"[A-Za-z0-9_À-ÿ]{3,}", name):
                    if part.lower() in lower_combined:
                        _add_token(part)

        # 2. Ambil kata berhuruf kapital (Proper Nouns: Nama orang, tempat, artefak)
        proper_nouns = re.findall(r"\b[A-Z][a-zA-Z0-9_À-ÿ]{2,}\b", combined_text)
        for pn in proper_nouns:
            _add_token(pn)

        # 3. Ambil seluruh token alfanumerik relevan lainnya
        all_tokens = re.findall(r"[A-Za-z0-9_À-ÿ]{3,}", lower_combined)
        for tok in all_tokens:
            _add_token(tok)
            if len(prioritized_tokens) >= max_keywords:
                break

        return prioritized_tokens[:max_keywords]

    @classmethod
    def build_fts5_match_expression(cls, keywords: List[str]) -> str:
        """Menyusun ekspresi query MATCH FTS5 dengan prefix matching yang aman."""
        safe_terms: List[str] = []
        for kw in keywords:
            clean = re.sub(r"[^a-z0-9_à-ÿ]", "", kw.lower())
            if len(clean) >= 3:
                safe_terms.append(f'"{clean}"*')
        return " OR ".join(safe_terms)

    @classmethod
    def retrieve_context_for_beat(
        cls,
        project_id: str,
        chapter: Dict[str, Any],
        beat: Dict[str, Any],
        codex_limit: int = 8,
        memory_limit: int = 6,
        db_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Menjalankan pencarian FTS5 BM25 sub-milidetik (<1ms) pada:
        - codex_fts (Lorebook, Karakter, Lokasi, Item)
        - episodic_memory_fts (Fakta adegan masa lalu lintas bab)
        - chapters (Ringkasan bab-bab sebelumnya)
        """
        t_start = time.perf_counter()

        with db_session(db_path) as conn:
            entity_rows = conn.execute(
                "SELECT name, aliases_and_tags, keywords_csv FROM codex_items WHERE project_id = ?",
                (project_id,),
            ).fetchall()
            known_names = [
                f"{r['name']} {r['aliases_and_tags']} {r['keywords_csv']}"
                for r in entity_rows
            ]

            keywords = cls.extract_beat_keywords(
                beat=beat,
                chapter=chapter,
                known_entity_names=known_names,
                max_keywords=22,
            )
            fts_expr = cls.build_fts5_match_expression(keywords)

            codex_matches: List[Dict[str, Any]] = []
            episodic_matches: List[Dict[str, Any]] = []
            past_chapter_summaries: List[Dict[str, Any]] = []

            if fts_expr:
                # 1. Query FTS5 BM25 pada codex_fts
                # Bobot kolom: name (10.0), aliases_and_tags (8.0), keywords_csv (8.0),
                # core_description (2.5), speech_style (1.0), current_state_text (2.0)
                codex_rows = conn.execute(
                    """
                    SELECT
                        c.*,
                        bm25(codex_fts, 0.0, 0.0, 0.0, 10.0, 8.0, 8.0, 2.5, 1.0, 2.0) AS bm25_rank
                    FROM codex_fts
                    JOIN codex_items c ON c.id = codex_fts.codex_id
                    WHERE codex_fts MATCH ?
                      AND c.project_id = ?
                    ORDER BY bm25_rank ASC
                    LIMIT ?
                    """,
                    (fts_expr, project_id, codex_limit),
                ).fetchall()

                for r in codex_rows:
                    item = dict(r)
                    try:
                        item["current_state"] = json.loads(item.get("current_state_json") or "{}")
                    except json.JSONDecodeError:
                        item["current_state"] = {}
                    codex_matches.append(item)

                # 2. Query FTS5 BM25 pada episodic_memory_fts (Bab sebelum atau sama dengan bab aktif)
                ep_rows = conn.execute(
                    """
                    SELECT
                        project_id,
                        CAST(chapter_number AS INTEGER) AS chapter_number,
                        beat_id,
                        keywords,
                        event_summary,
                        bm25(episodic_memory_fts, 0.0, 0.0, 0.0, 6.0, 3.0) AS bm25_rank
                    FROM episodic_memory_fts
                    WHERE episodic_memory_fts MATCH ?
                      AND project_id = ?
                      AND CAST(chapter_number AS INTEGER) <= ?
                      AND beat_id != ?
                    ORDER BY bm25_rank ASC
                    LIMIT ?
                    """,
                    (
                        fts_expr,
                        project_id,
                        int(chapter.get("chapter_number", 1)),
                        str(beat.get("id", "")),
                        memory_limit,
                    ),
                ).fetchall()
                episodic_matches = [dict(r) for r in ep_rows]

            # 3. Ambil ringkasan bab-bab sebelumnya (Previous Chapters Summary)
            prev_ch_rows = conn.execute(
                """
                SELECT chapter_number, title, chapter_summary
                FROM chapters
                WHERE project_id = ?
                  AND chapter_number < ?
                  AND TRIM(COALESCE(chapter_summary, '')) != ''
                ORDER BY chapter_number DESC
                LIMIT 4
                """,
                (project_id, int(chapter.get("chapter_number", 1))),
            ).fetchall()
            past_chapter_summaries = [dict(r) for r in reversed(prev_ch_rows)]

        elapsed_ms = round((time.perf_counter() - t_start) * 1000.0, 3)

        return {
            "extracted_keywords": keywords,
            "fts5_match_expression": fts_expr,
            "codex_matches": codex_matches,
            "episodic_matches": episodic_matches,
            "past_chapter_summaries": past_chapter_summaries,
            "elapsed_ms": elapsed_ms,
        }


# ============================================================================
# 2. DYNAMIC 4-TIER MEMORY CONTEXT ASSEMBLER
# ============================================================================

TIER1_AND_TIER2_SYSTEM_TEMPLATE = """Anda novelis fiksi sastra profesional. Tulis prosa hidup berbasis panca indra (Show, Don't Tell) dan dialog ber-subteks alami.

[TIER 1: STORY BIBLE & GUARDRAILS]
Judul: {title} ({genre})
Premis: {logline}
North Star: {main_objective}
POV & Tense: {pov_style} | {tense_style}
Tone: {tone_style}
Acuan Ritme Prosa: "{style_sample}"
Fase Aktif: {phase_name} (Bab {start_chapter}-{end_chapter}) | Fokus: {building_focus}
Guardrails Fase: {phase_guardrails}
Bab {chapter_number}: "{chapter_title}" — Tujuan: {chapter_goal}

[ATURAN DUNIA & LARANGAN]
{pinned_world_rules}
- Dilarang klise: {banned_phrases}
- Dilarang menutup adegan dengan refleksi moral atau rangkuman perasaan. Tunjukkan emosi lewat reaksi fisik/tindakan mikro.
- Wajib berhenti tepat pada [TITIK BERHENTI BEAT].

[TIER 2: CODEX & CHARACTER STATE]
Lokasi: {active_location_block}
Karakter:
{active_characters_block}{active_lore_and_items_block}"""


TIER3_AND_TIER4_USER_TEMPLATE = """[TIER 3: MEMORI & KONTINUITAS]
{rolling_summary_block}{fts5_memories_block}{current_chapter_beats_summary}{last_400_words_verbatim}
[TIER 4: TUGAS BEAT #{beat_number}/{total_beats}]
Pacing: {pacing_mode} | Tension: {tension_level}/100 | Target: {target_words} kata (Sisa bab: {remaining_words})
Mix: {mixing_directives}
Sensorik Wajib: {sensory_anchor}
Konflik Mikro: {conflict_focus}
Instruksi Beat: {beat_instruction}
TITIK BERHENTI BEAT: {stopping_point}

Tulis langsung kelanjutan prosa (~{target_words} kata) tanpa judul bab, label beat, maupun pengantar:"""


class FourTierMemoryAssembler:
    """
    Perakit Prompt Dinamis 4-Tier sesuai Spesifikasi Arsitektur Final:
    Tier 1 (Pinned Core: Premis & Guardrails)
      -> Tier 2 (Active Codex & Character State)
      -> Tier 3 (Rolling Summary + 400 kata terakhir dari beat sebelumnya + hasil FTS5 BM25)
      -> Tier 4 (Micro-Beat Task & Tension Level)
    """

    VERBATIM_TAIL_WORDS = 400

    @staticmethod
    def extract_last_n_words(text: str, max_words: int = 400) -> str:
        """Mengambil tepat N (400) kata terakhir dari beat sebelumnya untuk kontinuitas kalimat."""
        if not text or not text.strip():
            return "(Awal Bab — Belum ada teks naskah pada beat sebelumnya)"
        words = text.strip().split()
        if len(words) <= max_words:
            return " ".join(words)
        return " ".join(words[-max_words:])

    @staticmethod
    def _format_character_state_line(item: Dict[str, Any], role_tag: str = "KARAKTER") -> str:
        state = item.get("current_state") or {}
        if not isinstance(state, dict):
            state = {}
        parts = [
            f"Lokasi={state.get('location')}" if state.get("location") else "",
            f"Kondisi={state.get('condition')}" if state.get("condition") else "",
            f"Emosi={state.get('emotional_state')}" if state.get("emotional_state") else "",
            f"Inv={state.get('inventory')}" if state.get("inventory") and state.get("inventory") != "-" else "",
            f"Tahu={state.get('knowledge')}" if state.get("knowledge") and state.get("knowledge") != "-" else "",
        ]
        state_str = "; ".join(p for p in parts if p) or "Normal"
        speech = f" | Bicara: {item['speech_style']}" if (item.get("speech_style") or "").strip() else ""
        return f"* [{role_tag}] {item['name']}: {item['core_description']}{speech}\n  State: {state_str}"

    @classmethod
    def assemble_four_tier_prompt(
        cls,
        beat_id: str,
        db_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Merakit keseluruhan konteks 4-Tier untuk satu Micro-Beat beserta metrik FTS5 BM25.
        """
        beat = get_micro_beat(beat_id, db_path=db_path)
        if not beat:
            raise ValueError(f"Micro-Beat {beat_id} tidak ditemukan.")

        chapter = get_chapter(beat["chapter_id"], db_path=db_path)
        if not chapter:
            raise ValueError(f"Chapter {beat['chapter_id']} tidak ditemukan.")

        project = get_project(chapter["project_id"], db_path=db_path)
        if not project:
            raise ValueError(f"Project {chapter['project_id']} tidak ditemukan.")

        active_phase = get_active_phase_for_chapter(
            project["id"], int(chapter["chapter_number"]), db_path=db_path
        ) or {}

        # 1. Jalankan pencarian FTS5 BM25 (<1ms) untuk Beat ini
        fts_bundle = FTS5MemoryRetriever.retrieve_context_for_beat(
            project_id=project["id"],
            chapter=chapter,
            beat=beat,
            codex_limit=4,
            memory_limit=3,
            db_path=db_path,
        )

        # 2. Ambil seluruh Pinned Codex Items (is_pinned = 1)
        pinned_codex = list_codex_items(
            project_id=project["id"], pinned_only=True, db_path=db_path
        )

        # 3. Kumpulkan Beat sebelumnya di bab yang sama (atau bab sebelumnya jika ini Beat #1)
        all_beats = list_micro_beats(chapter["id"], db_path=db_path)
        total_beats = max(1, len(all_beats))
        prior_beats = [b for b in all_beats if int(b["beat_number"]) < int(beat["beat_number"])]

        words_written_in_chapter = 0
        last_prose_source = ""
        current_chapter_beat_summaries: List[str] = []

        for pb in prior_beats:
            words_written_in_chapter += int(pb.get("actual_words") or 0)
            if (pb.get("generated_prose") or "").strip():
                last_prose_source = pb["generated_prose"].strip()
            sum_txt = (pb.get("extracted_summary") or "").strip() or (pb.get("beat_instruction") or "").strip()
            if sum_txt:
                current_chapter_beat_summaries.append(f"- Beat #{pb['beat_number']}: {sum_txt}")

        # Jika ini Beat #1 di Bab > 1 dan belum ada teks di bab ini, ambil ekor teks dari beat terakhir bab sebelumnya
        if not last_prose_source and int(chapter["chapter_number"]) > 1:
            with db_session(db_path) as conn:
                prev_beat_row = conn.execute(
                    """
                    SELECT mb.generated_prose
                    FROM micro_beats mb
                    JOIN chapters c ON mb.chapter_id = c.id
                    WHERE c.project_id = ?
                      AND c.chapter_number < ?
                      AND TRIM(COALESCE(mb.generated_prose, '')) != ''
                    ORDER BY c.chapter_number DESC, mb.beat_number DESC
                    LIMIT 1
                    """,
                    (project["id"], int(chapter["chapter_number"])),
                ).fetchone()
                if prev_beat_row:
                    last_prose_source = prev_beat_row["generated_prose"].strip()

        last_400_words = cls.extract_last_n_words(
            last_prose_source, max_words=cls.VERBATIM_TAIL_WORDS
        )
        remaining_words = max(
            int(beat.get("target_words", 400)),
            int(chapter.get("target_word_count", 3200)) - words_written_in_chapter,
        )

        # ====================================================================
        # RAKIT TIER 1: PINNED CORE (PREMIS, NORTH STAR, & PHASE GUARDRAILS)
        # ====================================================================
        seen_entity_ids: set = set()
        pinned_rules = []
        for item in pinned_codex:
            if item["category"] in ("WORLD_RULE", "LORE"):
                seen_entity_ids.add(item["id"])
                pinned_rules.append(f"- [{item['category']}] {item['name']}: {item['core_description']}")
        pinned_world_rules_str = (
            "\n".join(pinned_rules)
            if pinned_rules
            else "- Jaga konsistensi hukum dunia dan logika sebab-akibat sesuai genre novel."
        )

        banned_list = project.get("banned_phrases") or DEFAULT_BANNED_PHRASES
        banned_phrases_str = ", ".join(f'"{p}"' for p in banned_list)

        # ====================================================================
        # RAKIT TIER 2: ACTIVE CODEX & CHARACTER STATE
        # ====================================================================
        # A. Lokasi Aktif
        active_location_block = beat.get("location_name") or "Sesuai konteks adegan"
        if beat.get("location_id"):
            loc_item = get_codex_item(beat["location_id"], db_path=db_path)
            if loc_item:
                loc_state = loc_item.get("current_state") or {}
                loc_notes = [x for x in (loc_state.get("condition"), loc_state.get("emotional_state")) if x]
                suffix = f" ({'; '.join(loc_notes)})" if loc_notes else ""
                active_location_block = f"{loc_item['name']} — {loc_item['core_description']}{suffix}"

        # B. Karakter Aktif (POV + Pinned Characters + BM25 Retrieved Characters)
        char_blocks: List[str] = []

        if beat.get("pov_character_id"):
            pov_char = get_codex_item(beat["pov_character_id"], db_path=db_path)
            if pov_char:
                seen_entity_ids.add(pov_char["id"])
                char_blocks.append(cls._format_character_state_line(pov_char, "POV"))

        for item in pinned_codex + fts_bundle["codex_matches"]:
            if item["category"] == "CHARACTER" and item["id"] not in seen_entity_ids:
                seen_entity_ids.add(item["id"])
                tag = "PINNED" if item.get("is_pinned") else "BM25"
                char_blocks.append(cls._format_character_state_line(item, tag))

        active_characters_block = (
            "\n".join(char_blocks)
            if char_blocks
            else "- Gunakan karakter sesuai instruksi beat dan tujuan bab."
        )

        # C. Artefak / Item / Lokasi / Lore hasil BM25 (tanpa duplikasi rule yg sudah di Tier 1)
        lore_and_items_lines: List[str] = []
        for item in pinned_codex + fts_bundle["codex_matches"]:
            if item["category"] != "CHARACTER" and item["id"] not in seen_entity_ids:
                if item["id"] == beat.get("location_id"):
                    continue
                seen_entity_ids.add(item["id"])
                st = item.get("current_state") or {}
                st_parts = [x for x in (st.get("location"), st.get("condition")) if x and x not in ("-", "Sehat")]
                st_note = f" ({', '.join(st_parts)})" if st_parts else ""
                lore_and_items_lines.append(
                    f"- [{item['category']}] {item['name']}: {item['core_description']}{st_note}"
                )

        active_lore_and_items_block = (
            "\nLore/Item FTS5:\n" + "\n".join(lore_and_items_lines)
            if lore_and_items_lines
            else ""
        )

        # ====================================================================
        # RAKIT TIER 3: ROLLING SUMMARY + KONTINUITAS + FTS5 BM25
        # ====================================================================
        rolling_parts: List[str] = []
        if (project.get("rolling_global_summary") or "").strip():
            rolling_parts.append(f"Ringkasan Global: {project['rolling_global_summary'].strip()}")
        for pch in fts_bundle["past_chapter_summaries"]:
            rolling_parts.append(
                f"- Bab {pch['chapter_number']} ({pch['title']}): {pch['chapter_summary']}"
            )
        rolling_summary_block = (
            ("\n".join(rolling_parts) + "\n")
            if rolling_parts
            else "Ringkasan: Awal cerita, bangun fondasi adegan.\n"
        )

        fts5_memory_lines = [
            f"- [Bab {m['chapter_number']}] {m['event_summary']}"
            for m in fts_bundle["episodic_matches"]
        ]
        fts5_memories_block = (
            "Memori Lampau (FTS5):\n" + "\n".join(fts5_memory_lines) + "\n"
            if fts5_memory_lines
            else ""
        )

        current_chapter_beats_str = (
            f"Beat Sebelumnya di Bab {chapter['chapter_number']}:\n"
            + "\n".join(current_chapter_beat_summaries[-4:])
            + "\n"
            if current_chapter_beat_summaries
            else ""
        )

        last_prose_block = (
            f"Sambungan Teks Terakhir:\n...{last_400_words}\n\n"
            if (last_prose_source or "").strip()
            else "\n"
        )

        # ====================================================================
        # RAKIT TIER 4: MICRO-BEAT TASK, NARRATIVE MIX, & TENSION LEVEL
        # ====================================================================
        mixing_directives = DeterministicPacingEngine.compile_mixing_directives(
            chapter, int(beat.get("tension_level", 35))
        )

        static_system_prompt = TIER1_AND_TIER2_SYSTEM_TEMPLATE.format(
            title=project["title"],
            genre=project["genre"],
            logline=project.get("logline") or "-",
            main_objective=project["main_objective"],
            pov_style=project.get("pov_style") or "Third-Person Limited",
            tense_style=project.get("tense_style") or "Lampau / Past Narrative",
            tone_style=project.get("tone_style") or "Atmosferik, Imersif, Show Dont Tell",
            style_sample=project.get("style_sample")
            or "Kalimat memiliki ritme bervariasi, mengutamakan kata benda dan kata kerja konkret di atas kata sifat abstrak.",
            phase_name=chapter.get("phase_name") or active_phase.get("phase_name") or "Fase Struktur Aktif",
            start_chapter=chapter.get("phase_start_chapter") or active_phase.get("start_chapter") or 1,
            end_chapter=chapter.get("phase_end_chapter") or active_phase.get("end_chapter") or project.get("total_planned_chapters", 24),
            building_focus=chapter.get("building_focus") or active_phase.get("building_focus") or "Pengembangan karakter dan plot bertahap.",
            phase_guardrails=chapter.get("phase_guardrails") or active_phase.get("phase_guardrails") or "Patuhi batas konflik fase ini.",
            chapter_number=chapter["chapter_number"],
            chapter_title=chapter["title"],
            chapter_goal=chapter["chapter_goal"],
            pinned_world_rules=pinned_world_rules_str,
            banned_phrases=banned_phrases_str,
            active_location_block=active_location_block,
            active_characters_block=active_characters_block,
            active_lore_and_items_block=active_lore_and_items_block,
        )

        dynamic_user_prompt = TIER3_AND_TIER4_USER_TEMPLATE.format(
            rolling_summary_block=rolling_summary_block,
            fts5_memories_block=fts5_memories_block,
            chapter_number=chapter["chapter_number"],
            current_chapter_beats_summary=current_chapter_beats_str,
            last_400_words_verbatim=last_prose_block,
            beat_number=beat["beat_number"],
            total_beats=total_beats,
            pacing_mode=chapter.get("pacing_mode", "BALANCED"),
            tension_level=beat.get("tension_level", 35),
            target_words=beat.get("target_words", 400),
            remaining_words=remaining_words,
            mixing_directives=mixing_directives,
            sensory_anchor=beat.get("sensory_anchor")
            or "Hadirkan minimal 3 panca indra konkret (cahaya, suara latar, suhu/bau).",
            conflict_focus=beat.get("conflict_focus")
            or "Pertahankan ketegangan subteks dan tujuan karakter di adegan ini.",
            beat_instruction=beat["beat_instruction"],
            stopping_point=beat["stopping_point"],
        )

        return {
            "beat": beat,
            "chapter": chapter,
            "project": project,
            "static_system_prompt": static_system_prompt,
            "dynamic_user_prompt": dynamic_user_prompt,
            "full_4tier_prompt": f"{static_system_prompt}\n\n{dynamic_user_prompt}",
            "fts5_telemetry": {
                "elapsed_ms": fts_bundle["elapsed_ms"],
                "extracted_keywords": fts_bundle["extracted_keywords"],
                "fts5_match_expression": fts_bundle["fts5_match_expression"],
                "codex_hits_count": len(fts_bundle["codex_matches"]),
                "episodic_hits_count": len(fts_bundle["episodic_matches"]),
            },
            "tiers_breakdown": {
                "tier_1_pinned_core": {
                    "phase_name": chapter.get("phase_name") or active_phase.get("phase_name"),
                    "phase_guardrails": chapter.get("phase_guardrails") or active_phase.get("phase_guardrails"),
                    "pinned_rules_count": len(pinned_rules),
                },
                "tier_2_active_codex_state": {
                    "active_location": beat.get("location_name"),
                    "active_pov": beat.get("pov_character_name"),
                    "matched_codex_names": [c["name"] for c in fts_bundle["codex_matches"]],
                },
                "tier_3_memory_and_verbatim": {
                    "verbatim_word_count": count_words(last_400_words),
                    "verbatim_text": last_400_words,
                    "episodic_memories": fts_bundle["episodic_matches"],
                    "past_chapter_summaries_count": len(fts_bundle["past_chapter_summaries"]),
                },
                "tier_4_beat_task": {
                    "beat_number": beat["beat_number"],
                    "total_beats": total_beats,
                    "tension_level": beat.get("tension_level", 35),
                    "target_words": beat.get("target_words", 400),
                    "remaining_words": remaining_words,
                },
            },
        }


# ============================================================================
# 3. POST-BEAT STATE EXTRACTOR (FAST LLAMA-SERVER PROMPT + SQLITE AUTO-UPDATE)
# ============================================================================

FAST_STATE_EXTRACTOR_SYSTEM_PROMPT = """Anda adalah POST-BEAT STATE EXTRACTOR untuk mesin kontinuitas novel.
Baca teks prosa Micro-Beat yang baru selesai ditulis dan ekstrak perubahan faktual pada karakter, inventaris, lokasi, serta ringkasan kejadian.

Keluarkan HANYA JSON valid dengan struktur persis berikut:
{
  "beat_summary": "Ringkasan padat 1-2 kalimat tentang apa yang baru saja terjadi di beat ini.",
  "episodic_keywords": "kata, kunci, penting, nama, karakter, lokasi, artefak",
  "character_updates": [
    {
      "name": "Nama Karakter",
      "location": "Lokasi baru karakter saat akhir beat (kosongkan jika tidak berubah)",
      "condition": "Kondisi fisik terkini (misal: Sehat / Terluka di lengan / Kelelahan)",
      "emotional_state": "Kondisi emosi saat akhir beat",
      "inventory": "Barang/artefak yang dipegang, ditemukan, atau hilang di beat ini",
      "knowledge": "Fakta, petunjuk, atau rahasia baru yang diketahui karakter di beat ini"
    }
  ],
  "location_updates": [
    {
      "name": "Nama Lokasi",
      "condition": "Perubahan kondisi fisik lokasi jika ada (misal: Pintu gudang terbuka paksa / Terbakar)"
    }
  ]
}"""

FAST_STATE_EXTRACTOR_USER_PROMPT = """[IDENTITAS ADEGAN]
Bab {chapter_number}: "{chapter_title}" — Micro-Beat #{beat_number}
Lokasi Adegan: {location_name}
Instruksi Beat: {beat_instruction}

[DAFTAR KARAKTER & STATE SEBELUMNYA]
{characters_state_json}

[NASKAH PROSA BEAT YANG BARU SELESAI DITULIS]
{generated_prose}

Hasilkan JSON ekstraksi state sekarang:"""


class PostBeatStateExtractor:
    """
    Mengekstrak perubahan state pasca-penulisan Micro-Beat menggunakan prompt kilat
    ke llama-server (atau fallback heuristik deterministik jika llama-server offline)
    dan memperbarui tabel-tabel SQLite secara otomatis:
    - micro_beats.extracted_summary
    - episodic_memory_fts (indeks FTS5 BM25)
    - codex_items.current_state_json (location, condition, emotional_state, inventory, knowledge)
    - chapters.chapter_summary
    - projects.rolling_global_summary
    """

    @classmethod
    def build_extractor_prompts(
        cls,
        beat_id: str,
        db_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        beat = get_micro_beat(beat_id, db_path=db_path)
        if not beat:
            raise ValueError(f"Micro-Beat {beat_id} tidak ditemukan.")

        chapter = get_chapter(beat["chapter_id"], db_path=db_path)
        if not chapter:
            raise ValueError(f"Chapter {beat['chapter_id']} tidak ditemukan.")

        characters = list_codex_items(
            project_id=chapter["project_id"], category="CHARACTER", db_path=db_path
        )
        locations = list_codex_items(
            project_id=chapter["project_id"], category="LOCATION", db_path=db_path
        )

        prose_and_inst = f"{beat.get('generated_prose') or ''} {beat.get('beat_instruction') or ''}".lower()
        relevant_chars = [
            c for c in characters
            if c["id"] == beat.get("pov_character_id")
            or c["name"].lower() in prose_and_inst
            or c["name"].split()[0].lower() in prose_and_inst
        ]
        if not relevant_chars:
            relevant_chars = characters[:5]

        char_snapshot = [
            {
                "id": c["id"],
                "name": c["name"],
                "current_state": c.get("current_state", {}),
            }
            for c in relevant_chars[:6]
        ]

        user_prompt = FAST_STATE_EXTRACTOR_USER_PROMPT.format(
            chapter_number=chapter["chapter_number"],
            chapter_title=chapter["title"],
            beat_number=beat["beat_number"],
            location_name=beat.get("location_name") or "Lokasi Adegan",
            beat_instruction=beat["beat_instruction"],
            characters_state_json=json.dumps(char_snapshot, ensure_ascii=False, indent=2),
            generated_prose=beat.get("generated_prose") or "",
        )

        return {
            "beat": beat,
            "chapter": chapter,
            "characters": characters,
            "locations": locations,
            "system_prompt": FAST_STATE_EXTRACTOR_SYSTEM_PROMPT,
            "user_prompt": user_prompt,
        }

    @classmethod
    def heuristic_extract(
        cls,
        beat: Dict[str, Any],
        characters: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Ekstraktor deterministik lokal cepat (<1ms) apabila llama-server sedang tidak aktif,
        menjamin ekstraksi ringkasan, kata kunci FTS5, inventaris, dan lokasi karakter tetap berjalan.
        """
        prose = (beat.get("generated_prose") or "").strip()
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", prose) if s.strip()]
        if len(sentences) >= 2:
            summary = f"{sentences[0]} {sentences[-1]}"
        elif sentences:
            summary = sentences[0]
        else:
            summary = beat.get("beat_instruction", "")

        if len(summary) > 360:
            summary = summary[:357].rsplit(" ", 1)[0] + "..."

        tokens = re.findall(r"[A-Za-z0-9_À-ÿ]{4,}", prose.lower())
        freq: Dict[str, int] = {}
        for t in tokens:
            if t not in INDONESIAN_AND_ENGLISH_STOPWORDS:
                freq[t] = freq.get(t, 0) + 1
        top_kw = sorted(freq.keys(), key=lambda k: freq[k], reverse=True)[:12]

        # Deteksi objek/inventaris umum di dekat kata kerja kepemilikan
        inv_matches = re.findall(
            r"\b(?:memegang|menggenggam|menyimpan|membawa|mengambil|menemukan|mencabut)\s+([a-zA-Z0-9_À-ÿ\s]{3,25}?)(?:[.,;]|dan\b|yang\b|di\b|ke\b)",
            prose,
            flags=re.IGNORECASE,
        )
        detected_inventory = ", ".join(m.strip() for m in inv_matches[:2]) if inv_matches else ""

        char_updates: List[Dict[str, Any]] = []
        for ch in characters:
            first_name = ch["name"].split()[0].lower()
            if ch["name"].lower() in prose.lower() or first_name in prose.lower():
                cur_state = ch.get("current_state") or {}
                char_updates.append(
                    {
                        "name": ch["name"],
                        "location": beat.get("location_name") or cur_state.get("location", ""),
                        "condition": cur_state.get("condition", "Sehat"),
                        "emotional_state": cur_state.get("emotional_state", "Waspada"),
                        "inventory": detected_inventory or cur_state.get("inventory", ""),
                        "knowledge": summary[:160],
                    }
                )

        return {
            "beat_summary": summary,
            "episodic_keywords": ", ".join(top_kw),
            "character_updates": char_updates,
            "location_updates": [],
        }

    @classmethod
    async def extract_and_persist_state(
        cls,
        beat_id: str,
        llama_chat_url: str = "http://127.0.0.1:8080/v1/chat/completions",
        llama_completion_url: str = "http://127.0.0.1:8080/completion",
        mode: str = "auto",
        provider_cfg: Optional[Dict[str, Any]] = None,
        db_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Memanggil mesin AI aktif (lokal llama-server / OpenAI-compatible / Anthropic) dengan prompt
        kilat khusus (mode='auto') atau ekstraktor heuristik deterministik lokal <1ms (mode='fast_local')
        dan memperbarui seluruh tabel kontinuitas di SQLite secara otomatis.
        """
        ctx = cls.build_extractor_prompts(beat_id, db_path=db_path)
        beat = ctx["beat"]
        chapter = ctx["chapter"]
        characters = ctx["characters"]
        locations = ctx["locations"]

        prose = (beat.get("generated_prose") or "").strip()
        if not prose:
            raise ValueError("Micro-Beat belum memiliki teks prosa (generated_prose kosong).")

        base_llama_url = llama_chat_url.split("/v1/")[0] if "/v1/" in llama_chat_url else "http://127.0.0.1:8080"
        cfg = provider_cfg or load_provider_config(base_llama_url)
        ptype = str(cfg.get("provider_type") or "local_llama").lower()

        llm_parsed: Optional[Dict[str, Any]] = None
        extraction_source = "llama_server_extractor" if ptype == "local_llama" else f"{ptype}_extractor"

        local_sampler = {
            "cache_prompt": False,
            "id_slot": 0,
            "max_tokens": 650,
            "temperature": 0.2,
            "min_p": 0.07,
            "repeat_penalty": 1.05,
        }

        if mode != "fast_local" and httpx is not None:
            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    if ptype == "local_llama":
                        url = llama_chat_url
                        headers = {"Content-Type": "application/json"}
                        chat_payload = {
                            "messages": [
                                {"role": "system", "content": ctx["system_prompt"]},
                                {"role": "user", "content": ctx["user_prompt"]},
                            ],
                            "stream": False,
                            **local_sampler,
                        }
                    else:
                        url, headers, chat_payload = build_chat_request(
                            provider_cfg=cfg,
                            system_prompt=ctx["system_prompt"],
                            user_prompt=ctx["user_prompt"],
                            max_tokens=650,
                            temperature=0.2,
                            stream=False,
                        )

                    resp = await client.post(url, headers=headers, json=chat_payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_content = extract_nonstream_text(ptype, data)
                        parsed = parse_json_safely(raw_content)
                        if isinstance(parsed, dict):
                            llm_parsed = parsed
                    elif ptype == "local_llama":
                        raw_payload = {
                            "prompt": f"{ctx['system_prompt']}\n\n{ctx['user_prompt']}\n",
                            "stream": False,
                            "cache_prompt": False,
                            "id_slot": 0,
                            "n_predict": 650,
                            "temperature": 0.2,
                            "min_p": 0.07,
                        }
                        resp2 = await client.post(llama_completion_url, json=raw_payload)
                        if resp2.status_code == 200:
                            parsed2 = parse_json_safely(resp2.json().get("content", ""))
                            if isinstance(parsed2, dict):
                                llm_parsed = parsed2
            except Exception:
                llm_parsed = None

        if not llm_parsed or not llm_parsed.get("beat_summary"):
            extraction_source = "deterministic_heuristic_extractor"
            extracted = cls.heuristic_extract(beat, characters)
        else:
            extracted = llm_parsed

        beat_summary = str(extracted.get("beat_summary") or "").strip()
        episodic_keywords = str(
            extracted.get("episodic_keywords") or beat.get("beat_instruction", "")
        ).strip()
        char_updates_list = extracted.get("character_updates") or []
        loc_updates_list = extracted.get("location_updates") or []

        # 1. Perbarui extracted_summary di tabel micro_beats
        update_micro_beat(beat_id, {"extracted_summary": beat_summary}, db_path=db_path)

        # 2. Simpan/Perbarui memori episodik di FTS5 (episodic_memory_fts)
        add_episodic_memory(
            project_id=chapter["project_id"],
            chapter_number=int(chapter["chapter_number"]),
            beat_id=beat_id,
            keywords=episodic_keywords,
            event_summary=f"[Bab {chapter['chapter_number']} Beat {beat['beat_number']}] {beat_summary}",
            db_path=db_path,
        )

        # 3. Perbarui current_state karakter di codex_items ( otomatis tersinkron ke codex_fts lewat Trigger)
        updated_characters: List[Dict[str, Any]] = []
        char_lookup: Dict[str, Dict[str, Any]] = {}
        for c in characters:
            char_lookup[c["name"].strip().lower()] = c
            first_tok = c["name"].strip().split()[0].lower()
            if first_tok not in char_lookup:
                char_lookup[first_tok] = c

        if isinstance(char_updates_list, list):
            for upd in char_updates_list:
                if not isinstance(upd, dict) or not upd.get("name"):
                    continue
                key = str(upd["name"]).strip().lower()
                target_char = char_lookup.get(key) or char_lookup.get(key.split()[0])
                if not target_char:
                    continue

                merged_state = dict(target_char.get("current_state") or {})
                for field in ("location", "condition", "emotional_state", "inventory", "knowledge"):
                    val = str(upd.get(field) or "").strip()
                    if val:
                        merged_state[field] = val

                saved_char = update_codex_item(
                    target_char["id"],
                    {"current_state": merged_state},
                    db_path=db_path,
                )
                if saved_char:
                    updated_characters.append(saved_char)

        # 4. Perbarui kondisi lokasi di codex_items jika ada perubahan
        updated_locations: List[Dict[str, Any]] = []
        loc_lookup = {loc["name"].strip().lower(): loc for loc in locations}
        if isinstance(loc_updates_list, list):
            for l_upd in loc_updates_list:
                if not isinstance(l_upd, dict) or not l_upd.get("name"):
                    continue
                target_loc = loc_lookup.get(str(l_upd["name"]).strip().lower())
                if not target_loc:
                    continue
                loc_state = dict(target_loc.get("current_state") or {})
                if l_upd.get("condition"):
                    loc_state["condition"] = str(l_upd["condition"]).strip()
                saved_loc = update_codex_item(
                    target_loc["id"],
                    {"current_state": loc_state},
                    db_path=db_path,
                )
                if saved_loc:
                    updated_locations.append(saved_loc)

        # 5. Perbarui chapter_summary & rolling_global_summary
        all_chapter_beats = list_micro_beats(chapter["id"], db_path=db_path)
        beat_summaries = [
            f"Beat {b['beat_number']}: {b['extracted_summary']}"
            for b in all_chapter_beats
            if (b.get("extracted_summary") or "").strip()
        ]
        new_chapter_summary = " | ".join(beat_summaries)
        update_chapter(chapter["id"], {"chapter_summary": new_chapter_summary}, db_path=db_path)

        all_chapters = list_chapters(chapter["project_id"], db_path=db_path)
        chapter_summary_blocks: List[str] = []
        for ch in all_chapters:
            ch_sum = ch["chapter_summary"] if ch["id"] != chapter["id"] else new_chapter_summary
            if (ch_sum or "").strip():
                chapter_summary_blocks.append(f"Bab {ch['chapter_number']} ({ch['title']}): {ch_sum}")

        rolling_summary_full = "\n".join(chapter_summary_blocks)
        rolling_words = rolling_summary_full.split()
        if len(rolling_words) > 600:
            rolling_summary_full = "... " + " ".join(rolling_words[-600:])

        updated_project = update_project(
            chapter["project_id"],
            {"rolling_global_summary": rolling_summary_full},
            db_path=db_path,
        )

        return {
            "beat_id": beat_id,
            "extraction_source": extraction_source,
            "beat_summary": beat_summary,
            "episodic_keywords": episodic_keywords,
            "updated_characters": updated_characters,
            "updated_locations": updated_locations,
            "chapter_summary": new_chapter_summary,
            "rolling_global_summary": (updated_project or {}).get("rolling_global_summary", ""),
        }
