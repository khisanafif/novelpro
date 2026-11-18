#!/usr/bin/env python3
"""
Sinkronisasi satu arah `frontend/` -> `docs/` untuk GitHub Pages Static Hosting.
Menjamin UI utama FastAPI dan versi GitHub Pages selalu identik tanpa duplikasi manual.

Penggunaan:
  python3 scripts/sync_github_pages.py          # Menyalin & memperbarui folder docs/
  python3 scripts/sync_github_pages.py --check  # Memastikan docs/ 100% sinkron dengan frontend/
"""
import argparse
import hashlib
import shutil
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
DOCS_DIR = ROOT_DIR / "docs"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def collect_relative_files(base_dir: Path) -> dict[str, Path]:
    if not base_dir.exists():
        return {}
    out: dict[str, Path] = {}
    for p in sorted(base_dir.rglob("*")):
        if p.is_file():
            rel = p.relative_to(base_dir).as_posix()
            if rel == ".nojekyll":
                continue
            out[rel] = p
    return out


def sync_docs() -> None:
    src_files = collect_relative_files(FRONTEND_DIR)
    if DOCS_DIR.exists():
        shutil.rmtree(DOCS_DIR)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    for rel, src_path in src_files.items():
        dst_path = DOCS_DIR / rel
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dst_path)
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")
    print(f"OK: Tersinkronisasi {len(src_files)} file frontend/ -> docs/ (+ .nojekyll)")


def check_docs() -> int:
    src_files = collect_relative_files(FRONTEND_DIR)
    dst_files = collect_relative_files(DOCS_DIR)
    diffs: list[str] = []

    if not (DOCS_DIR / ".nojekyll").is_file():
        diffs.append("MISSING docs/.nojekyll")

    for rel in sorted(set(src_files) | set(dst_files)):
        if rel not in dst_files:
            diffs.append(f"MISSING in docs/: {rel}")
        elif rel not in src_files:
            diffs.append(f"EXTRA in docs/: {rel}")
        elif file_sha256(src_files[rel]) != file_sha256(dst_files[rel]):
            diffs.append(f"MODIFIED in docs/: {rel}")

    if diffs:
        for d in diffs:
            print(d)
        print("Jalankan: python3 scripts/sync_github_pages.py")
        return 1

    print(f"OK: docs/ identik dengan frontend/ ({len(src_files)} file)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync frontend/ ke docs/ untuk GitHub Pages")
    parser.add_argument("--check", action="store_true", help="Periksa konsistensi tanpa menulis file")
    args = parser.parse_args()
    if args.check:
        return check_docs()
    sync_docs()
    return check_docs()


if __name__ == "__main__":
    raise SystemExit(main())
