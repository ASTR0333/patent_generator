"""
FastAPI backend for patent-generator.

Run with:
    uvicorn backend.main:app --reload --port 8000
or from the backend/ directory:
    uvicorn main:app --reload --port 8000
"""

import os
import re
import shutil
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Make sure the project root is on the path so we can import generator.py
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from generator import (  # noqa: E402
    CODE_EXTENSIONS,
    PATTERNS,
    SPECIAL_FILENAMES,
    build_fio_string,
    collect_code_files,
    extract_archive,
    is_archive_file,
    is_code_file,
)
from docxtpl import DocxTemplate  # noqa: E402

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_DIR_RESOLVED = OUTPUT_DIR.resolve()

TEMPLATES_DIR = ROOT / "templates"
UPLOAD_CHUNK_SIZE = 1024 * 1024
SOURCE_HEADER_TEMPLATE = "// ===== {} =====\n{}"
SAFE_FILENAME_CHARS_RE = re.compile(r"[^\w.\-]+", re.UNICODE)
COMPILED_PATTERNS: dict[str, tuple[re.Pattern[str], str]] = {
    field: (re.compile(pattern), msg)
    for field, (pattern, msg) in PATTERNS.items()
}

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Patent Generator API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class Author(BaseModel):
    fio: str
    address: str
    phone: str
    email: str
    inn: str
    passport: str
    snils: str
    birthday: str
    skill: str


class GenerateRequest(BaseModel):
    name: str
    authors: list[Author]
    source_file: str   # filename relative to OUTPUT_DIR (previously uploaded)
    referat_file: str  # filename relative to OUTPUT_DIR (previously uploaded)


class ValidateRequest(BaseModel):
    field: str
    value: str


# ---------------------------------------------------------------------------
# Helper: safe filename in OUTPUT_DIR
# ---------------------------------------------------------------------------


def _output_path(filename: str) -> Path:
    """Resolve *filename* inside OUTPUT_DIR and verify it stays inside."""
    target = (OUTPUT_DIR / filename).resolve()
    try:
        target.relative_to(OUTPUT_DIR_RESOLVED)
    except ValueError:
        raise HTTPException(status_code=400, detail="Недопустимый путь к файлу.")
    return target


def _remove_uuid_prefix(filename: str) -> str:
    """Remove UUID prefix from filename if present (format: {32_hex_chars}_{original_name})."""
    if len(filename) > 33 and filename[32] == '_':
        # Check if first 32 chars are hex
        if all(c in '0123456789abcdef' for c in filename[:32]):
            return filename[33:]
    return filename


def _sanitize_archive_stem(name: str) -> str:
    """Build a safe archive stem from program name."""
    cleaned = SAFE_FILENAME_CHARS_RE.sub("_", name.strip()).strip("._")
    return cleaned or "package"


def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return path.read_text(encoding="latin-1", errors="replace")


def _prepare_source_payload(source_path: Path, extract_dir: Path) -> tuple[str, list[tuple[Path, str]]]:
    """
    Build combined source-code text and a list of files to include in ZIP.
    Returns tuple: (combined_source_code, [(absolute_path, archive_name), ...]).
    """
    if is_archive_file(str(source_path)):
        extract_archive(str(source_path), str(extract_dir))
        code_files = [Path(p) for p in collect_code_files(str(extract_dir))]
        if not code_files:
            raise ValueError("В архиве не найдено файлов с исходным кодом.")

        parts: list[str] = []
        zip_entries: list[tuple[Path, str]] = []
        for code_file in code_files:
            rel_name = code_file.relative_to(extract_dir).as_posix()
            parts.append(SOURCE_HEADER_TEMPLATE.format(rel_name, _read_text_file(code_file)))
            zip_entries.append((code_file, f"source_code/{rel_name}"))
        return "\n\n".join(parts), zip_entries

    if is_code_file(str(source_path)):
        source_clean_name = _remove_uuid_prefix(source_path.name)
        return _read_text_file(source_path), [(source_path, f"source_code/{source_clean_name}")]

    raise ValueError(
        f"Файл '{source_path}' не является поддерживаемым файлом исходного кода или архивом."
    )


