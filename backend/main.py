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
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
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
    generate_pril1_211_1,
    generate_pril1_211_2,
    generate_pril3_211,
    generate_pril4_211,
    is_archive_file,
    is_code_file,
    read_code_from_path,
)
from docxtpl import DocxTemplate  # noqa: E402

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

TEMPLATES_DIR = ROOT / "templates"

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
    if not str(target).startswith(str(OUTPUT_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Недопустимый путь к файлу.")
    return target


# ---------------------------------------------------------------------------
# /api/upload-source
# ---------------------------------------------------------------------------


@app.post("/api/upload-source")
async def upload_source(file: UploadFile = File(...)) -> dict[str, Any]:
    """Accept a source-code file (any recognised extension) or a supported archive."""
    original_name = file.filename or "upload"
    if not (is_code_file(original_name) or is_archive_file(original_name)):
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
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    # If it's an archive, list recognised code files inside it for the client
    code_files: list[str] = []
    if is_archive_file(str(dest)):
        tmp_dir = tempfile.mkdtemp()
        try:
            extract_archive(str(dest), tmp_dir)
            code_files = [
                os.path.relpath(p, tmp_dir) for p in collect_code_files(tmp_dir)
            ]
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Ошибка распаковки архива: {exc}")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return {"filename": unique_name, "code_files": code_files}


# ---------------------------------------------------------------------------
# /api/upload-referat
# ---------------------------------------------------------------------------


@app.post("/api/upload-referat")
async def upload_referat(file: UploadFile = File(...)) -> dict[str, Any]:
    """Accept the abstract (referat) .docx file."""
    original_name = file.filename or "referat.docx"
    unique_name = f"{uuid.uuid4().hex}_{original_name}"
    dest = OUTPUT_DIR / unique_name
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"filename": unique_name}


# ---------------------------------------------------------------------------
# /api/generate
# ---------------------------------------------------------------------------


@app.post("/api/generate")
async def generate(req: GenerateRequest) -> dict[str, Any]:
    """Generate all patent documents and return their filenames."""
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Название программы не может быть пустым.")

    if not req.authors:
        raise HTTPException(status_code=400, detail="Необходимо указать хотя бы одного автора.")

    # Validate all author fields
    for idx, author in enumerate(req.authors):
        for field, (pattern, msg) in PATTERNS.items():
            value = getattr(author, field, "")
            if not re.fullmatch(pattern, value):
                raise HTTPException(
                    status_code=422,
                    detail=f"Автор {idx + 1}, поле '{field}': {msg}",
                )

    # Read source code
    source_path = _output_path(req.source_file)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail=f"Файл исходного кода не найден: {req.source_file}")

    try:
        code = read_code_from_path(str(source_path))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    authors_dicts = [a.model_dump() for a in req.authors]
    fio_of_authors = build_fio_string(authors_dicts)
    quantity = len(req.authors)

    # Generate source-code.docx
    source_code_out = str(OUTPUT_DIR / "source-code.docx")
    doc = DocxTemplate(str(TEMPLATES_DIR / "source_code_template.docx"))
    doc.render({"name": req.name, "fio_of_authors": fio_of_authors, "code": code})
    doc.save(source_code_out)

    # Count pages (skip on non-Windows)
    referat_path = _output_path(req.referat_file)
    if not referat_path.exists():
        raise HTTPException(status_code=404, detail=f"Файл реферата не найден: {req.referat_file}")

    nr = "?"
    ns = "?"
    try:
        from generator import count_pages_exact
        nr = str(count_pages_exact(str(referat_path)))
        ns = str(count_pages_exact(source_code_out))
    except RuntimeError:
        pass  # non-Windows environment

    # Monkey-patch count_pages_exact return for generate_pril1_211_1
    # We pass pre-resolved paths to avoid the CLI file-exists check
    _generate_docs(req.name, quantity, authors_dicts, str(referat_path), nr, ns)

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

    # Only return files that were actually created
    existing = [f for f in generated if (OUTPUT_DIR / f).exists()]

    return {"files": existing}


def _generate_docs(
    name: str,
    quantity: int,
    authors: list[dict],
    referat_path: str,
    nr: str,
    ns: str,
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
        "skils_author1": author1["snils"],
    })
    doc.save(str(OUTPUT_DIR / "pril1-211-1-1.docx"))

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
    doc.save(str(OUTPUT_DIR / "pril1-211-1-2.docx"))

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
        doc.save(str(OUTPUT_DIR / f"pril1-211-2-1_author{idx + 1}.docx"))

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
        doc.save(str(OUTPUT_DIR / f"pril1-211-2-2_author{idx + 1}.docx"))

    for idx, author in enumerate(authors):
        doc = DocxTemplate(str(TEMPLATES_DIR / "pril3_211.docx"))
        doc.render({
            "name": name,
            "fio_author": author["fio"],
            "adres_author": author["address"],
            "passport_author_fully": author["passport"],
        })
        if len(authors) == 1:
            doc.save(str(OUTPUT_DIR / "pril3_211.docx"))
        else:
            doc.save(str(OUTPUT_DIR / f"pril3_211_author{idx + 1}.docx"))

    for idx, author in enumerate(authors):
        day, month, year = author["birthday"].split(".")
        doc = DocxTemplate(str(TEMPLATES_DIR / "pril4_211 .docx"))
        doc.render({
            "name": name,
            "fio_author": author["fio"],
            "adres_author": author["address"],
            "d_a": day,
            "m_a": month,
            "y_a": year,
        })
        if len(authors) == 1:
            doc.save(str(OUTPUT_DIR / "pril4_211.docx"))
        else:
            doc.save(str(OUTPUT_DIR / f"pril4_211_author{idx + 1}.docx"))


# ---------------------------------------------------------------------------
# /api/validate
# ---------------------------------------------------------------------------


@app.post("/api/validate")
async def validate(req: ValidateRequest) -> dict[str, Any]:
    """Validate a single field value against the known PATTERNS."""
    if req.field not in PATTERNS:
        raise HTTPException(status_code=400, detail=f"Неизвестное поле: {req.field}")

    pattern, msg = PATTERNS[req.field]
    valid = bool(re.fullmatch(pattern, req.value))
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
