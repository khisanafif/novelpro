from datetime import datetime, timezone
import html
import io
import os
import re
import tempfile
import uuid
import zipfile
from typing import Any, Dict, List, Optional, Tuple

try:
    from ebooklib import epub  # type: ignore
except ImportError:
    epub = None  # type: ignore

try:
    from fastapi import APIRouter, HTTPException, Query
    from fastapi.responses import Response
except ImportError:
    APIRouter = None  # type: ignore
    HTTPException = Exception  # type: ignore
    Query = lambda default=None, **kwargs: default  # type: ignore
    Response = None  # type: ignore

from database import (
    count_words,
    get_project,
    list_chapters,
    list_codex_items,
    list_micro_beats,
    list_story_phases,
)


# ============================================================================
# GAYA TIPOGRAFI BUKU CETAK STANDAR PENERBIT (EPUB CSS)
# ============================================================================

PUBLISHER_EPUB_CSS = """
@namespace epub "http://www.idpf.org/2007/ops";

body {
    font-family: "Literata", "Georgia", "Palatino Linotype", "Book Antiqua", serif;
    font-size: 1.05em;
    line-height: 1.78;
    color: #18181B;
    margin: 5% 6%;
    text-align: justify;
    hyphens: auto;
    -webkit-hyphens: auto;
}

h1, h2, h3 {
    font-family: "Literata", "Georgia", serif;
    font-weight: 700;
    color: #111315;
    text-align: center;
    line-height: 1.3;
    page-break-after: avoid;
}

.title-page {
    text-align: center;
    margin-top: 18%;
    page-break-after: always;
}

.book-title {
    font-size: 2.2em;
    letter-spacing: 0.04em;
    margin-bottom: 0.3em;
    text-transform: uppercase;
}

.book-genre {
    font-size: 0.95em;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #57534E;
    margin-bottom: 2.2em;
}

.book-logline {
    font-style: italic;
    font-size: 1.02em;
    color: #44403C;
    margin: 2em 8%;
    line-height: 1.65;
}

.book-author {
    font-size: 1.2em;
    font-weight: 600;
    margin-top: 3.5em;
    letter-spacing: 0.06em;
}

.book-meta {
    font-size: 0.82em;
    color: #78716C;
    margin-top: 4em;
}

.chapter-header {
    margin-top: 12%;
    margin-bottom: 2.4em;
    text-align: center;
}

.chapter-number {
    font-size: 0.85em;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #78716C;
    margin-bottom: 0.4em;
}

.chapter-title {
    font-size: 1.55em;
    margin-top: 0.2em;
    margin-bottom: 0.4em;
}

.chapter-phase {
    font-size: 0.78em;
    font-style: italic;
    color: #78716C;
}

p {
    margin-top: 0;
    margin-bottom: 0.45em;
    text-indent: 1.6em;
}

p.first-paragraph {
    text-indent: 0;
}

p.first-paragraph::first-letter {
    font-size: 2.4em;
    font-weight: 700;
    float: left;
    line-height: 0.88;
    padding-right: 0.12em;
    color: #1C1917;
}

hr.scene-break {
    border: none;
    text-align: center;
    margin: 1.8em 0;
    page-break-inside: avoid;
}

hr.scene-break::after {
    content: "* * *";
    letter-spacing: 0.35em;
    color: #78716C;
    font-size: 0.95em;
}

.toc-list {
    list-style-type: none;
    padding-left: 0;
    margin-top: 2em;
}

.toc-list li {
    margin-bottom: 0.75em;
    text-align: left;
}

.toc-list a {
    text-decoration: none;
    color: #1C1917;
}
"""


# ============================================================================
# MANUSCRIPT COMPILER (EPUB & MARKDOWN ENGINE)
# ============================================================================

