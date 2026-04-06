import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import uuid
import zipfile
from collections import Counter
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
    PATTERNS,
    build_fio_string,
    collect_code_files,
    extract_archive,
    is_archive_file,
    is_code_file,
)
from docxtpl import DocxTemplate  # noqa: E402

try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

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
LANGUAGE_BY_EXTENSION: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".jsx": "JavaScript (React)",
    ".tsx": "TypeScript (React)",
    ".java": "Java",
    ".c": "C",
    ".cpp": "C++",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".kts": "Kotlin Script",
    ".scala": "Scala",
    ".lua": "Lua",
    ".sh": "Shell",
    ".bash": "Bash",
    ".sql": "SQL",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "SASS",
    ".less": "Less",
    ".xml": "XML",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".ini": "INI",
    ".cfg": "Config",
    ".dart": "Dart",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".hs": "Haskell",
    ".erl": "Erlang",
    ".clj": "Clojure",
    ".groovy": "Groovy",
    ".asm": "Assembly",
    ".s": "Assembly",
    ".bat": "Batch",
    ".ps1": "PowerShell",
}
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_QUEUE_KEY = "patent_generator:jobs:queue"
REDIS_JOB_KEY_PREFIX = "patent_generator:job:"
OUTPUT_RETENTION_HOURS = int(os.getenv("OUTPUT_RETENTION_HOURS", "72"))
OUTPUT_CLEANUP_INTERVAL_SECONDS = int(os.getenv("OUTPUT_CLEANUP_INTERVAL_SECONDS", "21600"))

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
    referat_file: str | None = None  # filename relative to OUTPUT_DIR (previously uploaded)
    referat_text: str | None = None


class ValidateRequest(BaseModel):
    field: str
    value: str


class GenerateQueuedResponse(BaseModel):
    job_id: str
    status: str


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


def _remove_archive_uuid_suffix(filename: str) -> str:
    """
    Remove trailing short UUID before extension, e.g.:
    name_пакет_документов_a1b2c3d4.zip -> name_пакет_документов.zip
    """
    path = Path(filename)
    stem = path.stem
    if len(stem) > 9 and stem[-9] == "_" and all(c in "0123456789abcdef" for c in stem[-8:]):
        return f"{stem[:-9]}{path.suffix}"
    return filename


def _sanitize_archive_stem(name: str) -> str:
    """Build a safe archive stem from program name."""
    cleaned = SAFE_FILENAME_CHARS_RE.sub("_", name.strip()).strip("._")
    return cleaned or "package"


def _format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} Б"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.2f} КБ"
    return f"{num_bytes / (1024 * 1024):.2f} МБ"


def _detect_source_metadata(source_path: Path) -> dict[str, Any]:
    if is_archive_file(str(source_path)):
        tmp_dir = tempfile.mkdtemp()
        try:
            extract_archive(str(source_path), tmp_dir)
            code_files = [Path(p) for p in collect_code_files(tmp_dir)]
            if not code_files:
                return {
                    "language": "Не определён",
                    "source_size_bytes": source_path.stat().st_size,
                    "source_size_human": _format_size(source_path.stat().st_size),
                    "code_files": [],
                }

            ext_counter: Counter[str] = Counter()
            size_bytes = 0
            rel_files: list[str] = []
            for code_file in code_files:
                rel_files.append(str(code_file.relative_to(tmp_dir).as_posix()))
                size_bytes += code_file.stat().st_size
                ext = code_file.suffix.lower()
                if ext in LANGUAGE_BY_EXTENSION:
                    ext_counter[ext] += 1

            lang = "Не определён"
            if ext_counter:
                dominant_ext = ext_counter.most_common(1)[0][0]
                lang = LANGUAGE_BY_EXTENSION.get(dominant_ext, "Не определён")

            return {
                "language": lang,
                "source_size_bytes": size_bytes,
                "source_size_human": _format_size(size_bytes),
                "code_files": rel_files,
            }
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    file_size = source_path.stat().st_size
    ext = source_path.suffix.lower()
    language = LANGUAGE_BY_EXTENSION.get(ext, "Не определён")
    return {
        "language": language,
        "source_size_bytes": file_size,
        "source_size_human": _format_size(file_size),
        "code_files": [],
    }


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
    source_meta: dict[str, Any] | None = None
    if kind == "source":
        try:
            source_meta = await run_in_threadpool(lambda: _detect_source_metadata(dest))
            code_files = source_meta.get("code_files", [])
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Ошибка обработки исходника: {exc}")

    response: dict[str, Any] = {"filename": unique_name, "code_files": code_files}
    if source_meta:
        response.update(
            {
                "language": source_meta["language"],
                "source_size_bytes": source_meta["source_size_bytes"],
                "source_size_human": source_meta["source_size_human"],
            }
        )
    return response


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
# /api/generate + queued generation
# ---------------------------------------------------------------------------