async def _save_upload_file(upload_file: UploadFile, destination: Path) -> None:
    with destination.open("wb") as f:
        while True:
            chunk = await upload_file.read(UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            f.write(chunk)
    await upload_file.close()


# ---------------------------------------------------------------------------
# /api/upload (unified)
# ---------------------------------------------------------------------------


async def _handle_upload(file: UploadFile, kind: str) -> dict[str, Any]:
    original_name = file.filename or ("upload" if kind == "source" else "referat.docx")
    if kind == "source" and not (is_code_file(original_name) or is_archive_file(original_name)):
        raise HTTPException(
            status_code=400,
            detail=(
                "Неподдерживаемый тип файла. "
                "Загрузите файл с исходным кодом (.py, .js, .java, …) "
                "или архив (.zip, .tar.gz, .rar, .7z, …)."
            ),
        )

    unique_name = f"{uuid.uuid4().hex}_{original_name}"
    dest = OUTPUT_DIR / unique_name
    await _save_upload_file(file, dest)

    code_files: list[str] = []
    if kind == "source" and is_archive_file(str(dest)):
        def _extract_code_files() -> list[str]:
            tmp_dir = tempfile.mkdtemp()
            try:
                extract_archive(str(dest), tmp_dir)
                return [os.path.relpath(p, tmp_dir) for p in collect_code_files(tmp_dir)]
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        try:
            code_files = await run_in_threadpool(_extract_code_files)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Ошибка распаковки архива: {exc}")

    return {"filename": unique_name, "code_files": code_files}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), kind: str = Form(...)) -> dict[str, Any]:
    """Unified upload endpoint for source code and referat files."""
    if kind not in {"source", "referat"}:
        raise HTTPException(status_code=400, detail="Параметр kind должен быть source или referat.")
    return await _handle_upload(file, kind)


# Backward compatibility aliases
@app.post("/api/upload-source")
async def upload_source(file: UploadFile = File(...)) -> dict[str, Any]:
    return await _handle_upload(file, "source")


@app.post("/api/upload-referat")
async def upload_referat(file: UploadFile = File(...)) -> dict[str, Any]:
    return await _handle_upload(file, "referat")


# ---------------------------------------------------------------------------
# /api/generate
# ---------------------------------------------------------------------------


@app.post("/api/generate")
async def generate(req: GenerateRequest) -> dict[str, Any]:
    """Generate all patent documents and return as a single ZIP archive."""
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Название программы не может быть пустым.")

    if not req.authors:
        raise HTTPException(status_code=400, detail="Необходимо указать хотя бы одного автора.")

    # Validate all author fields
    for idx, author in enumerate(req.authors):
        for field, (pattern, msg) in COMPILED_PATTERNS.items():
            value = getattr(author, field, "")
            if not pattern.fullmatch(value):
                raise HTTPException(
                    status_code=422,
                    detail=f"Автор {idx + 1}, поле '{field}': {msg}",
                )

    source_path = _output_path(req.source_file)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail=f"Файл исходного кода не найден: {req.source_file}")

    referat_path = _output_path(req.referat_file)
    if not referat_path.exists():
        raise HTTPException(status_code=404, detail=f"Файл реферата не найден: {req.referat_file}")

    def _generate_sync() -> dict[str, Any]:
        authors_dicts = [a.model_dump() for a in req.authors]
        fio_of_authors = build_fio_string(authors_dicts)
        quantity = len(req.authors)

        with tempfile.TemporaryDirectory(prefix="patent_generate_") as temp_dir:
            work_dir = Path(temp_dir)
            extract_dir = work_dir / "source_extract"
            extract_dir.mkdir(exist_ok=True)

            try:
                code, source_zip_entries = _prepare_source_payload(source_path, extract_dir)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc))

            source_code_out = work_dir / "source-code.docx"
            doc = DocxTemplate(str(TEMPLATES_DIR / "source_code_template.docx"))
            doc.render({"name": req.name, "fio_of_authors": fio_of_authors, "code": code})
            doc.save(str(source_code_out))

            nr = "?"
            ns = "?"
            page_count_warning = None
            try:
                from generator import count_pages_exact
                nr = str(count_pages_exact(str(referat_path)))
                ns = str(count_pages_exact(str(source_code_out)))
            except (RuntimeError, Exception) as e:
                page_count_warning = f"Не удалось подсчитать количество страниц: {str(e)}"

            _generate_docs(req.name, quantity, authors_dicts, nr, ns, work_dir)

            generated = [
                "source-code.docx",
                "pril1-211-1-1.docx",
                "pril1-211-1-2.docx",
            ]
            if quantity >= 2:
                for i in range(2, quantity + 1):
                    generated.append(f"pril1-211-2-1_author{i}.docx")
                    generated.append(f"pril1-211-2-2_author{i}.docx")

            if quantity == 1:
                generated += ["pril3_211.docx", "pril4_211.docx"]
            else:
                for i in range(1, quantity + 1):
                    generated.append(f"pril3_211_author{i}.docx")
                    generated.append(f"pril4_211_author{i}.docx")

            existing = [f for f in generated if (work_dir / f).exists()]

            archive_stem = _sanitize_archive_stem(req.name)
            archive_path = OUTPUT_DIR / f"{archive_stem}_пакет_документов_{uuid.uuid4().hex[:8]}.zip"

            with zipfile.ZipFile(str(archive_path), "w") as zf:
                for filename in existing:
                    zf.write(str(work_dir / filename), filename)

                referat_clean_name = _remove_uuid_prefix(referat_path.name)
                zf.write(str(referat_path), f"referat/{referat_clean_name}")

                for abs_path, arcname in source_zip_entries:
                    zf.write(str(abs_path), arcname)

        response = {"archive_filename": archive_path.name}
        if page_count_warning:
            response["warning"] = page_count_warning
        return response

    return await run_in_threadpool(_generate_sync)