class ManuscriptCompiler:
    """
    Mesin Kompilasi Naskah Novel:
    Menggabungkan seluruh Bab (Chapters) dan Adegan (Micro-Beats) yang telah ditulis
    atau disetujui dari SQLite menjadi:
    1. File `.epub` standar penerbit (menggunakan EbookLib dengan fallback standar EPUB3).
    2. File `.md` (Markdown) terstruktur rapi dengan Daftar Isi, Metrik Kata, & Lampiran Story Bible.
    """

    APPROVED_BEAT_STATUSES = {"COMPLETED", "REVISED", "APPROVED"}

    @staticmethod
    def slugify_filename(text: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9_-]+", "_", (text or "novel").strip())
        clean = re.sub(r"_+", "_", clean).strip("_").lower()
        return clean or "novel_manuscript"

    @staticmethod
    def _prose_to_paragraphs(prose: str) -> List[str]:
        if not prose or not prose.strip():
            return []
        blocks = re.split(r"\n\s*\n", prose.strip())
        paragraphs: List[str] = []
        for blk in blocks:
            lines = [ln.strip() for ln in blk.splitlines() if ln.strip()]
            if lines:
                paragraphs.append(" ".join(lines))
        return paragraphs

    @classmethod
    def _prose_to_xhtml_paragraphs(cls, prose: str, is_first_beat_in_chapter: bool = False) -> str:
        paragraphs = cls._prose_to_paragraphs(prose)
        if not paragraphs:
            return ""
        html_parts: List[str] = []
        for idx, para in enumerate(paragraphs):
            escaped = html.escape(para)
            # Konversi penekanan miring sederhana (*kata* atau _kata_) ke <em>
            escaped = re.sub(r"\*([^*\n]+)\*", r"<em>\1</em>", escaped)
            css_class = ' class="first-paragraph"' if (is_first_beat_in_chapter and idx == 0) else ""
            html_parts.append(f"<p{css_class}>{escaped}</p>")
        return "\n".join(html_parts)

    @classmethod
    def collect_manuscript_data(
        cls,
        project_id: str,
        author_name: str = "Penulis AI Novel Studio",
        approved_only: bool = True,
        include_codex_appendix: bool = False,
        db_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Mengumpulkan seluruh data proyek, fase cerita, bab, dan micro-beats.
        Jika approved_only=True, hanya mengambil beat berstatus COMPLETED/REVISED/APPROVED
        yang memiliki teks prosa. Jika belum ada beat berstatus tersebut namun ada beat
        yang sudah memiliki generated_prose, otomatis menyertakannya agar ekspor tidak kosong.
        """
        project = get_project(project_id, db_path=db_path)
        if not project:
            raise ValueError(f"Proyek novel dengan ID '{project_id}' tidak ditemukan.")

        phases = list_story_phases(project_id, db_path=db_path)
        chapters_raw = list_chapters(project_id, db_path=db_path)
        codex_items = list_codex_items(project_id, db_path=db_path) if include_codex_appendix else []

        compiled_chapters: List[Dict[str, Any]] = []
        total_words = 0
        total_included_beats = 0

        for ch in chapters_raw:
            beats = list_micro_beats(ch["id"], db_path=db_path)
            if approved_only:
                valid_beats = [
                    b
                    for b in beats
                    if (b.get("generated_prose") or "").strip()
                    and str(b.get("status", "")).upper() in cls.APPROVED_BEAT_STATUSES
                ]
                # Fallback aman jika penulis mengedit manual tetapi status masih PENDING/STREAMING
                if not valid_beats:
                    valid_beats = [b for b in beats if (b.get("generated_prose") or "").strip()]
            else:
                valid_beats = [b for b in beats if (b.get("generated_prose") or "").strip()]

            if not valid_beats:
                continue

            chapter_words = 0
            scene_segments: List[Dict[str, Any]] = []
            for b in valid_beats:
                prose_clean = (b.get("generated_prose") or "").strip()
                w_count = count_words(prose_clean)
                chapter_words += w_count
                total_included_beats += 1
                scene_segments.append(
                    {
                        "beat_id": b["id"],
                        "beat_number": b["beat_number"],
                        "pov_character_name": b.get("pov_character_name") or "",
                        "location_name": b.get("location_name") or "",
                        "tension_level": b.get("tension_level", 35),
                        "word_count": w_count,
                        "prose": prose_clean,
                    }
                )

            total_words += chapter_words
            compiled_chapters.append(
                {
                    "chapter_id": ch["id"],
                    "chapter_number": ch["chapter_number"],
                    "title": ch["title"],
                    "phase_name": ch.get("phase_name") or "",
                    "chapter_goal": ch.get("chapter_goal") or "",
                    "chapter_summary": ch.get("chapter_summary") or "",
                    "word_count": chapter_words,
                    "scenes": scene_segments,
                }
            )

        resolved_author = (author_name or "").strip()
        if not resolved_author or resolved_author == "Penulis AI Novel Studio":
            resolved_author = (project.get("author_name") or "").strip() or "Penulis Studio"

        return {
            "project": project,
            "author_name": resolved_author,
            "phases": phases,
            "chapters": compiled_chapters,
            "codex_items": codex_items,
            "total_chapters": len(compiled_chapters),
            "total_scenes": total_included_beats,
            "total_words": total_words,
            "compiled_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        }

    # ========================================================================
    # 1. KOMPILASI KE MARKDOWN (.md)
    # ========================================================================

    @classmethod
    def compile_markdown(
        cls,
        project_id: str,
        author_name: str = "Penulis AI Novel Studio",
        approved_only: bool = True,
        include_codex_appendix: bool = False,
        db_path: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Mengompilasi seluruh novel menjadi satu file Markdown (.md) rapi lengkap
        dengan YAML Frontmatter, Daftar Isi, Bab & Pemisah Adegan, serta Lampiran opsional.
        """
        data = cls.collect_manuscript_data(
            project_id=project_id,
            author_name=author_name,
            approved_only=approved_only,
            include_codex_appendix=include_codex_appendix,
            db_path=db_path,
        )
        project = data["project"]
        chapters = data["chapters"]

        lines: List[str] = [
            "---",
            f'title: "{project["title"]}"',
            f'author: "{data["author_name"]}"',
            f'genre: "{project["genre"]}"',
            f'language: "id"',
            f'total_chapters: {data["total_chapters"]}',
            f'total_words: {data["total_words"]}',
            f'compiled_at: "{data["compiled_at"]}"',
            "---",
            "",
            f"# {project['title']}",
            f"**Penulis:** {data['author_name']}  ",
            f"**Genre:** {project['genre']} | **Sudut Pandang:** {project.get('pov_style', 'Third-Person Limited')}  ",
            f"**Total Kata Naskah:** {data['total_words']:,} kata ({data['total_chapters']} Bab, {data['total_scenes']} Adegan)",
            "",
        ]

        if (project.get("logline") or "").strip():
            lines.extend(
                [
                    f"> *{project['logline'].strip()}*",
                    "",
                ]
            )

        lines.extend(
            [
                "---",
                "",
                "## Daftar Isi",
                "",
            ]
        )

        if not chapters:
            lines.append("*(Belum ada bab dengan teks naskah yang selesai ditulis.)*")
            lines.append("")
        else:
            for ch in chapters:
                anchor = f"bab-{ch['chapter_number']}"
                phase_tag = f" — *({ch['phase_name']})*" if ch.get("phase_name") else ""
                lines.append(
                    f"- [Bab {ch['chapter_number']}: {ch['title']}](#{anchor}) "
                    f"({ch['word_count']:,} kata){phase_tag}"
                )
            lines.append("")

        lines.extend(["---", ""])

        for ch in chapters:
            lines.append(f'<a id="bab-{ch["chapter_number"]}"></a>')
            lines.append(f"## Bab {ch['chapter_number']}: {ch['title']}")
            if ch.get("phase_name"):
                lines.append(f"*{ch['phase_name']}*")
            lines.append("")

            for idx, scene in enumerate(ch["scenes"]):
                if idx > 0:
                    lines.extend(["", "* * *", ""])
                paragraphs = cls._prose_to_paragraphs(scene["prose"])
                lines.append("\n\n".join(paragraphs))

            lines.extend(["", "---", ""])

        if include_codex_appendix and data["codex_items"]:
            lines.extend(
                [
                    "## Lampiran: Ensiklopedia & Karakter (Story Bible)",
                    "",
                ]
            )
            for item in data["codex_items"]:
                lines.append(f"### [{item['category']}] {item['name']}")
                lines.append(item["core_description"])
                st = item.get("current_state") or {}
                if item["category"] == "CHARACTER" and st:
                    lines.append(
                        f"- **Status Terakhir:** Lokasi: `{st.get('location') or '-'}` | "
                        f"Kondisi: `{st.get('condition') or 'Sehat'}` | "
                        f"Emosi: `{st.get('emotional_state') or 'Stabil'}`"
                    )
                lines.append("")

        filename = f"{cls.slugify_filename(project['title'])}.md"
        return filename, "\n".join(lines).strip() + "\n"

    # ========================================================================
    # 2. KOMPILASI KE EPUB STANDAR PENERBIT (.epub via EbookLib)
    # ========================================================================

    @classmethod
    def compile_epub(
        cls,
        project_id: str,
        author_name: str = "Penulis AI Novel Studio",
        approved_only: bool = True,
        include_synopsis: bool = True,
        db_path: Optional[str] = None,
    ) -> Tuple[str, bytes]:
        """
        Menggabungkan seluruh bab dan adegan yang telah disetujui menjadi file `.epub`
        standar penerbit menggunakan library `ebooklib` (lengkap dengan metadata judul,
        penulis, stylesheet buku cetak, halaman judul, dan daftar isi otomatis).
        """
        data = cls.collect_manuscript_data(
            project_id=project_id,
            author_name=author_name,
            approved_only=approved_only,
            include_codex_appendix=False,
            db_path=db_path,
        )
        project = data["project"]
        filename = f"{cls.slugify_filename(project['title'])}.epub"

        if epub is not None:
            epub_bytes = cls._build_epub_with_ebooklib(data, include_synopsis=include_synopsis)
        else:
            epub_bytes = cls._build_epub_standard_zip_fallback(data, include_synopsis=include_synopsis)

        return filename, epub_bytes

    @classmethod
    def _build_epub_with_ebooklib(
        cls,
        data: Dict[str, Any],
        include_synopsis: bool = True,
    ) -> bytes:
        project = data["project"]
        chapters = data["chapters"]
        author_name = data["author_name"]

        book = epub.EpubBook()
        book.set_identifier(f"urn:uuid:{project['id']}")
        book.set_title(project["title"])
        book.set_language("id")
        book.add_author(author_name)

        if (project.get("logline") or "").strip():
            book.add_metadata("DC", "description", project["logline"].strip())
        if (project.get("genre") or "").strip():
            book.add_metadata("DC", "subject", project["genre"].strip())
        book.add_metadata("DC", "publisher", "The Zen Literary Studio")
        book.add_metadata("DC", "date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

        # Stylesheet Tipografi Buku Cetak
        style_item = epub.EpubItem(
            uid="style_publisher",
            file_name="style/publisher.css",
            media_type="text/css",
            content=PUBLISHER_EPUB_CSS.encode("utf-8"),
        )
        book.add_item(style_item)

        spine_items: List[Any] = ["nav"]
        toc_items: List[Any] = []

        # 1. Halaman Judul (Title Page)
        title_html = f"""<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="id">
<head>
    <title>{html.escape(project['title'])}</title>
    <link rel="stylesheet" type="text/css" href="style/publisher.css"/>
</head>
<body>
    <div class="title-page">
        <div class="book-genre">{html.escape(project.get('genre') or 'Novel Fiksi')}</div>
        <h1 class="book-title">{html.escape(project['title'])}</h1>
        <div class="book-logline">{html.escape(project.get('logline') or '')}</div>
        <div class="book-author">{html.escape(author_name)}</div>
        <div class="book-meta">
            Diterbitkan melalui The Zen Literary Studio<br/>
            {data['total_chapters']} Bab &#8226; {data['total_words']:,} Kata<br/>
            {html.escape(data['compiled_at'])}
        </div>
    </div>
</body>
</html>"""
        title_page = epub.EpubHtml(
            title="Halaman Judul",
            file_name="title_page.xhtml",
            lang="id",
        )
        title_page.set_content(title_html.encode("utf-8"))
        title_page.add_item(style_item)
        book.add_item(title_page)
        spine_items.append(title_page)
        toc_items.append(epub.Link("title_page.xhtml", "Halaman Judul", "title_page"))

        # 2. Halaman Sinopsis & Kompas Cerita (Opsional)
        if include_synopsis and (project.get("main_objective") or project.get("logline")):
            synopsis_html = f"""<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="id">
<head>
    <title>Sinopsis &amp; Kompas Cerita</title>
    <link rel="stylesheet" type="text/css" href="style/publisher.css"/>
</head>
<body>
    <div class="chapter-header">
        <div class="chapter-number">Pengantar Naskah</div>
        <h2 class="chapter-title">Sinopsis &amp; Visi Naratif</h2>
    </div>
    <p class="first-paragraph">{html.escape(project.get('logline') or project.get('main_objective') or '')}</p>
    <p>{html.escape(project.get('main_objective') or '')}</p>
</body>
</html>"""
            synopsis_page = epub.EpubHtml(
                title="Sinopsis",
                file_name="synopsis.xhtml",
                lang="id",
            )
            synopsis_page.set_content(synopsis_html.encode("utf-8"))
            synopsis_page.add_item(style_item)
            book.add_item(synopsis_page)
            spine_items.append(synopsis_page)
            toc_items.append(epub.Link("synopsis.xhtml", "Sinopsis", "synopsis"))

        # 3. Halaman Bab demi Bab
        if not chapters:
            empty_ch = epub.EpubHtml(
                title="Naskah Belum Tersedia",
                file_name="chapter_empty.xhtml",
                lang="id",
            )
            empty_ch.set_content(
                b"<html><body><h2>Belum Ada Bab yang Disetujui</h2>"
                b"<p>Silakan tulis atau setujui Micro-Beat terlebih dahulu di Studio.</p></body></html>"
            )
            empty_ch.add_item(style_item)
            book.add_item(empty_ch)
            spine_items.append(empty_ch)
            toc_items.append(empty_ch)
        else:
            for ch in chapters:
                ch_num = ch["chapter_number"]
                ch_title_full = f"Bab {ch_num}: {ch['title']}"
                file_name = f"chapter_{ch_num:03d}.xhtml"

                scenes_xhtml_parts: List[str] = []
                for s_idx, scene in enumerate(ch["scenes"]):
                    if s_idx > 0:
                        scenes_xhtml_parts.append('<hr class="scene-break" />')
                    scenes_xhtml_parts.append(
                        cls._prose_to_xhtml_paragraphs(
                            scene["prose"],
                            is_first_beat_in_chapter=(s_idx == 0),
                        )
                    )

                phase_subtitle = (
                    f'<div class="chapter-phase">{html.escape(ch["phase_name"])}</div>'
                    if ch.get("phase_name")
                    else ""
                )
                chapter_xhtml = f"""<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="id">
<head>
    <title>{html.escape(ch_title_full)}</title>
    <link rel="stylesheet" type="text/css" href="style/publisher.css"/>
</head>
<body>
    <div class="chapter-header">
        <div class="chapter-number">Bab {ch_num}</div>
        <h2 class="chapter-title">{html.escape(ch['title'])}</h2>
        {phase_subtitle}
    </div>
    {"".join(scenes_xhtml_parts)}
</body>
</html>"""
                epub_ch = epub.EpubHtml(
                    title=ch_title_full,
                    file_name=file_name,
                    lang="id",
                )
                epub_ch.set_content(chapter_xhtml.encode("utf-8"))
                epub_ch.add_item(style_item)
                book.add_item(epub_ch)
                spine_items.append(epub_ch)
                toc_items.append(epub_ch)

        book.toc = tuple(toc_items)
        book.add_item(epub.EpubNcx())
        nav_item = epub.EpubNav()
        nav_item.add_item(style_item)
        book.add_item(nav_item)
        book.spine = spine_items

        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        try:
            epub.write_epub(tmp_path, book, {})
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    @classmethod
    def _build_epub_standard_zip_fallback(
        cls,
        data: Dict[str, Any],
        include_synopsis: bool = True,
    ) -> bytes:
        """
        Builder EPUB3/EPUB2 standar berbasis pustaka standar Python (zipfile + OPF + NCX)
        apabila paket `ebooklib` belum terinstal di environment.
        """
        project = data["project"]
        chapters = data["chapters"]
        author_name = data["author_name"]
        book_uuid = str(project.get("id") or uuid.uuid4())
        pub_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # 1. mimetype wajib tidak terkompresi dan berada di urutan pertama
            zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)

            # 2. META-INF/container.xml
            container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""
            zf.writestr("META-INF/container.xml", container_xml)

            # 3. Stylesheet
            zf.writestr("OEBPS/style/publisher.css", PUBLISHER_EPUB_CSS)

            manifest_entries = [
                '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
                '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
                '<item id="css" href="style/publisher.css" media-type="text/css"/>',
                '<item id="title_page" href="title_page.xhtml" media-type="application/xhtml+xml"/>',
            ]
            spine_entries = ['<itemref idref="title_page"/>']
            nav_links = ['<li><a href="title_page.xhtml">Halaman Judul</a></li>']
            ncx_navpoints = [
                """<navPoint id="navPoint-1" playOrder="1">
      <navLabel><text>Halaman Judul</text></navLabel>
      <content src="title_page.xhtml"/>
    </navPoint>"""
            ]
            play_order = 2

            # 4. Halaman Judul
            title_xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="id">
<head>
  <title>{html.escape(project['title'])}</title>
  <link rel="stylesheet" type="text/css" href="style/publisher.css"/>
</head>
<body>
  <div class="title-page">
    <div class="book-genre">{html.escape(project.get('genre') or 'Novel Fiksi')}</div>
    <h1 class="book-title">{html.escape(project['title'])}</h1>
    <div class="book-logline">{html.escape(project.get('logline') or '')}</div>
    <div class="book-author">{html.escape(author_name)}</div>
    <div class="book-meta">{data['total_chapters']} Bab &#8226; {data['total_words']:,} Kata</div>
  </div>
</body>
</html>"""
            zf.writestr("OEBPS/title_page.xhtml", title_xhtml)

            if include_synopsis and (project.get("main_objective") or project.get("logline")):
                synopsis_xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="id">
<head>
  <title>Sinopsis</title>
  <link rel="stylesheet" type="text/css" href="style/publisher.css"/>
</head>
<body>
  <div class="chapter-header">
    <div class="chapter-number">Pengantar</div>
    <h2 class="chapter-title">Sinopsis &amp; Kompas Cerita</h2>
  </div>
  <p class="first-paragraph">{html.escape(project.get('logline') or '')}</p>
  <p>{html.escape(project.get('main_objective') or '')}</p>
</body>
</html>"""
                zf.writestr("OEBPS/synopsis.xhtml", synopsis_xhtml)
                manifest_entries.append(
                    '<item id="synopsis" href="synopsis.xhtml" media-type="application/xhtml+xml"/>'
                )
                spine_entries.append('<itemref idref="synopsis"/>')
                nav_links.append('<li><a href="synopsis.xhtml">Sinopsis</a></li>')
                ncx_navpoints.append(
                    f"""<navPoint id="navPoint-{play_order}" playOrder="{play_order}">
      <navLabel><text>Sinopsis</text></navLabel>
      <content src="synopsis.xhtml"/>
    </navPoint>"""
                )
                play_order += 1

            # 5. Halaman Bab
            for ch in chapters:
                ch_num = ch["chapter_number"]
                item_id = f"chapter_{ch_num:03d}"
                href = f"{item_id}.xhtml"
                ch_label = f"Bab {ch_num}: {ch['title']}"

                scenes_parts: List[str] = []
                for s_idx, scene in enumerate(ch["scenes"]):
                    if s_idx > 0:
                        scenes_parts.append('<hr class="scene-break" />')
                    scenes_parts.append(
                        cls._prose_to_xhtml_paragraphs(
                            scene["prose"],
                            is_first_beat_in_chapter=(s_idx == 0),
                        )
                    )

                ch_xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="id">
<head>
  <title>{html.escape(ch_label)}</title>
  <link rel="stylesheet" type="text/css" href="style/publisher.css"/>
</head>
<body>
  <div class="chapter-header">
    <div class="chapter-number">Bab {ch_num}</div>
    <h2 class="chapter-title">{html.escape(ch['title'])}</h2>
  </div>
  {"".join(scenes_parts)}
</body>
</html>"""
                zf.writestr(f"OEBPS/{href}", ch_xhtml)
                manifest_entries.append(
                    f'<item id="{item_id}" href="{href}" media-type="application/xhtml+xml"/>'
                )
                spine_entries.append(f'<itemref idref="{item_id}"/>')
                nav_links.append(f'<li><a href="{href}">{html.escape(ch_label)}</a></li>')
                ncx_navpoints.append(
                    f"""<navPoint id="navPoint-{play_order}" playOrder="{play_order}">
      <navLabel><text>{html.escape(ch_label)}</text></navLabel>
      <content src="{href}"/>
    </navPoint>"""
                )
                play_order += 1

            # 6. Daftar Isi (nav.xhtml & toc.ncx)
            nav_xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="id">
<head>
  <title>Daftar Isi</title>
  <link rel="stylesheet" type="text/css" href="style/publisher.css"/>
</head>
<body>
  <nav epub:type="toc" id="toc">
    <h2>Daftar Isi</h2>
    <ol class="toc-list">
      {"".join(nav_links)}
    </ol>
  </nav>
</body>
</html>"""
            zf.writestr("OEBPS/nav.xhtml", nav_xhtml)

            toc_ncx = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="urn:uuid:{book_uuid}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>{html.escape(project['title'])}</text></docTitle>
  <navMap>
    {"".join(ncx_navpoints)}
  </navMap>
</ncx>"""
            zf.writestr("OEBPS/toc.ncx", toc_ncx)

            # 7. Package Document (OEBPS/content.opf)
            content_opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="BookId">urn:uuid:{book_uuid}</dc:identifier>
    <dc:title>{html.escape(project['title'])}</dc:title>
    <dc:creator>{html.escape(author_name)}</dc:creator>
    <dc:language>id</dc:language>
    <dc:publisher>The Zen Literary Studio</dc:publisher>
    <dc:date>{pub_date}</dc:date>
    <meta property="dcterms:modified">{datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}</meta>
  </metadata>
  <manifest>
    {"".join(manifest_entries)}
  </manifest>
  <spine toc="ncx">
    {"".join(spine_entries)}
  </spine>
</package>"""
            zf.writestr("OEBPS/content.opf", content_opf)

        return buf.getvalue()

    # ========================================================================
    # 3. KOMPILASI PRINT-READY BOOK HTML / PDF PRINT LAYOUT
    # ========================================================================

    @classmethod
    def compile_print_html(
        cls,
        project_id: str,
        author_name: str = "",
        approved_only: bool = True,
        include_synopsis: bool = True,
        db_path: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Menghasilkan halaman buku HTML mandiri berstandar tata letak cetak (`@page` & `page-break`)
        yang siap dicetak atau disimpan sebagai PDF melalui dialog Print browser (Ctrl+P).
        """
        data = cls.collect_manuscript_data(
            project_id=project_id,
            author_name=author_name,
            approved_only=approved_only,
            include_codex_appendix=False,
            db_path=db_path,
        )
        project = data["project"]
        chapters = data["chapters"]
        resolved_author = data["author_name"]
        filename = f"{cls.slugify_filename(project['title'])}_print.html"

        toc_items = []
        chapters_html = []
        for ch in chapters:
            ch_num = ch["chapter_number"]
            anchor = f"bab-{ch_num}"
            toc_items.append(
                f'<li><a href="#{anchor}"><span>Bab {ch_num}: {html.escape(ch["title"])}</span>'
                f'<span class="toc-words">{ch["word_count"]:,} kata</span></a></li>'
            )
            scenes_parts = []
            for s_idx, scene in enumerate(ch["scenes"]):
                if s_idx > 0:
                    scenes_parts.append('<div class="scene-break">* &#160; * &#160; *</div>')
                scenes_parts.append(
                    cls._prose_to_xhtml_paragraphs(
                        scene["prose"],
                        is_first_beat_in_chapter=(s_idx == 0),
                    )
                )
            phase_sub = (
                f'<div class="chapter-phase">{html.escape(ch["phase_name"])}</div>'
                if ch.get("phase_name")
                else ""
            )
            chapters_html.append(
                f'<section class="book-chapter" id="{anchor}">\n'
                f'  <div class="chapter-header">\n'
                f'    <div class="chapter-number">Bab {ch_num}</div>\n'
                f'    <h2 class="chapter-title">{html.escape(ch["title"])}</h2>\n'
                f'    {phase_sub}\n'
                f'  </div>\n'
                f'  {"".join(scenes_parts)}\n'
                f'</section>'
            )

        synopsis_block = ""
        if include_synopsis and (project.get("logline") or project.get("main_objective")):
            synopsis_block = (
                '<section class="book-chapter">\n'
                '  <div class="chapter-header"><div class="chapter-number">Pengantar</div>'
                '<h2 class="chapter-title">Sinopsis Naskah</h2></div>\n'
                f'  <p class="first-paragraph">{html.escape(project.get("logline") or "")}</p>\n'
                f'  <p>{html.escape(project.get("main_objective") or "")}</p>\n'
                '</section>\n'
            )

        empty_notice = (
            '<section class="book-chapter"><p style="text-align:center;">Belum ada adegan naskah yang tersedia untuk diekspor.</p></section>'
            if not chapters
            else ""
        )

        html_doc = f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{html.escape(project['title'])} — Naskah Siap Cetak</title>
<style>
@page {{
    size: A5;
    margin: 22mm 18mm 22mm 20mm;
}}
* {{ box-sizing: border-box; }}
body {{
    font-family: "Literata", "Georgia", "Palatino Linotype", "Book Antiqua", serif;
    font-size: 11.5pt;
    line-height: 1.72;
    color: #18181B;
    background: #F6F3EC;
    margin: 0;
    padding: 24px 16px 64px;
}}
.print-toolbar {{
    position: sticky;
    top: 12px;
    max-width: 720px;
    margin: 0 auto 24px;
    background: #1C1917;
    color: #FBF9F5;
    padding: 10px 16px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 13px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.2);
}}
.print-toolbar button {{
    background: #D97706;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 700;
    cursor: pointer;
}}
.book-sheet {{
    max-width: 680px;
    margin: 0 auto;
    background: #FFFFFF;
    padding: 48px 54px;
    box-shadow: 0 8px 30px rgba(24,24,27,0.08);
    border: 1px solid #E5DFD3;
}}
.title-page {{
    text-align: center;
    padding: 96px 24px;
    page-break-after: always;
    break-after: page;
}}
.book-genre {{
    font-size: 9.5pt;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: #57534E;
    margin-bottom: 18px;
}}
.book-title {{
    font-size: 26pt;
    line-height: 1.2;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin: 0 0 18px;
}}
.book-logline {{
    font-style: italic;
    color: #44403C;
    max-width: 46ch;
    margin: 0 auto 36px;
}}
.book-author {{
    font-size: 13pt;
    font-weight: 700;
    letter-spacing: 0.08em;
    margin-top: 28px;
}}
.book-meta {{
    font-size: 9pt;
    color: #78716C;
    margin-top: 24px;
}}
.toc-section {{
    page-break-after: always;
    break-after: page;
    padding-top: 16px;
}}
.toc-list {{
    list-style: none;
    padding: 0;
    margin: 24px 0 0;
}}
.toc-list li {{
    border-bottom: 1px dotted #D6D3CD;
    padding: 6px 0;
}}
.toc-list a {{
    display: flex;
    justify-content: space-between;
    text-decoration: none;
    color: #18181B;
}}
.toc-words {{
    font-size: 9pt;
    color: #78716C;
    font-family: monospace;
}}
.book-chapter {{
    page-break-before: always;
    break-before: page;
}}
.chapter-header {{
    text-align: center;
    margin: 20px 0 32px;
}}
.chapter-number {{
    font-size: 9.5pt;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: #78716C;
}}
.chapter-title {{
    font-size: 18pt;
    margin: 6px 0 4px;
}}
.chapter-phase {{
    font-size: 9.5pt;
    font-style: italic;
    color: #57534E;
}}
p {{
    margin: 0;
    text-indent: 1.5em;
    text-align: justify;
    orphans: 2;
    widows: 2;
}}
p.first-paragraph {{
    text-indent: 0;
}}
.scene-break {{
    text-align: center;
    margin: 20px 0;
    color: #57534E;
    letter-spacing: 0.35em;
}}
@media print {{
    body {{
        background: #FFFFFF;
        padding: 0;
    }}
    .print-toolbar {{
        display: none !important;
    }}
    .book-sheet {{
        max-width: none;
        box-shadow: none;
        border: none;
        padding: 0;
    }}
}}
</style>
</head>
<body>
  <div class="print-toolbar">
    <div><strong>Pratinjau Naskah Buku</strong> — {html.escape(project['title'])} ({data['total_chapters']} Bab, {data['total_words']:,} kata)</div>
    <button onclick="window.print()">🖨️ Cetak / Simpan PDF</button>
  </div>
  <main class="book-sheet">
    <section class="title-page">
      <div class="book-genre">{html.escape(project.get('genre') or 'Novel Fiksi')}</div>
      <h1 class="book-title">{html.escape(project['title'])}</h1>
      <div class="book-logline">{html.escape(project.get('logline') or '')}</div>
      <div class="book-author">{html.escape(resolved_author)}</div>
      <div class="book-meta">{data['total_chapters']} Bab &#8226; {data['total_words']:,} Kata &#8226; {html.escape(data['compiled_at'])}</div>
    </section>
    <section class="toc-section">
      <h2 class="chapter-title" style="text-align:center;">Daftar Isi</h2>
      <ul class="toc-list">
        {"".join(toc_items)}
      </ul>
    </section>
    {synopsis_block}
    {"".join(chapters_html)}
    {empty_notice}
  </main>
</body>
</html>"""
        return filename, html_doc


# ============================================================================
# FASTAPI ROUTER UNTUK EXPORT EPUB & MARKDOWN
# ============================================================================

if APIRouter is not None:
    router = APIRouter(tags=["Manuscript Exporter"])

    @router.get("/api/projects/{project_id}/export/epub")
    def api_export_project_epub(
        project_id: str,
        author: str = Query(default="", description="Nama penulis pada metadata EPUB (kosong = pakai Author Name proyek)"),
        approved_only: bool = Query(default=True, description="Hanya sertakan adegan yang telah selesai/disetujui"),
        include_synopsis: bool = Query(default=True, description="Sertakan halaman sinopsis di awal buku"),
    ) -> Response:
        """
        Menggabungkan seluruh bab dan adegan yang telah disetujui menjadi file `.epub`
        standar penerbit menggunakan `ebooklib` (lengkap dengan metadata judul, penulis,
        dan daftar isi otomatis).
        """
        try:
            filename, epub_bytes = ManuscriptCompiler.compile_epub(
                project_id=project_id,
                author_name=author,
                approved_only=approved_only,
                include_synopsis=include_synopsis,
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

        return Response(
            content=epub_bytes,
            media_type="application/epub+zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )

    @router.get("/api/projects/{project_id}/export/markdown")
    def api_export_project_markdown(
        project_id: str,
        author: str = Query(default="", description="Nama penulis pada YAML frontmatter"),
        approved_only: bool = Query(default=True, description="Hanya sertakan adegan yang telah selesai/disetujui"),
        include_codex_appendix: bool = Query(default=True, description="Sertakan lampiran Story Bible & Codex di akhir naskah"),
    ) -> Response:
        """
        Mengompilasi seluruh novel menjadi satu file Markdown (`.md`) rapi.
        """
        try:
            filename, md_content = ManuscriptCompiler.compile_markdown(
                project_id=project_id,
                author_name=author,
                approved_only=approved_only,
                include_codex_appendix=include_codex_appendix,
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

        return Response(
            content=md_content.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )

    @router.get("/api/projects/{project_id}/export/print-html")
    def api_export_project_print_html(
        project_id: str,
        author: str = Query(default="", description="Nama penulis pada halaman judul cetak"),
        approved_only: bool = Query(default=True, description="Hanya sertakan adegan yang telah selesai/disetujui"),
        include_synopsis: bool = Query(default=True, description="Sertakan halaman sinopsis di awal buku"),
        download: bool = Query(default=False, description="Unduh sebagai file alih-alih pratinjau cetak"),
    ) -> Response:
        """
        Menghasilkan layout buku HTML siap cetak / Save-as-PDF (browser Ctrl+P).
        """
        try:
            filename, html_doc = ManuscriptCompiler.compile_print_html(
                project_id=project_id,
                author_name=author,
                approved_only=approved_only,
                include_synopsis=include_synopsis,
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

        disposition = "attachment" if download else "inline"
        return Response(
            content=html_doc.encode("utf-8"),
            media_type="text/html; charset=utf-8",
            headers={
                "Content-Disposition": f'{disposition}; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )
else:
    router = None