def _validate_authors(authors: list[Author]) -> None:
    if not authors:
        raise HTTPException(status_code=400, detail="Необходимо указать хотя бы одного автора.")
    for idx, author in enumerate(authors):
        for field, (pattern, msg) in COMPILED_PATTERNS.items():
            value = getattr(author, field, "")
            if not pattern.fullmatch(value):
                raise HTTPException(
                    status_code=422,
                    detail=f"Автор {idx + 1}, поле '{field}': {msg}",
                )


def _render_referat_from_text(
    output_path: Path,
    *,
    name: str,
    referat_text: str,
    language: str,
    source_size_human: str,
) -> None:
    doc = DocxTemplate(str(TEMPLATES_DIR / "referat.docx"))
    doc.render(
        {
            "name": name,
            "text": referat_text.strip(),
            "language_programming": language,
            "mass_programm": source_size_human,
        }
    )
    doc.save(str(output_path))


def _generate_documents_sync(req: GenerateRequest) -> dict[str, Any]:
    _validate_authors(req.authors)
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="Название программы не может быть пустым.")

    source_path = _output_path(req.source_file)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail=f"Файл исходного кода не найден: {req.source_file}")

    source_meta = _detect_source_metadata(source_path)
    program_name = req.name.strip()

    referat_path: Path | None = None
    if req.referat_file:
        referat_path = _output_path(req.referat_file)
        if not referat_path.exists():
            raise HTTPException(status_code=404, detail=f"Файл реферата не найден: {req.referat_file}")

    with tempfile.TemporaryDirectory(prefix="patent_generate_") as temp_dir:
        work_dir = Path(temp_dir)
        extract_dir = work_dir / "source_extract"
        extract_dir.mkdir(exist_ok=True)

        if req.referat_text and req.referat_text.strip():
            referat_path = work_dir / "referat.docx"
            _render_referat_from_text(
                referat_path,
                name=program_name,
                referat_text=req.referat_text,
                language=source_meta["language"],
                source_size_human=source_meta["source_size_human"],
            )
        elif referat_path is None:
            raise HTTPException(
                status_code=400,
                detail="Нужно загрузить файл реферата или ввести текст реферата в редакторе.",
            )

        try:
            code, source_zip_entries = _prepare_source_payload(source_path, extract_dir)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        authors_dicts = [a.model_dump() for a in req.authors]
        fio_of_authors = build_fio_string(authors_dicts)
        quantity = len(req.authors)

        source_code_out = work_dir / "source-code.docx"
        doc = DocxTemplate(str(TEMPLATES_DIR / "source_code_template.docx"))
        doc.render({"name": program_name, "fio_of_authors": fio_of_authors, "code": code})
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

        _generate_docs(program_name, quantity, authors_dicts, nr, ns, work_dir)

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
        archive_stem = _sanitize_archive_stem(program_name)
        archive_path = OUTPUT_DIR / f"{archive_stem}_пакет_документов.zip"
        counter = 1
        while archive_path.exists():
            archive_path = OUTPUT_DIR / f"{archive_stem}_пакет_документов_{counter}.zip"
            counter += 1

        with zipfile.ZipFile(str(archive_path), "w") as zf:
            for filename in existing:
                zf.write(str(work_dir / filename), filename)

            referat_clean_name = _remove_uuid_prefix(referat_path.name)
            zf.write(str(referat_path), f"referat/{referat_clean_name}")

            for abs_path, arcname in source_zip_entries:
                zf.write(str(abs_path), arcname)

    response: dict[str, Any] = {
        "archive_filename": archive_path.name,
        "program_name": program_name,
        "language": source_meta["language"],
        "source_size_human": source_meta["source_size_human"],
    }
    if page_count_warning:
        response["warning"] = page_count_warning
    return response


@app.post("/api/generate")
async def generate(req: GenerateRequest) -> dict[str, Any]:
    return await run_in_threadpool(lambda: _generate_documents_sync(req))


def _job_key(job_id: str) -> str:
    return f"{REDIS_JOB_KEY_PREFIX}{job_id}"


def _get_redis_client() -> "redis.Redis":
    if not HAS_REDIS:
        raise RuntimeError("Пакет redis не установлен. Добавьте зависимость: redis>=5.0.0")
    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    client.ping()
    return client