def _generate_docs(
    name: str,
    quantity: int,
    authors: list[dict],
    nr: str,
    ns: str,
    output_dir: Path,
) -> None:
    """Generate pril documents without any interactive CLI prompts."""
    author1 = authors[0]
    passport_parts = author1["passport"].split(" ")
    passport_series_number = f"{passport_parts[0]} {passport_parts[1]}"
    day, month, year = author1["birthday"].split(".")

    doc = DocxTemplate(str(TEMPLATES_DIR / "pril1-211-1-1.docx"))
    doc.render({
        "name": name,
        "fio_author1": author1["fio"],
        "quantity_of_authors": quantity,
        "adres_author1": author1["address"],
        "phone_author1": author1["phone"],
        "email_author1": author1["email"],
        "inn_author1": author1["inn"],
        "passport_author1": passport_series_number,
        "snils_author1": author1["snils"],
    })
    doc.save(str(output_dir / "pril1-211-1-1.docx"))

    doc = DocxTemplate(str(TEMPLATES_DIR / "pril1-211-1-2.docx"))
    doc.render({
        "name": name,
        "fio_author1": author1["fio"],
        "q": quantity,
        "adres_author1": author1["address"],
        "d_a1": day,
        "m_a1": month,
        "y_a1": year,
        "skill_author1": author1["skill"],
        "ns": ns,
        "nr": nr,
    })
    doc.save(str(output_dir / "pril1-211-1-2.docx"))

    for idx in range(1, quantity):
        author = authors[idx]
        passport_parts = author["passport"].split(" ")
        passport_series_number = f"{passport_parts[0]} {passport_parts[1]}"
        day, month, year = author["birthday"].split(".")

        doc = DocxTemplate(str(TEMPLATES_DIR / "pril1-211-2-1.docx"))
        doc.render({
            "name": name,
            "fio_author": author["fio"],
            "quantity_of_authors": quantity,
            "adres_author": author["address"],
            "passport_author": passport_series_number,
            "snils_author": author["snils"],
        })
        doc.save(str(output_dir / f"pril1-211-2-1_author{idx + 1}.docx"))

        doc = DocxTemplate(str(TEMPLATES_DIR / "pril1-211-2-2.docx"))
        doc.render({
            "name": name,
            "fio_author": author["fio"],
            "adres_author": author["address"],
            "d_a": day,
            "m_a": month,
            "y_a": year,
            "skill_author": author["skill"],
        })
        doc.save(str(output_dir / f"pril1-211-2-2_author{idx + 1}.docx"))

    for idx, author in enumerate(authors):
        doc = DocxTemplate(str(TEMPLATES_DIR / "pril3_211.docx"))
        doc.render({
            "name": name,
            "fio_author": author["fio"],
            "adres_author": author["address"],
            "passport_author_fully": author["passport"],
        })
        if len(authors) == 1:
            doc.save(str(output_dir / "pril3_211.docx"))
        else:
            doc.save(str(output_dir / f"pril3_211_author{idx + 1}.docx"))

    for idx, author in enumerate(authors):
        day, month, year = author["birthday"].split(".")
        doc = DocxTemplate(str(TEMPLATES_DIR / "pril4_211.docx"))
        doc.render({
            "name": name,
            "fio_author": author["fio"],
            "adres_author": author["address"],
            "d_a": day,
            "m_a": month,
            "y_a": year,
            "skill_author": author["skill"],
        })
        if len(authors) == 1:
            doc.save(str(output_dir / "pril4_211.docx"))
        else:
            doc.save(str(output_dir / f"pril4_211_author{idx + 1}.docx"))


# ---------------------------------------------------------------------------
# /api/validate
# ---------------------------------------------------------------------------


@app.post("/api/validate")
async def validate(req: ValidateRequest) -> dict[str, Any]:
    """Validate a single field value against the known PATTERNS."""
    if req.field not in COMPILED_PATTERNS:
        raise HTTPException(status_code=400, detail=f"Неизвестное поле: {req.field}")

    pattern, msg = COMPILED_PATTERNS[req.field]
    valid = bool(pattern.fullmatch(req.value))
    return {"field": req.field, "valid": valid, "message": "" if valid else msg}


# ---------------------------------------------------------------------------
# /api/patterns  – expose all patterns/hints to the frontend
# ---------------------------------------------------------------------------


@app.get("/api/patterns")
async def get_patterns() -> dict[str, Any]:
    return {
        field: {"pattern": pattern, "hint": msg}
        for field, (pattern, msg) in PATTERNS.items()
    }


# ---------------------------------------------------------------------------
# /api/download/{filename}
# ---------------------------------------------------------------------------


@app.get("/api/download/{filename}")
async def download(filename: str) -> FileResponse:
    target = _output_path(filename)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Файл не найден: {filename}")
    return FileResponse(
        path=str(target),
        filename=filename,
        media_type="application/octet-stream",
    )
