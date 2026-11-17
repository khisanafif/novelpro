import json
import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional

DB_PATH = os.environ.get("NOVEL_STUDIO_DB", os.path.join(os.path.dirname(__file__), "novel_studio.db"))

DEFAULT_BANNED_PHRASES = [
    "tanpa mereka sadari",
    "waktu seakan berhenti",
    "menghela napas berat",
    "baru saja dimulai",
    "sebuah simfoni",
    "entah mengapa",
    "takdir berkata lain",
    "hanya waktu yang bisa menjawab",
]

DDL_SCRIPT = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA temp_store=MEMORY;
PRAGMA cache_size=-8000;
PRAGMA foreign_keys=ON;

-- 1. Tabel Projects (Master Novel / Story Bible)
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    author_name TEXT DEFAULT 'Penulis Studio',
    genre TEXT NOT NULL,
    logline TEXT DEFAULT '',
    main_objective TEXT NOT NULL,
    pov_style TEXT DEFAULT 'Third-Person Limited',
    tense_style TEXT DEFAULT 'Lampau / Past Narrative',
    tone_style TEXT DEFAULT 'Atmosferik, Imersif, Show Dont Tell',
    style_sample TEXT DEFAULT '',
    banned_phrases_json TEXT DEFAULT '["tanpa mereka sadari", "waktu seakan berhenti", "menghela napas berat", "baru saja dimulai", "sebuah simfoni"]',
    total_planned_chapters INTEGER DEFAULT 24,
    default_chapter_words INTEGER DEFAULT 3200,
    rolling_global_summary TEXT DEFAULT '',
    active_model_profile TEXT DEFAULT 'Qwen2.5-3B-Instruct-Q4_K_M',
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- 2. Tabel Story Phases (Rentang Bab X s.d. Bab Y & Guardrails)
CREATE TABLE IF NOT EXISTS story_phases (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    phase_order INTEGER NOT NULL,
    phase_name TEXT NOT NULL,
    start_chapter INTEGER NOT NULL,
    end_chapter INTEGER NOT NULL,
    default_pacing TEXT DEFAULT 'BALANCED',
    tension_min INTEGER DEFAULT 15,
    tension_max INTEGER DEFAULT 45,
    building_focus TEXT NOT NULL,
    phase_guardrails TEXT NOT NULL,
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    CHECK (start_chapter <= end_chapter),
    CHECK (tension_min >= 0 AND tension_max <= 100 AND tension_min <= tension_max)
);

CREATE INDEX IF NOT EXISTS idx_story_phases_project_range
    ON story_phases(project_id, start_chapter, end_chapter);

-- 3. Tabel Codex Items (Karakter, Lokasi, Aturan Dunia, Item)
CREATE TABLE IF NOT EXISTS codex_items (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    category TEXT NOT NULL CHECK (category IN ('CHARACTER', 'LOCATION', 'WORLD_RULE', 'ITEM', 'LORE')),
    name TEXT NOT NULL,
    aliases_and_tags TEXT NOT NULL DEFAULT '',
    keywords_csv TEXT NOT NULL DEFAULT '',
    is_pinned INTEGER DEFAULT 0,
    core_description TEXT NOT NULL,
    speech_style TEXT DEFAULT '',
    current_state_json TEXT DEFAULT '{"location": "", "condition": "Sehat", "knowledge": "", "emotional_state": "Stabil"}',
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_codex_items_project_cat
    ON codex_items(project_id, category, is_pinned);

-- 4. Virtual Table FTS5 BM25 untuk Codex (Auto-Retrieval <1ms Tanpa Vector DB)
CREATE VIRTUAL TABLE IF NOT EXISTS codex_fts USING fts5(
    codex_id UNINDEXED,
    project_id UNINDEXED,
    category UNINDEXED,
    name,
    aliases_and_tags,
    keywords_csv,
    core_description,
    speech_style,
    current_state_text,
    tokenize='unicode61 remove_diacritics 1'
);

-- Triggers Sinkronisasi Otomatis codex_items -> codex_fts
CREATE TRIGGER IF NOT EXISTS trg_codex_items_ai AFTER INSERT ON codex_items BEGIN
    INSERT INTO codex_fts(
        rowid, codex_id, project_id, category, name, aliases_and_tags,
        keywords_csv, core_description, speech_style, current_state_text
    ) VALUES (
        new.rowid, new.id, new.project_id, new.category, new.name, new.aliases_and_tags,
        new.keywords_csv, new.core_description, new.speech_style, new.current_state_json
    );
END;

CREATE TRIGGER IF NOT EXISTS trg_codex_items_ad AFTER DELETE ON codex_items BEGIN
    DELETE FROM codex_fts WHERE rowid = old.rowid;
END;

CREATE TRIGGER IF NOT EXISTS trg_codex_items_au AFTER UPDATE ON codex_items BEGIN
    DELETE FROM codex_fts WHERE rowid = old.rowid;
    INSERT INTO codex_fts(
        rowid, codex_id, project_id, category, name, aliases_and_tags,
        keywords_csv, core_description, speech_style, current_state_text
    ) VALUES (
        new.rowid, new.id, new.project_id, new.category, new.name, new.aliases_and_tags,
        new.keywords_csv, new.core_description, new.speech_style, new.current_state_json
    );
END;

-- 5. Virtual Table FTS5 untuk Memori Episodik Lintas Bab (Bagian 7 Blueprint)
CREATE VIRTUAL TABLE IF NOT EXISTS episodic_memory_fts USING fts5(
    project_id UNINDEXED,
    chapter_number UNINDEXED,
    beat_id UNINDEXED,
    keywords,
    event_summary,
    tokenize='unicode61 remove_diacritics 1'
);

-- 6. Tabel Chapters (Konfigurasi Bab & 5 Slider Narrative Mix)
CREATE TABLE IF NOT EXISTS chapters (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    phase_id TEXT REFERENCES story_phases(id) ON DELETE SET NULL,
    chapter_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    chapter_goal TEXT NOT NULL,
    target_word_count INTEGER NOT NULL DEFAULT 3200,
    current_word_count INTEGER DEFAULT 0,
    pacing_mode TEXT DEFAULT 'BALANCED' CHECK (pacing_mode IN ('SLOW_BURN', 'BALANCED', 'FAST_PACED', 'FRENETIC_ACTION')),
    mix_world_building INTEGER DEFAULT 50 CHECK (mix_world_building BETWEEN 0 AND 100),
    mix_psychology INTEGER DEFAULT 50 CHECK (mix_psychology BETWEEN 0 AND 100),
    mix_sensory INTEGER DEFAULT 70 CHECK (mix_sensory BETWEEN 0 AND 100),
    mix_dialogue INTEGER DEFAULT 40 CHECK (mix_dialogue BETWEEN 0 AND 100),
    mix_action INTEGER DEFAULT 30 CHECK (mix_action BETWEEN 0 AND 100),
    ending_hook_style TEXT DEFAULT 'CLIFFHANGER',
    chapter_summary TEXT DEFAULT '',
    status TEXT DEFAULT 'PLANNED' CHECK (status IN ('PLANNED', 'DRAFTING', 'COMPLETED')),
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(project_id, chapter_number)
);

CREATE INDEX IF NOT EXISTS idx_chapters_project_num
    ON chapters(project_id, chapter_number);

-- 7. Tabel Micro-Beats (Unit Eksekusi 350-400 Kata per Beat)
CREATE TABLE IF NOT EXISTS micro_beats (
    id TEXT PRIMARY KEY,
    chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    beat_number INTEGER NOT NULL,
    pov_character_id TEXT REFERENCES codex_items(id) ON DELETE SET NULL,
    location_id TEXT REFERENCES codex_items(id) ON DELETE SET NULL,
    tension_level INTEGER DEFAULT 30 CHECK (tension_level BETWEEN 0 AND 100),
    target_words INTEGER DEFAULT 400,
    beat_instruction TEXT NOT NULL,
    stopping_point TEXT NOT NULL,
    sensory_anchor TEXT DEFAULT '',
    conflict_focus TEXT DEFAULT '',
    generated_prose TEXT DEFAULT '',
    extracted_summary TEXT DEFAULT '',
    actual_words INTEGER DEFAULT 0,
    status TEXT DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'STREAMING', 'COMPLETED', 'REVISED')),
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(chapter_id, beat_number)
);