def _set_job_redis(job_id: str, **values: Any) -> None:
    client = _get_redis_client()
    serialized: dict[str, str] = {}
    for key, value in values.items():
        if isinstance(value, (dict, list)):
            serialized[key] = json.dumps(value, ensure_ascii=False)
        elif value is None:
            serialized[key] = ""
        else:
            serialized[key] = str(value)
    if serialized:
        client.hset(_job_key(job_id), mapping=serialized)


def _get_job_redis(job_id: str) -> dict[str, Any] | None:
    client = _get_redis_client()
    job = client.hgetall(_job_key(job_id))
    return job or None


def _enqueue_redis_job(job_id: str) -> None:
    client = _get_redis_client()
    client.lpush(REDIS_QUEUE_KEY, job_id)


def _generation_worker() -> None:
    while True:
        job_id: str | None = None
        try:
            client = _get_redis_client()
            item = client.brpop(REDIS_QUEUE_KEY, timeout=5)
            if not item:
                continue
            _queue_key, job_id = item
            _set_job_redis(job_id, status="processing")
            job = _get_job_redis(job_id)
            if not job or "payload" not in job:
                _set_job_redis(job_id, status="failed", error="Не найден payload задачи в Redis.")
                continue

            payload = json.loads(job["payload"])
            req = GenerateRequest(**payload)
            result = _generate_documents_sync(req)
            _set_job_redis(job_id, status="completed", result=result)
        except Exception as exc:
            # Keep worker alive on transient Redis/processing errors.
            # If we have a job id in scope, mark it failed.
            try:
                if isinstance(job_id, str):
                    _set_job_redis(job_id, status="failed", error=str(exc))
            except Exception:
                pass
            time.sleep(1)


def _cleanup_output_once() -> None:
    cutoff_ts = time.time() - (OUTPUT_RETENTION_HOURS * 3600)
    for path in OUTPUT_DIR.iterdir():
        try:
            if path.is_file() and path.stat().st_mtime < cutoff_ts:
                path.unlink(missing_ok=True)
        except Exception:
            continue


def _cleanup_output_worker() -> None:
    while True:
        _cleanup_output_once()
        time.sleep(max(3600, OUTPUT_CLEANUP_INTERVAL_SECONDS))


@app.on_event("startup")
def _startup_worker() -> None:
    _cleanup_output_once()
    cleanup_thread = threading.Thread(
        target=_cleanup_output_worker,
        daemon=True,
        name="output-cleanup-worker",
    )
    cleanup_thread.start()

    if not HAS_REDIS:
        return
    worker = threading.Thread(target=_generation_worker, daemon=True, name="generation-worker-redis")
    worker.start()


@app.post("/api/generate-queued", response_model=GenerateQueuedResponse)
async def generate_queued(req: GenerateRequest) -> GenerateQueuedResponse:
    # Fast validation upfront for immediate feedback before queueing.
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="Название программы не может быть пустым.")
    _validate_authors(req.authors)
    source_path = _output_path(req.source_file)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail=f"Файл исходного кода не найден: {req.source_file}")
    if req.referat_file:
        referat_path = _output_path(req.referat_file)
        if not referat_path.exists():
            raise HTTPException(status_code=404, detail=f"Файл реферата не найден: {req.referat_file}")
    if not (req.referat_text and req.referat_text.strip()) and not req.referat_file:
        raise HTTPException(
            status_code=400,
            detail="Нужно загрузить файл реферата или ввести текст реферата в редакторе.",
        )

    try:
        _get_redis_client()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Очередь Redis недоступна: {exc}")

    job_id = uuid.uuid4().hex
    try:
        _set_job_redis(job_id, status="queued", payload=req.model_dump())
        _enqueue_redis_job(job_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Не удалось поставить задачу в очередь Redis: {exc}")
    return GenerateQueuedResponse(job_id=job_id, status="queued")


@app.get("/api/generate-status/{job_id}")
async def generate_status(job_id: str) -> dict[str, Any]:
    try:
        job = _get_job_redis(job_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Очередь Redis недоступна: {exc}")
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена.")
    response: dict[str, Any] = {"job_id": job_id, "status": job.get("status", "queued")}
    if "result" in job and job["result"]:
        try:
            response["result"] = json.loads(job["result"])
        except json.JSONDecodeError:
            response["result"] = job["result"]
    if "error" in job:
        response["error"] = job["error"]
    return response


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
    download_name = _remove_uuid_prefix(filename)
    download_name = _remove_archive_uuid_suffix(download_name)
    return FileResponse(
        path=str(target),
        filename=download_name,
        media_type="application/octet-stream",
    )