CREATE INDEX IF NOT EXISTS idx_micro_beats_chapter_num
    ON micro_beats(chapter_id, beat_number);

-- 8. Tabel Beat Revisions (Riwayat Versi Naskah & Polish per Micro-Beat)
CREATE TABLE IF NOT EXISTS beat_revisions (
    id TEXT PRIMARY KEY,
    beat_id TEXT NOT NULL REFERENCES micro_beats(id) ON DELETE CASCADE,
    revision_number INTEGER NOT NULL,
    prose_content TEXT NOT NULL,
    word_count INTEGER NOT NULL DEFAULT 0,
    revision_note TEXT DEFAULT 'Initial Generation',
    sampler_snapshot_json TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_beat_revisions_beat
    ON beat_revisions(beat_id, revision_number DESC);
"""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def count_words(text: str) -> int:
    if not text or not text.strip():
        return 0
    return len(re.findall(r"\S+", text.strip()))


_WAL_INITIALIZED_PATHS: set = set()


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Membuka koneksi SQLite dengan PRAGMA khusus Linux Mint RAM 8 GB."""
    target_path = os.path.abspath(db_path or DB_PATH)
    conn = sqlite3.connect(target_path, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if target_path not in _WAL_INITIALIZED_PATHS:
        conn.execute("PRAGMA journal_mode=WAL;")
        _WAL_INITIALIZED_PATHS.add(target_path)
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA cache_size=-8000;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@contextmanager
def db_session(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager transaksi database yang aman dengan auto-commit/rollback."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None) -> None:
    """Inisialisasi seluruh tabel, indeks, FTS5 BM25, trigger sinkronisasi, dan migrasi aman."""
    with db_session(db_path) as conn:
        conn.executescript(DDL_SCRIPT)
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(projects)").fetchall()}
        if "author_name" not in cols:
            conn.execute("ALTER TABLE projects ADD COLUMN author_name TEXT DEFAULT 'Penulis Studio'")


def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    data = dict(row)
    if "banned_phrases_json" in data and isinstance(data["banned_phrases_json"], str):
        try:
            data["banned_phrases"] = json.loads(data["banned_phrases_json"])
        except json.JSONDecodeError:
            data["banned_phrases"] = list(DEFAULT_BANNED_PHRASES)
    if "current_state_json" in data and isinstance(data["current_state_json"], str):
        try:
            data["current_state"] = json.loads(data["current_state_json"])
        except json.JSONDecodeError:
            data["current_state"] = {
                "location": "",
                "condition": "Sehat",
                "knowledge": "",
                "emotional_state": "Stabil",
            }
    return data


# ============================================================================
# CRUD PROJECTS (STORY BIBLE)
# ============================================================================

def create_project(
    title: str,
    genre: str,
    main_objective: str,
    author_name: str = "Penulis Studio",
    logline: str = "",
    pov_style: str = "Third-Person Limited",
    tense_style: str = "Lampau / Past Narrative",
    tone_style: str = "Atmosferik, Imersif, Show Dont Tell",
    style_sample: str = "",
    banned_phrases: Optional[List[str]] = None,
    total_planned_chapters: int = 24,
    default_chapter_words: int = 3200,
    rolling_global_summary: str = "",
    active_model_profile: str = "Qwen2.5-3B-Instruct-Q4_K_M",
    seed_default_phases: bool = True,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    project_id = str(uuid.uuid4())
    phrases = banned_phrases if banned_phrases is not None else DEFAULT_BANNED_PHRASES
    clean_author = (author_name or "").strip() or "Penulis Studio"
    now = _utc_now_iso()

    with db_session(db_path) as conn:
        conn.execute(
            """
            INSERT INTO projects (
                id, title, author_name, genre, logline, main_objective, pov_style, tense_style,
                tone_style, style_sample, banned_phrases_json, total_planned_chapters,
                default_chapter_words, rolling_global_summary, active_model_profile,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                title,
                clean_author,
                genre,
                logline,
                main_objective,
                pov_style,
                tense_style,
                tone_style,
                style_sample,
                json.dumps(phrases, ensure_ascii=False),
                total_planned_chapters,
                default_chapter_words,
                rolling_global_summary,
                active_model_profile,
                now,
                now,
            ),
        )

        if seed_default_phases and total_planned_chapters >= 6:
            default_phases = _build_default_phases(total_planned_chapters)
            for idx, ph in enumerate(default_phases, start=1):
                conn.execute(
                    """
                    INSERT INTO story_phases (
                        id, project_id, phase_order, phase_name, start_chapter, end_chapter,
                        default_pacing, tension_min, tension_max, building_focus,
                        phase_guardrails, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        project_id,
                        idx,
                        ph["phase_name"],
                        ph["start_chapter"],
                        ph["end_chapter"],
                        ph["default_pacing"],
                        ph["tension_min"],
                        ph["tension_max"],
                        ph["building_focus"],
                        ph["phase_guardrails"],
                        now,
                    ),
                )

    project = get_project(project_id, db_path=db_path)
    if not project:
        raise RuntimeError("Gagal mengambil project yang baru dibuat.")
    return project


def _build_default_phases(total_chapters: int) -> List[Dict[str, Any]]:
    """Membagi rentang bab secara proporsional menjadi 6 fase struktur novel sesuai Bagian 4 Blueprint."""
    c1_end = max(1, round(total_chapters * 0.14))
    c2_end = max(c1_end + 1, round(total_chapters * 0.40))
    c3_end = max(c2_end + 1, round(total_chapters * 0.52))
    c4_end = max(c3_end + 1, round(total_chapters * 0.80))
    c5_end = max(c4_end + 1, round(total_chapters * 0.93))
    c6_end = max(c5_end + 1, total_chapters)

    return [
        {
            "phase_name": "Fase I: Opening & Setup",
            "start_chapter": 1,
            "end_chapter": c1_end,
            "default_pacing": "SLOW_BURN",
            "tension_min": 15,
            "tension_max": 30,
            "building_focus": "Pengenalan atmosfer dunia, rutinitas karakter POV, luka batin awal, dan pemicu insiden pertama.",
            "phase_guardrails": "DILARANG memunculkan antagonis utama secara penuh atau menyelesaikan konflik besar. Fokus pada detail keseharian yang terganggu.",
        },
        {
            "phase_name": "Fase II: Early Development",
            "start_chapter": c1_end + 1,
            "end_chapter": c2_end,
            "default_pacing": "BALANCED",
            "tension_min": 35,
            "tension_max": 60,
            "building_focus": "Eksplorasi aturan dunia lebih luas, dinamika relasi antar-karakter, sekutu/musuh awal, dan ujian pertama.",
            "phase_guardrails": "Jaga agar rahasia inti dunia baru terbuka sebagian (maksimal 40%). Biarkan karakter membuat kesalahan taktis.",
        },
        {
            "phase_name": "Fase III: Midpoint Twist",
            "start_chapter": c2_end + 1,
            "end_chapter": c3_end,
            "default_pacing": "BALANCED",
            "tension_min": 65,
            "tension_max": 80,
            "building_focus": "Pengungkapan fakta besar yang membalikkan asumsi protagonis (Point of No Return).",
            "phase_guardrails": "Protagonis harus beralih dari reaktif menjadi proaktif. Konsekuensi kegagalan harus terasa permanen.",
        },
        {
            "phase_name": "Fase IV: Crisis & Rising Stakes",
            "start_chapter": c3_end + 1,
            "end_chapter": c4_end,
            "default_pacing": "BALANCED",
            "tension_min": 75,
            "tension_max": 90,
            "building_focus": "Runtuhnya rencana lama, pengkhianatan atau kehilangan besar (All Hope Is Lost), dan tekanan psikologis ekstrem.",
            "phase_guardrails": "DILARANG memberi jalan keluar instan (Deus Ex Machina). Setiap kemajuan kecil harus dibayar dengan pengorbanan.",
        },
        {
            "phase_name": "Fase V: Climax",
            "start_chapter": c4_end + 1,
            "end_chapter": c5_end,
            "default_pacing": "FAST_PACED",
            "tension_min": 92,
            "tension_max": 100,
            "building_focus": "Benturan puncak antara protagonis dan konflik utama dengan pertaruhan tertinggi.",
            "phase_guardrails": "DILARANG membuka subplot baru atau eksposisi sejarah panjang. Gunakan hanya aturan dunia dan alat yang sudah ditanam di bab sebelumnya.",
        },
        {
            "phase_name": "Fase VI: Resolution / Ending",
            "start_chapter": c5_end + 1,
            "end_chapter": c6_end,
            "default_pacing": "SLOW_BURN",
            "tension_min": 15,
            "tension_max": 30,
            "building_focus": "Dampak emosional pasca-klimaks, perubahan batin protagonis, dan gema dunia yang baru.",
            "phase_guardrails": "Hindari ceramah moral. Tutup cerita dengan citra sensorik konkret yang mencerminkan tema utama novel.",
        },
    ]


def list_projects(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    with db_session(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM projects ORDER BY updated_at DESC, created_at DESC"
        ).fetchall()
        return [_row_to_dict(r) for r in rows if r is not None]


def get_project(project_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with db_session(db_path) as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return _row_to_dict(row)


def update_project(
    project_id: str, updates: Dict[str, Any], db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    allowed_fields = {
        "title",
        "author_name",
        "genre",
        "logline",
        "main_objective",
        "pov_style",
        "tense_style",
        "tone_style",
        "style_sample",
        "banned_phrases_json",
        "total_planned_chapters",
        "default_chapter_words",
        "rolling_global_summary",
        "active_model_profile",
    }
    payload = dict(updates)
    if "banned_phrases" in payload:
        payload["banned_phrases_json"] = json.dumps(payload.pop("banned_phrases"), ensure_ascii=False)

    filtered = {k: v for k, v in payload.items() if k in allowed_fields and v is not None}
    if not filtered:
        return get_project(project_id, db_path=db_path)

    filtered["updated_at"] = _utc_now_iso()
    set_clause = ", ".join(f"{k} = ?" for k in filtered.keys())
    values = list(filtered.values()) + [project_id]

    with db_session(db_path) as conn:
        conn.execute(f"UPDATE projects SET {set_clause} WHERE id = ?", values)

    return get_project(project_id, db_path=db_path)


def delete_project(project_id: str, db_path: Optional[str] = None) -> bool:
    with db_session(db_path) as conn:
        conn.execute("DELETE FROM episodic_memory_fts WHERE project_id = ?", (project_id,))
        cur = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        return cur.rowcount > 0


# ============================================================================
# CRUD STORY PHASES & ACTIVE PHASE RESOLVER BY CHAPTER NUMBER
# ============================================================================

def create_story_phase(
    project_id: str,
    phase_order: int,
    phase_name: str,
    start_chapter: int,
    end_chapter: int,
    building_focus: str,
    phase_guardrails: str,
    default_pacing: str = "BALANCED",
    tension_min: int = 15,
    tension_max: int = 45,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    phase_id = str(uuid.uuid4())
    now = _utc_now_iso()
    with db_session(db_path) as conn:
        conn.execute(
            """
            INSERT INTO story_phases (
                id, project_id, phase_order, phase_name, start_chapter, end_chapter,
                default_pacing, tension_min, tension_max, building_focus,
                phase_guardrails, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                phase_id,
                project_id,
                phase_order,
                phase_name,
                start_chapter,
                end_chapter,
                default_pacing,
                tension_min,
                tension_max,
                building_focus,
                phase_guardrails,
                now,
            ),
        )
        # Re-link existing chapters in this range automatically
        conn.execute(
            """
            UPDATE chapters
            SET phase_id = ?, updated_at = ?
            WHERE project_id = ? AND chapter_number BETWEEN ? AND ?
            """,
            (phase_id, now, project_id, start_chapter, end_chapter),
        )
        row = conn.execute("SELECT * FROM story_phases WHERE id = ?", (phase_id,)).fetchone()
        return _row_to_dict(row) or {}


def list_story_phases(project_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    with db_session(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM story_phases
            WHERE project_id = ?
            ORDER BY start_chapter ASC, phase_order ASC
            """,
            (project_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows if r is not None]


def get_story_phase(phase_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with db_session(db_path) as conn:
        row = conn.execute("SELECT * FROM story_phases WHERE id = ?", (phase_id,)).fetchone()
        return _row_to_dict(row)


def get_active_phase_for_chapter(
    project_id: str, chapter_number: int, db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Mengambil Phase aktif berdasarkan nomor bab (start_chapter <= chapter_number <= end_chapter)."""
    with db_session(db_path) as conn:
        row = conn.execute(
            """
            SELECT * FROM story_phases
            WHERE project_id = ?
              AND start_chapter <= ?
              AND end_chapter >= ?
            ORDER BY phase_order ASC
            LIMIT 1
            """,
            (project_id, chapter_number, chapter_number),
        ).fetchone()
        if row:
            return _row_to_dict(row)

        # Fallback ke fase terdekat jika nomor bab melampaui rentang
        fallback = conn.execute(
            """
            SELECT * FROM story_phases
            WHERE project_id = ?
            ORDER BY ABS(start_chapter - ?) ASC
            LIMIT 1
            """,
            (project_id, chapter_number),
        ).fetchone()
        return _row_to_dict(fallback)


def update_story_phase(
    phase_id: str, updates: Dict[str, Any], db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    allowed = {
        "phase_order",
        "phase_name",
        "start_chapter",
        "end_chapter",
        "default_pacing",
        "tension_min",
        "tension_max",
        "building_focus",
        "phase_guardrails",
    }
    filtered = {k: v for k, v in updates.items() if k in allowed and v is not None}
    if not filtered:
        return get_story_phase(phase_id, db_path=db_path)

    set_clause = ", ".join(f"{k} = ?" for k in filtered.keys())
    values = list(filtered.values()) + [phase_id]

    with db_session(db_path) as conn:
        conn.execute(f"UPDATE story_phases SET {set_clause} WHERE id = ?", values)
        updated_row = conn.execute("SELECT * FROM story_phases WHERE id = ?", (phase_id,)).fetchone()
        if updated_row:
            conn.execute(
                """
                UPDATE chapters
                SET phase_id = ?
                WHERE project_id = ? AND chapter_number BETWEEN ? AND ?
                """,
                (
                    phase_id,
                    updated_row["project_id"],
                    updated_row["start_chapter"],
                    updated_row["end_chapter"],
                ),
            )
        return _row_to_dict(updated_row)


def delete_story_phase(phase_id: str, db_path: Optional[str] = None) -> bool:
    with db_session(db_path) as conn:
        cur = conn.execute("DELETE FROM story_phases WHERE id = ?", (phase_id,))
        return cur.rowcount > 0


# ============================================================================
# CRUD CODEX / LOREBOOK & FTS5 BM25 CONTEXT RETRIEVAL
# ============================================================================

def create_codex_item(
    project_id: str,
    category: str,
    name: str,
    core_description: str,
    keywords_csv: str = "",
    aliases_and_tags: str = "",
    is_pinned: int = 0,
    speech_style: str = "",
    current_state: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    codex_id = str(uuid.uuid4())
    now = _utc_now_iso()
    default_state = {
        "location": "",
        "condition": "Sehat",
        "knowledge": "",
        "emotional_state": "Stabil",
    }
    if current_state:
        default_state.update(current_state)

    if not keywords_csv.strip():
        keywords_csv = name

    with db_session(db_path) as conn:
        conn.execute(
            """
            INSERT INTO codex_items (
                id, project_id, category, name, aliases_and_tags, keywords_csv,
                is_pinned, core_description, speech_style, current_state_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                codex_id,
                project_id,
                category.upper(),
                name.strip(),
                aliases_and_tags.strip(),
                keywords_csv.strip(),
                1 if is_pinned else 0,
                core_description.strip(),
                speech_style.strip(),
                json.dumps(default_state, ensure_ascii=False),
                now,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM codex_items WHERE id = ?", (codex_id,)).fetchone()
        return _row_to_dict(row) or {}


def get_codex_item(codex_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with db_session(db_path) as conn:
        row = conn.execute("SELECT * FROM codex_items WHERE id = ?", (codex_id,)).fetchone()
        return _row_to_dict(row)


def list_codex_items(
    project_id: str,
    category: Optional[str] = None,
    pinned_only: bool = False,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    query = "SELECT * FROM codex_items WHERE project_id = ?"
    params: List[Any] = [project_id]
    if category:
        query += " AND category = ?"
        params.append(category.upper())
    if pinned_only:
        query += " AND is_pinned = 1"
    query += " ORDER BY is_pinned DESC, category ASC, name ASC"

    with db_session(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(r) for r in rows if r is not None]


def update_codex_item(
    codex_id: str, updates: Dict[str, Any], db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    allowed = {
        "category",
        "name",
        "aliases_and_tags",
        "keywords_csv",
        "is_pinned",
        "core_description",
        "speech_style",
        "current_state_json",
    }
    payload = dict(updates)
    if "current_state" in payload and isinstance(payload["current_state"], dict):
        existing = get_codex_item(codex_id, db_path=db_path)
        merged_state = (existing or {}).get("current_state", {})
        merged_state.update(payload.pop("current_state"))
        payload["current_state_json"] = json.dumps(merged_state, ensure_ascii=False)

    if "category" in payload and isinstance(payload["category"], str):
        payload["category"] = payload["category"].upper()
    if "is_pinned" in payload and payload["is_pinned"] is not None:
        payload["is_pinned"] = 1 if payload["is_pinned"] else 0

    filtered = {k: v for k, v in payload.items() if k in allowed and v is not None}
    if not filtered:
        return get_codex_item(codex_id, db_path=db_path)

    filtered["updated_at"] = _utc_now_iso()
    set_clause = ", ".join(f"{k} = ?" for k in filtered.keys())
    values = list(filtered.values()) + [codex_id]

    with db_session(db_path) as conn:
        conn.execute(f"UPDATE codex_items SET {set_clause} WHERE id = ?", values)
    return get_codex_item(codex_id, db_path=db_path)


def delete_codex_item(codex_id: str, db_path: Optional[str] = None) -> bool:
    with db_session(db_path) as conn:
        cur = conn.execute("DELETE FROM codex_items WHERE id = ?", (codex_id,))
        return cur.rowcount > 0


def _build_fts5_match_query(raw_text: str, max_terms: int = 18) -> str:
    """Membersihkan teks input menjadi query OR FTS5 yang aman dari syntax error."""
    if not raw_text:
        return ""
    # Ambil kata alfanumerik minimal 3 karakter
    tokens = re.findall(r"[A-Za-z0-9_À-ÿ]{3,}", raw_text.lower())
    stopwords = {
        "yang", "dan", "di", "ke", "dari", "ini", "itu", "dengan", "untuk",
        "pada", "adalah", "dalam", "tidak", "akan", "atau", "juga", "სა",
        "sudah", "telah", "saat", "ketika", "karena", "namun", "tetapi",
        "mereka", "dia", "ia", "kami", "kita", "anda", "saya", "aku",
        "sebuah", "seorang", "para", "tersebut", "bisa", "dapat", "harus",
    }
    seen = set()
    clean_tokens: List[str] = []
    for tok in tokens:
        if tok not in stopwords and tok not in seen:
            seen.add(tok)
            clean_tokens.append(f'"{tok}"*')
            if len(clean_tokens) >= max_terms:
                break
    return " OR ".join(clean_tokens)


def search_codex_fts_bm25(
    project_id: str,
    query_text: str,
    limit: int = 6,
    exclude_ids: Optional[List[str]] = None,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Pencarian otomatis entitas Codex yang relevan menggunakan algoritma BM25 SQLite FTS5.
    Menggunakan bobot kolom: name (10.0), aliases_and_tags (8.0), keywords_csv (8.0),
    core_description (2.0), speech_style (1.0), current_state_text (1.5).
    """
    fts_query = _build_fts5_match_query(query_text)
    if not fts_query:
        return []

    excluded = set(exclude_ids or [])
    with db_session(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                c.*,
                bm25(codex_fts, 0.0, 0.0, 0.0, 10.0, 8.0, 8.0, 2.0, 1.0, 1.5) AS bm25_score
            FROM codex_fts
            JOIN codex_items c ON c.id = codex_fts.codex_id
            WHERE codex_fts MATCH ?
              AND c.project_id = ?
            ORDER BY bm25_score ASC
            LIMIT ?
            """,
            (fts_query, project_id, limit + len(excluded)),
        ).fetchall()

        results: List[Dict[str, Any]] = []
        for r in rows:
            item = _row_to_dict(r)
            if item and item["id"] not in excluded:
                results.append(item)
                if len(results) >= limit:
                    break
        return results


def add_episodic_memory(
    project_id: str,
    chapter_number: int,
    beat_id: str,
    keywords: str,
    event_summary: str,
    db_path: Optional[str] = None,
) -> None:
    if not event_summary.strip():
        return
    with db_session(db_path) as conn:
        conn.execute(
            "DELETE FROM episodic_memory_fts WHERE project_id = ? AND beat_id = ?",
            (project_id, beat_id),
        )
        conn.execute(
            """
            INSERT INTO episodic_memory_fts (
                project_id, chapter_number, beat_id, keywords, event_summary
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, chapter_number, beat_id, keywords.strip(), event_summary.strip()),
        )


def search_episodic_memory_bm25(
    project_id: str,
    query_text: str,
    before_chapter: Optional[int] = None,
    limit: int = 5,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Mencari memori kejadian masa lalu lintas bab menggunakan FTS5 BM25."""
    fts_query = _build_fts5_match_query(query_text)
    if not fts_query:
        return []

    sql = """
        SELECT
            project_id,
            CAST(chapter_number AS INTEGER) AS chapter_number,
            beat_id,
            keywords,
            event_summary,
            bm25(episodic_memory_fts, 0.0, 0.0, 0.0, 6.0, 3.0) AS bm25_score
        FROM episodic_memory_fts
        WHERE episodic_memory_fts MATCH ?
          AND project_id = ?
    """
    params: List[Any] = [fts_query, project_id]
    if before_chapter is not None:
        sql += " AND CAST(chapter_number AS INTEGER) <= ?"
        params.append(before_chapter)
    sql += " ORDER BY bm25_score ASC LIMIT ?"
    params.append(limit)

    with db_session(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


# ============================================================================
# CRUD CHAPTERS & MICRO-BEATS & BEAT REVISIONS
# ============================================================================

def create_chapter(
    project_id: str,
    chapter_number: int,
    title: str,
    chapter_goal: str,
    target_word_count: int = 3200,
    pacing_mode: Optional[str] = None,
    phase_id: Optional[str] = None,
    mix_world_building: int = 50,
    mix_psychology: int = 50,
    mix_sensory: int = 70,
    mix_dialogue: int = 40,
    mix_action: int = 30,
    ending_hook_style: str = "CLIFFHANGER",
    chapter_summary: str = "",
    status: str = "PLANNED",
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    chapter_id = str(uuid.uuid4())
    now = _utc_now_iso()

    resolved_phase = get_active_phase_for_chapter(project_id, chapter_number, db_path=db_path)
    effective_phase_id = phase_id or (resolved_phase["id"] if resolved_phase else None)
    effective_pacing = (
        pacing_mode
        or (resolved_phase["default_pacing"] if resolved_phase else "BALANCED")
    ).upper()

    with db_session(db_path) as conn:
        conn.execute(
            """
            INSERT INTO chapters (
                id, project_id, phase_id, chapter_number, title, chapter_goal,
                target_word_count, current_word_count, pacing_mode,
                mix_world_building, mix_psychology, mix_sensory, mix_dialogue, mix_action,
                ending_hook_style, chapter_summary, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chapter_id,
                project_id,
                effective_phase_id,
                chapter_number,
                title.strip(),
                chapter_goal.strip(),
                target_word_count,
                effective_pacing,
                mix_world_building,
                mix_psychology,
                mix_sensory,
                mix_dialogue,
                mix_action,
                ending_hook_style,
                chapter_summary,
                status,
                now,
                now,
            ),
        )
    chapter = get_chapter(chapter_id, db_path=db_path)
    if not chapter:
        raise RuntimeError("Gagal mengambil bab yang baru dibuat.")
    return chapter


def get_chapter(chapter_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with db_session(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                c.*,
                p.phase_name,
                p.start_chapter AS phase_start_chapter,
                p.end_chapter AS phase_end_chapter,
                p.tension_min,
                p.tension_max,
                p.building_focus,
                p.phase_guardrails
            FROM chapters c
            LEFT JOIN story_phases p ON c.phase_id = p.id
            WHERE c.id = ?
            """,
            (chapter_id,),
        ).fetchone()
        if not row:
            return None
        chapter_dict = _row_to_dict(row) or {}
        if not chapter_dict.get("phase_id"):
            active_phase = get_active_phase_for_chapter(
                chapter_dict["project_id"], chapter_dict["chapter_number"], db_path=db_path
            )
            if active_phase:
                chapter_dict["phase_id"] = active_phase["id"]
                chapter_dict["phase_name"] = active_phase["phase_name"]
                chapter_dict["phase_start_chapter"] = active_phase["start_chapter"]
                chapter_dict["phase_end_chapter"] = active_phase["end_chapter"]
                chapter_dict["tension_min"] = active_phase["tension_min"]
                chapter_dict["tension_max"] = active_phase["tension_max"]
                chapter_dict["building_focus"] = active_phase["building_focus"]
                chapter_dict["phase_guardrails"] = active_phase["phase_guardrails"]
        return chapter_dict


def list_chapters(project_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    with db_session(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                c.*,
                p.phase_name,
                p.tension_min,
                p.tension_max
            FROM chapters c
            LEFT JOIN story_phases p ON c.phase_id = p.id
            WHERE c.project_id = ?
            ORDER BY c.chapter_number ASC
            """,
            (project_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows if r is not None]


def update_chapter(
    chapter_id: str, updates: Dict[str, Any], db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    allowed = {
        "phase_id",
        "chapter_number",
        "title",
        "chapter_goal",
        "target_word_count",
        "current_word_count",
        "pacing_mode",
        "mix_world_building",
        "mix_psychology",
        "mix_sensory",
        "mix_dialogue",
        "mix_action",
        "ending_hook_style",
        "chapter_summary",
        "status",
    }
    filtered = {k: v for k, v in updates.items() if k in allowed and v is not None}
    if not filtered:
        return get_chapter(chapter_id, db_path=db_path)

    filtered["updated_at"] = _utc_now_iso()
    set_clause = ", ".join(f"{k} = ?" for k in filtered.keys())
    values = list(filtered.values()) + [chapter_id]

    with db_session(db_path) as conn:
        conn.execute(f"UPDATE chapters SET {set_clause} WHERE id = ?", values)
    return get_chapter(chapter_id, db_path=db_path)


def delete_chapter(chapter_id: str, db_path: Optional[str] = None) -> bool:
    with db_session(db_path) as conn:
        cur = conn.execute("DELETE FROM chapters WHERE id = ?", (chapter_id,))
        return cur.rowcount > 0


def recalculate_chapter_word_count(chapter_id: str, db_path: Optional[str] = None) -> int:
    with db_session(db_path) as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(actual_words), 0) AS total_words FROM micro_beats WHERE chapter_id = ?",
            (chapter_id,),
        ).fetchone()
        total_words = int(row["total_words"]) if row else 0
        conn.execute(
            "UPDATE chapters SET current_word_count = ?, updated_at = ? WHERE id = ?",
            (total_words, _utc_now_iso(), chapter_id),
        )
        return total_words


def replace_chapter_micro_beats(
    chapter_id: str,
    beats_payload: List[Dict[str, Any]],
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Menyimpan daftar Micro-Beats baru hasil generasi Plot Architect untuk satu bab."""
    now = _utc_now_iso()
    with db_session(db_path) as conn:
        conn.execute("DELETE FROM micro_beats WHERE chapter_id = ?", (chapter_id,))
        for idx, b in enumerate(beats_payload, start=1):
            beat_id = b.get("id") or str(uuid.uuid4())
            beat_num = int(b.get("beat_number") or idx)
            conn.execute(
                """
                INSERT INTO micro_beats (
                    id, chapter_id, beat_number, pov_character_id, location_id,
                    tension_level, target_words, beat_instruction, stopping_point,
                    sensory_anchor, conflict_focus, generated_prose, extracted_summary,
                    actual_words, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    beat_id,
                    chapter_id,
                    beat_num,
                    b.get("pov_character_id"),
                    b.get("location_id"),
                    int(b.get("tension_level", 30)),
                    int(b.get("target_words", 400)),
                    str(b.get("beat_instruction", "")).strip(),
                    str(b.get("stopping_point", "")).strip(),
                    str(b.get("sensory_anchor", "")).strip(),
                    str(b.get("conflict_focus", "")).strip(),
                    str(b.get("generated_prose", "")),
                    str(b.get("extracted_summary", "")),
                    int(b.get("actual_words", 0)),
                    str(b.get("status", "PENDING")),
                    now,
                    now,
                ),
            )
    recalculate_chapter_word_count(chapter_id, db_path=db_path)
    return list_micro_beats(chapter_id, db_path=db_path)


def list_micro_beats(chapter_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    with db_session(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                mb.*,
                pov.name AS pov_character_name,
                loc.name AS location_name
            FROM micro_beats mb
            LEFT JOIN codex_items pov ON mb.pov_character_id = pov.id
            LEFT JOIN codex_items loc ON mb.location_id = loc.id
            WHERE mb.chapter_id = ?
            ORDER BY mb.beat_number ASC
            """,
            (chapter_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows if r is not None]


def add_single_micro_beat(
    chapter_id: str,
    beat_instruction: str = "Tulis kelanjutan adegan berikutnya secara konkret.",
    stopping_point: str = "Hentikan tepat pada dialog atau tindakan mikro terakhir.",
    target_words: int = 400,
    tension_level: int = 45,
    pov_character_id: Optional[str] = None,
    location_id: Optional[str] = None,
    sensory_anchor: str = "",
    conflict_focus: str = "",
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    beat_id = str(uuid.uuid4())
    now = _utc_now_iso()
    with db_session(db_path) as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(beat_number), 0) AS max_num FROM micro_beats WHERE chapter_id = ?",
            (chapter_id,),
        ).fetchone()
        next_num = (int(row["max_num"]) if row else 0) + 1
        conn.execute(
            """
            INSERT INTO micro_beats (
                id, chapter_id, beat_number, pov_character_id, location_id,
                tension_level, target_words, beat_instruction, stopping_point,
                sensory_anchor, conflict_focus, generated_prose, extracted_summary,
                actual_words, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', 0, 'PENDING', ?, ?)
            """,
            (
                beat_id,
                chapter_id,
                next_num,
                pov_character_id,
                location_id,
                max(5, min(100, int(tension_level))),
                max(100, int(target_words)),
                beat_instruction.strip() or f"Adegan lanjutan Beat #{next_num}",
                stopping_point.strip() or "Berhenti pada dialog/aksi penutup adegan.",
                sensory_anchor.strip(),
                conflict_focus.strip(),
                now,
                now,
            ),
        )
    return get_micro_beat(beat_id, db_path=db_path) or {}


def delete_micro_beat(beat_id: str, db_path: Optional[str] = None) -> bool:
    with db_session(db_path) as conn:
        row = conn.execute(
            "SELECT chapter_id, beat_number FROM micro_beats WHERE id = ?",
            (beat_id,),
        ).fetchone()
        if not row:
            return False
        chapter_id = row["chapter_id"]
        deleted_num = int(row["beat_number"])
        conn.execute("DELETE FROM micro_beats WHERE id = ?", (beat_id,))
        conn.execute(
            "DELETE FROM episodic_memory_fts WHERE beat_id = ?",
            (beat_id,),
        )
        conn.execute(
            """
            UPDATE micro_beats
            SET beat_number = beat_number - 1
            WHERE chapter_id = ? AND beat_number > ?
            """,
            (chapter_id, deleted_num),
        )
    recalculate_chapter_word_count(chapter_id, db_path=db_path)
    return True


def move_micro_beat(
    beat_id: str, direction: str, db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Menukar posisi Micro-Beat ke atas ('up') atau ke bawah ('down') secara atomik."""
    dir_norm = (direction or "").strip().lower()
    if dir_norm not in ("up", "down"):
        raise ValueError("Arah pemindahan harus 'up' atau 'down'.")

    with db_session(db_path) as conn:
        current = conn.execute(
            "SELECT id, chapter_id, beat_number FROM micro_beats WHERE id = ?",
            (beat_id,),
        ).fetchone()
        if not current:
            raise ValueError("Micro-Beat tidak ditemukan.")

        chapter_id = str(current["chapter_id"])
        cur_num = int(current["beat_number"])
        target_num = cur_num - 1 if dir_norm == "up" else cur_num + 1

        neighbor = conn.execute(
            "SELECT id, beat_number FROM micro_beats WHERE chapter_id = ? AND beat_number = ?",
            (chapter_id, target_num),
        ).fetchone()
        if not neighbor:
            # Sudah di posisi paling awal atau paling akhir
            pass
        else:
            now = _utc_now_iso()
            conn.execute(
                "UPDATE micro_beats SET beat_number = -999999 WHERE id = ?",
                (current["id"],),
            )
            conn.execute(
                "UPDATE micro_beats SET beat_number = ?, updated_at = ? WHERE id = ?",
                (cur_num, now, neighbor["id"]),
            )
            conn.execute(
                "UPDATE micro_beats SET beat_number = ?, updated_at = ? WHERE id = ?",
                (target_num, now, current["id"]),
            )

    return list_micro_beats(chapter_id, db_path=db_path)


def get_micro_beat(beat_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with db_session(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                mb.*,
                pov.name AS pov_character_name,
                loc.name AS location_name
            FROM micro_beats mb
            LEFT JOIN codex_items pov ON mb.pov_character_id = pov.id
            LEFT JOIN codex_items loc ON mb.location_id = loc.id
            WHERE mb.id = ?
            """,
            (beat_id,),
        ).fetchone()
        return _row_to_dict(row)


def save_beat_prose_and_revision(
    beat_id: str,
    prose_content: str,
    revision_note: str = "Streamed Generation",
    sampler_snapshot: Optional[Dict[str, Any]] = None,
    status: str = "COMPLETED",
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Menyimpan hasil prosa Micro-Beat sekaligus mencatat versi di beat_revisions."""
    now = _utc_now_iso()
    wc = count_words(prose_content)
    snapshot_json = json.dumps(sampler_snapshot or {}, ensure_ascii=False)

    with db_session(db_path) as conn:
        beat_row = conn.execute("SELECT * FROM micro_beats WHERE id = ?", (beat_id,)).fetchone()
        if not beat_row:
            raise ValueError(f"Micro-Beat {beat_id} tidak ditemukan.")

        rev_row = conn.execute(
            "SELECT COALESCE(MAX(revision_number), 0) AS max_rev FROM beat_revisions WHERE beat_id = ?",
            (beat_id,),
        ).fetchone()
        next_rev = (int(rev_row["max_rev"]) if rev_row else 0) + 1

        conn.execute(
            """
            UPDATE micro_beats
            SET generated_prose = ?, actual_words = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (prose_content, wc, status, now, beat_id),
        )

        conn.execute(
            """
            INSERT INTO beat_revisions (
                id, beat_id, revision_number, prose_content, word_count,
                revision_note, sampler_snapshot_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                beat_id,
                next_rev,
                prose_content,
                wc,
                revision_note,
                snapshot_json,
                now,
            ),
        )
        chapter_id = beat_row["chapter_id"]

    recalculate_chapter_word_count(chapter_id, db_path=db_path)
    return get_micro_beat(beat_id, db_path=db_path) or {}


def update_micro_beat(
    beat_id: str, updates: Dict[str, Any], db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    allowed = {
        "pov_character_id",
        "location_id",
        "tension_level",
        "target_words",
        "beat_instruction",
        "stopping_point",
        "sensory_anchor",
        "conflict_focus",
        "generated_prose",
        "extracted_summary",
        "actual_words",
        "status",
    }
    filtered = {k: v for k, v in updates.items() if k in allowed and v is not None}
    if not filtered:
        return get_micro_beat(beat_id, db_path=db_path)

    if "generated_prose" in filtered and "actual_words" not in filtered:
        filtered["actual_words"] = count_words(str(filtered["generated_prose"]))

    filtered["updated_at"] = _utc_now_iso()
    set_clause = ", ".join(f"{k} = ?" for k in filtered.keys())
    values = list(filtered.values()) + [beat_id]

    with db_session(db_path) as conn:
        conn.execute(f"UPDATE micro_beats SET {set_clause} WHERE id = ?", values)
        row = conn.execute("SELECT chapter_id FROM micro_beats WHERE id = ?", (beat_id,)).fetchone()
        chapter_id = row["chapter_id"] if row else None

    if chapter_id:
        recalculate_chapter_word_count(chapter_id, db_path=db_path)
    return get_micro_beat(beat_id, db_path=db_path)


def list_beat_revisions(beat_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    with db_session(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM beat_revisions
            WHERE beat_id = ?
            ORDER BY revision_number DESC
            """,
            (beat_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_story_bible_bundle(
    project_id: str,
    chapter_number: Optional[int] = None,
    query_context: str = "",
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Helper komprehensif untuk mengambil:
    1. Project / Story Bible utama
    2. Story Phase aktif berdasarkan nomor bab
    3. Pinned Codex Items (selalu masuk ke Static Prefix di Slot 0)
    4. Dynamic Codex Items & Episodic Memories hasil pencarian FTS5 BM25
    """
    project = get_project(project_id, db_path=db_path)
    if not project:
        raise ValueError(f"Project {project_id} tidak ditemukan.")

    active_phase = None
    if chapter_number is not None:
        active_phase = get_active_phase_for_chapter(project_id, chapter_number, db_path=db_path)

    pinned_codex = list_codex_items(project_id, pinned_only=True, db_path=db_path)
    pinned_ids = [item["id"] for item in pinned_codex]

    dynamic_codex: List[Dict[str, Any]] = []
    episodic_memories: List[Dict[str, Any]] = []
    if query_context.strip():
        dynamic_codex = search_codex_fts_bm25(
            project_id=project_id,
            query_text=query_context,
            limit=6,
            exclude_ids=pinned_ids,
            db_path=db_path,
        )
        episodic_memories = search_episodic_memory_bm25(
            project_id=project_id,
            query_text=query_context,
            before_chapter=chapter_number,
            limit=5,
            db_path=db_path,
        )

    return {
        "project": project,
        "active_phase": active_phase,
        "pinned_codex": pinned_codex,
        "dynamic_codex": dynamic_codex,
        "episodic_memories": episodic_memories,
    }


def export_project_backup_dict(project_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Menghasilkan snapshot lengkap proyek novel (Story Bible, Fase, Codex, Bab, Beats, & Revisi)."""
    project = get_project(project_id, db_path=db_path)
    if not project:
        raise ValueError(f"Project {project_id} tidak ditemukan.")

    phases = list_story_phases(project_id, db_path=db_path)
    codex_items = list_codex_items(project_id, db_path=db_path)
    chapters = list_chapters(project_id, db_path=db_path)
    for ch in chapters:
        beats = list_micro_beats(ch["id"], db_path=db_path)
        for b in beats:
            b["revisions"] = list_beat_revisions(b["id"], db_path=db_path)
        ch["beats"] = beats

    return {
        "backup_version": "1.0",
        "exported_at": _utc_now_iso(),
        "project": project,
        "story_phases": phases,
        "codex_items": codex_items,
        "chapters": chapters,
    }


def import_project_backup_dict(
    backup: Dict[str, Any], db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Memulihkan file backup JSON menjadi proyek novel baru yang utuh
    (memetakan ulang semua UUID agar aman dari bentrok ID maupun duplikasi).
    """
    if not isinstance(backup, dict) or not isinstance(backup.get("project"), dict):
        raise ValueError("Format file backup JSON tidak valid: objek 'project' tidak ditemukan.")

    src_proj = backup["project"]
    title = str(src_proj.get("title") or "").strip()
    main_objective = str(src_proj.get("main_objective") or "").strip()
    if not title or not main_objective:
        raise ValueError("Backup JSON tidak lengkap: judul atau tujuan utama proyek kosong.")

    new_project_id = str(uuid.uuid4())
    now = _utc_now_iso()
    raw_phrases = src_proj.get("banned_phrases")
    if isinstance(raw_phrases, list):
        phrases_json = json.dumps([str(p) for p in raw_phrases], ensure_ascii=False)
    elif isinstance(src_proj.get("banned_phrases_json"), str):
        phrases_json = src_proj["banned_phrases_json"]
    else:
        phrases_json = json.dumps(DEFAULT_BANNED_PHRASES, ensure_ascii=False)

    phase_map: Dict[str, str] = {}
    codex_map: Dict[str, str] = {}
    chapter_ids_created: List[str] = []

    with db_session(db_path) as conn:
        existing_titles = {
            str(r["title"]).strip().lower()
            for r in conn.execute("SELECT title FROM projects").fetchall()
        }
        final_title = title
        if final_title.lower() in existing_titles:
            final_title = f"{title} (Pulihan)"

        conn.execute(
            """
            INSERT INTO projects (
                id, title, author_name, genre, logline, main_objective, pov_style, tense_style,
                tone_style, style_sample, banned_phrases_json, total_planned_chapters,
                default_chapter_words, rolling_global_summary, active_model_profile,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_project_id,
                final_title,
                str(src_proj.get("author_name") or "Penulis Studio"),
                str(src_proj.get("genre") or "Fiksi Umum"),
                str(src_proj.get("logline") or ""),
                main_objective,
                str(src_proj.get("pov_style") or "Third-Person Limited"),
                str(src_proj.get("tense_style") or "Lampau / Past Narrative"),
                str(src_proj.get("tone_style") or "Atmosferik, Imersif, Show Dont Tell"),
                str(src_proj.get("style_sample") or ""),
                phrases_json,
                int(src_proj.get("total_planned_chapters") or 24),
                int(src_proj.get("default_chapter_words") or 3200),
                str(src_proj.get("rolling_global_summary") or ""),
                str(src_proj.get("active_model_profile") or "Qwen2.5-3B-Instruct-Q4_K_M"),
                now,
                now,
            ),
        )

        # 1. Story Phases
        for idx, ph in enumerate(backup.get("story_phases") or [], start=1):
            if not isinstance(ph, dict):
                continue
            new_phase_id = str(uuid.uuid4())
            if ph.get("id"):
                phase_map[str(ph["id"])] = new_phase_id
            start_ch = int(ph.get("start_chapter") or 1)
            end_ch = max(start_ch, int(ph.get("end_chapter") or start_ch))
            t_min = max(0, min(100, int(ph.get("tension_min") or 15)))
            t_max = max(t_min, min(100, int(ph.get("tension_max") or 45)))
            pacing = str(ph.get("default_pacing") or "BALANCED").upper()
            if pacing not in ("SLOW_BURN", "BALANCED", "FAST_PACED", "FRENETIC_ACTION"):
                pacing = "BALANCED"

            conn.execute(
                """
                INSERT INTO story_phases (
                    id, project_id, phase_order, phase_name, start_chapter, end_chapter,
                    default_pacing, tension_min, tension_max, building_focus, phase_guardrails, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_phase_id,
                    new_project_id,
                    int(ph.get("phase_order") or idx),
                    str(ph.get("phase_name") or f"Fase {idx}"),
                    start_ch,
                    end_ch,
                    pacing,
                    t_min,
                    t_max,
                    str(ph.get("building_focus") or ""),
                    str(ph.get("phase_guardrails") or ""),
                    now,
                ),
            )

        # 2. Codex Items (trigger FTS5 otomatis mengisi codex_fts)
        valid_categories = {"CHARACTER", "LOCATION", "WORLD_RULE", "ITEM", "LORE"}
        for item in backup.get("codex_items") or []:
            if not isinstance(item, dict):
                continue
            new_codex_id = str(uuid.uuid4())
            if item.get("id"):
                codex_map[str(item["id"])] = new_codex_id
            cat = str(item.get("category") or "LORE").upper()
            if cat not in valid_categories:
                cat = "LORE"
            state_obj = item.get("current_state")
            if isinstance(state_obj, dict):
                state_json = json.dumps(state_obj, ensure_ascii=False)
            elif isinstance(item.get("current_state_json"), str):
                state_json = item["current_state_json"]
            else:
                state_json = json.dumps(
                    {"location": "", "condition": "Sehat", "knowledge": "", "emotional_state": "Stabil"},
                    ensure_ascii=False,
                )

            conn.execute(
                """
                INSERT INTO codex_items (
                    id, project_id, category, name, aliases_and_tags, keywords_csv,
                    is_pinned, core_description, speech_style, current_state_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_codex_id,
                    new_project_id,
                    cat,
                    str(item.get("name") or "Entitas Tanpa Nama"),
                    str(item.get("aliases_and_tags") or ""),
                    str(item.get("keywords_csv") or ""),
                    1 if item.get("is_pinned") else 0,
                    str(item.get("core_description") or ""),
                    str(item.get("speech_style") or ""),
                    state_json,
                    now,
                    now,
                ),
            )

        # 3. Chapters, Micro-Beats, Revisions, & Episodic Memory FTS5
        valid_ch_status = {"PLANNED", "DRAFTING", "COMPLETED"}
        valid_beat_status = {"PENDING", "STREAMING", "COMPLETED", "REVISED"}
        for ch_idx, ch in enumerate(backup.get("chapters") or [], start=1):
            if not isinstance(ch, dict):
                continue
            new_ch_id = str(uuid.uuid4())
            chapter_ids_created.append(new_ch_id)
            mapped_phase_id = phase_map.get(str(ch.get("phase_id") or ""))
            ch_num = int(ch.get("chapter_number") or ch_idx)
            pacing = str(ch.get("pacing_mode") or "BALANCED").upper()
            if pacing not in ("SLOW_BURN", "BALANCED", "FAST_PACED", "FRENETIC_ACTION"):
                pacing = "BALANCED"
            ch_status = str(ch.get("status") or "PLANNED").upper()
            if ch_status not in valid_ch_status:
                ch_status = "PLANNED"

            conn.execute(
                """
                INSERT INTO chapters (
                    id, project_id, phase_id, chapter_number, title, chapter_goal,
                    target_word_count, current_word_count, pacing_mode,
                    mix_world_building, mix_psychology, mix_sensory, mix_dialogue, mix_action,
                    ending_hook_style, chapter_summary, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_ch_id,
                    new_project_id,
                    mapped_phase_id,
                    ch_num,
                    str(ch.get("title") or f"Bab {ch_num}"),
                    str(ch.get("chapter_goal") or ""),
                    int(ch.get("target_word_count") or 3200),
                    int(ch.get("current_word_count") or 0),
                    pacing,
                    max(0, min(100, int(ch.get("mix_world_building") or 50))),
                    max(0, min(100, int(ch.get("mix_psychology") or 50))),
                    max(0, min(100, int(ch.get("mix_sensory") or 70))),
                    max(0, min(100, int(ch.get("mix_dialogue") or 40))),
                    max(0, min(100, int(ch.get("mix_action") or 30))),
                    str(ch.get("ending_hook_style") or "CLIFFHANGER"),
                    str(ch.get("chapter_summary") or ""),
                    ch_status,
                    now,
                    now,
                ),
            )

            for b_idx, b in enumerate(ch.get("beats") or [], start=1):
                if not isinstance(b, dict):
                    continue
                new_beat_id = str(uuid.uuid4())
                prose = str(b.get("generated_prose") or "")
                b_status = str(b.get("status") or "PENDING").upper()
                if b_status not in valid_beat_status:
                    b_status = "COMPLETED" if prose.strip() else "PENDING"
                summary_text = str(b.get("extracted_summary") or "")

                conn.execute(
                    """
                    INSERT INTO micro_beats (
                        id, chapter_id, beat_number, pov_character_id, location_id,
                        tension_level, target_words, beat_instruction, stopping_point,
                        sensory_anchor, conflict_focus, generated_prose, extracted_summary,
                        actual_words, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_beat_id,
                        new_ch_id,
                        int(b.get("beat_number") or b_idx),
                        codex_map.get(str(b.get("pov_character_id") or "")),
                        codex_map.get(str(b.get("location_id") or "")),
                        max(0, min(100, int(b.get("tension_level") or 35))),
                        int(b.get("target_words") or 400),
                        str(b.get("beat_instruction") or f"Adegan Beat #{b_idx}"),
                        str(b.get("stopping_point") or "Berhenti pada tindakan/dialog penutup."),
                        str(b.get("sensory_anchor") or ""),
                        str(b.get("conflict_focus") or ""),
                        prose,
                        summary_text,
                        count_words(prose),
                        b_status,
                        now,
                        now,
                    ),
                )

                if summary_text.strip():
                    conn.execute(
                        """
                        INSERT INTO episodic_memory_fts(project_id, chapter_number, beat_id, keywords, event_summary)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            new_project_id,
                            str(ch_num),
                            new_beat_id,
                            f"Bab {ch_num} {ch.get('title', '')}",
                            summary_text.strip(),
                        ),
                    )

                for r_idx, rev in enumerate(b.get("revisions") or [], start=1):
                    if not isinstance(rev, dict):
                        continue
                    rev_prose = str(rev.get("prose_content") or "")
                    conn.execute(
                        """
                        INSERT INTO beat_revisions (
                            id, beat_id, revision_number, prose_content, word_count,
                            revision_note, sampler_snapshot_json, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(uuid.uuid4()),
                            new_beat_id,
                            int(rev.get("revision_number") or r_idx),
                            rev_prose,
                            count_words(rev_prose),
                            str(rev.get("revision_note") or "Restored Revision"),
                            str(rev.get("sampler_snapshot_json") or "{}"),
                            str(rev.get("created_at") or now),
                        ),
                    )

    for ch_id in chapter_ids_created:
        recalculate_chapter_word_count(ch_id, db_path=db_path)

    restored = get_project(new_project_id, db_path=db_path)
    if not restored:
        raise RuntimeError("Gagal mengambil proyek hasil pemulihan backup.")
    return restored
