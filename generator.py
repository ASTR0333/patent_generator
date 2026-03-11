from docxtpl import DocxTemplate
import os
import re
import shutil
import tarfile
import tempfile
import zipfile
import subprocess
import time
import json

try:
    import rarfile
    HAS_RARFILE = True
except ImportError:
    HAS_RARFILE = False

try:
    import py7zr
    HAS_PY7ZR = True
except ImportError:
    HAS_PY7ZR = False

# pip install python-docx
# pip install docxtpl
# pip install rarfile (optional, for .rar support)
# pip install py7zr (optional, for .7z support)

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".kts", ".scala",
    ".lua", ".r", ".m", ".mm", ".pl", ".sh", ".bash", ".sql", ".html", ".css",
    ".scss", ".sass", ".less", ".xml", ".json", ".yaml", ".yml", ".toml",
    ".ini", ".cfg", ".md", ".dart", ".ex", ".exs", ".hs", ".erl", ".clj",
    ".groovy", ".v", ".sv", ".vhdl", ".asm", ".s", ".bat", ".ps1",
}

SPECIAL_FILENAMES= {"dockerfile", "makefile", "gemfile", "rakefile", "vagrantfile"}


def validate_input(prompt: str, pattern: str, error_message: str) -> str:
    while True:
        value = input(prompt).strip()
        if re.fullmatch(pattern, value):
            return value
        print(f"Ошибка: {error_message}")


def validate_positive_int(prompt: str) -> int:
    while True:
        value = input(prompt).strip()
        if value.isdigit() and int(value) > 0:
            return int(value)
        print("Ошибка: введите положительное целое число.")


def validate_file_exists(prompt: str, directory: str = "output") -> str:
    while True:
        filename = input(prompt).strip()
        filepath = os.path.join(directory, filename)
        if os.path.isfile(filepath):
            return filename
        print(f"Ошибка: файл '{filepath}' не найден.")


PATTERNS = {
    "fio": (
        r"[А-ЯЁа-яё]+ [А-ЯЁа-яё]+ [А-ЯЁа-яё]+",
        "ФИО должно быть в формате: Иванов Иван Иванович (кириллица, три слова)"
    ),
    "address": (
        r"\d{6},\s*.+",
        "Адрес должен быть в формате: 000000, Москва, …"
    ),
    "phone": (
        r"\+7\d{10}",
        "Телефон должен быть в формате: +7xxxxxxxxxx"
    ),
    "email": (
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
        "Email должен быть в формате: name@email.ru"
    ),
    "inn": (
        r"\d{12}",
        "ИНН должен содержать ровно 12 цифр"
    ),
    "passport": (
        r"\d{4}\s\d{6}\s.+\s\d{2}\.\d{2}\.\d{4}",
        "Формат: 0000 000000 ГУ МВД по Московской области 01.01.2000"
    ),
    "snils": (
        r"\d{11}",
        "СНИЛС должен содержать ровно 11 цифр"
    ),
    "birthday": (
        # Note: regex validates format only; calendar logic (e.g. Feb 31) is not checked.
        r"(0[1-9]|[12]\d|3[01])\.(0[1-9]|1[0-2])\.(19|20)\d{2}",
        "Дата рождения должна быть в формате: ДД.ММ.ГГГГ"
    ),
}


def is_code_file(filename: str) -> bool:
    """Return True if the file has a recognised source-code extension or name."""
    basename = os.path.basename(filename).lower()
    if basename in SPECIAL_FILENAMES:
        return True
    _, ext = os.path.splitext(basename)
    return ext in CODE_EXTENSIONS


def is_archive_file(filename: str) -> bool:
    """Return True if the file looks like a supported archive."""
    lower = filename.lower()
    return (
        lower.endswith(".zip")
        or lower.endswith(".tar")
        or lower.endswith(".tar.gz")
        or lower.endswith(".tgz")
        or lower.endswith(".tar.bz2")
        or lower.endswith(".rar")
        or lower.endswith(".7z")
    )


def extract_archive(archive_path: str, dest_dir: str) -> None:
    """Extract a supported archive to *dest_dir*."""
    lower = archive_path.lower()
    if lower.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(dest_dir)
    elif lower.endswith(".tar.gz") or lower.endswith(".tgz"):
        with tarfile.open(archive_path, "r:gz") as tf:
            tf.extractall(dest_dir)
    elif lower.endswith(".tar.bz2"):
        with tarfile.open(archive_path, "r:bz2") as tf:
            tf.extractall(dest_dir)
    elif lower.endswith(".tar"):
        with tarfile.open(archive_path, "r:") as tf:
            tf.extractall(dest_dir)
    elif lower.endswith(".rar"):
        if not HAS_RARFILE:
            raise RuntimeError("Пакет 'rarfile' не установлен. Выполните: pip install rarfile")
        with rarfile.RarFile(archive_path) as rf:
            rf.extractall(dest_dir)
    elif lower.endswith(".7z"):
        if not HAS_PY7ZR:
            raise RuntimeError("Пакет 'py7zr' не установлен. Выполните: pip install py7zr")
        with py7zr.SevenZipFile(archive_path, mode="r") as szf:
            szf.extractall(dest_dir)
    else:
        raise ValueError(f"Неподдерживаемый формат архива: {archive_path}")


def collect_code_files(directory: str) -> list[str]:
    """Recursively collect all code files inside *directory* (sorted)."""
    result = []
    for root, _dirs, files in os.walk(directory):
        for fname in sorted(files):
            full = os.path.join(root, fname)
            if is_code_file(full):
                result.append(full)
    return result


def read_code_from_path(path: str, output_dir: str = "output") -> str:
    """
    *path* can be:
    - a file name relative to *output_dir*
    - an absolute path to a code file or archive

    Returns the combined source-code text (multiple files separated by headers).
    """
    if os.path.isabs(path):
        full_path = path
    else:
        full_path = os.path.join(output_dir, path)

    if is_archive_file(full_path):
        tmp_dir = tempfile.mkdtemp()
        try:
            extract_archive(full_path, tmp_dir)
            code_files = collect_code_files(tmp_dir)
            if not code_files:
                raise ValueError("В архиве не найдено файлов с исходным кодом.")
            parts = []
            for cf in code_files:
                rel_name = os.path.relpath(cf, tmp_dir)
                try:
                    content = open(cf, "r", encoding="utf-8", errors="replace").read()
                except Exception:
                    content = open(cf, "r", encoding="latin-1", errors="replace").read()
                parts.append(f"// ===== {rel_name} =====\n{content}")
            return "\n\n".join(parts)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    if is_code_file(full_path):
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception:
            with open(full_path, "r", encoding="latin-1", errors="replace") as f:
                return f.read()

    raise ValueError(
        f"Файл '{full_path}' не является поддерживаемым файлом исходного кода или архивом."
    )


def count_pages_exact(filepath: str) -> int:
    filepath = os.path.abspath(filepath)
    
    # Create a temporary JSON file for output
    temp_output = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    temp_output_path = temp_output.name
    temp_output.close()
    
    try:
        # Create a temporary Python script for LibreOffice UNO
        temp_script = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False)
        script_path = temp_script.name
        
        script_content = f'''
import uno
from com.sun.star.beans import PropertyValue
import json
import sys

def get_page_count(doc_path):
    """Get page count from a document using LibreOffice UNO API"""
    try:
        local_context = uno.getComponentContext()
        resolver = local_context.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", local_context)
        
        ctx = resolver.resolve(
            "uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
        smgr = ctx.ServiceManager
        desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        
        url = uno.systemPathToFileUrl(doc_path)
        doc = desktop.loadComponentFromURL(url, "_blank", 0, ())
        
        pages = doc.getImplementation().getPageCount()
        
        doc.close(True)
        
        return pages
    except Exception as e:
        return {{"error": str(e)}}

result = get_page_count(r"{filepath}")
with open(r"{temp_output_path}", "w") as f:
    json.dump({{"pages": result}}, f)
'''
        
        temp_script.write(script_content)
        temp_script.close()
        
        # Start LibreOffice in headless mode with UNO socket listener
        lo_process = subprocess.Popen(
            ["libreoffice", "--headless", "--accept=socket,host=localhost,port=2002;urp;"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Wait for LibreOffice to start
        time.sleep(3)
        
        try:
            # Run the UNO script
            result = subprocess.run(
                ["python3", script_path],
                capture_output=True,
                timeout=30
            )
            
            # Read the result from JSON file
            if os.path.exists(temp_output_path):
                with open(temp_output_path, 'r') as f:
                    data = json.load(f)
                    if "pages" in data:
                        pages = data["pages"]
                        if isinstance(pages, int):
                            return pages
                        else:
                            raise RuntimeError(f"LibreOffice API error: {pages}")
            
            raise RuntimeError("Failed to get page count from LibreOffice")
        
        finally:
            lo_process.terminate()
            try:
                lo_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                lo_process.kill()
    
    finally:
        # Clean up temp files
        if os.path.exists(script_path):
            os.unlink(script_path)
        if os.path.exists(temp_output_path):
            os.unlink(temp_output_path)


def input_author(index: int) -> dict:
    return {
        "fio": validate_input(
            f"Введите ФИО {index + 1} автора (формат: Иванов Иван Иванович): ",
            *PATTERNS["fio"]
        ),
        "address": validate_input(
            f"Введите адрес {index + 1} автора (формат: 000000, Москва, …): ",
            *PATTERNS["address"]
        ),
        "phone": validate_input(
            f"Введите номер телефона {index + 1} автора (формат: +7xxxxxxxxxx): ",
            *PATTERNS["phone"]
        ),
        "email": validate_input(
            f"Введите почту {index + 1} автора (формат: name@email.ru): ",
            *PATTERNS["email"]
        ),
        "inn": validate_input(
            f"Введите ИНН {index + 1} автора (формат: 000000000000): ",
            *PATTERNS["inn"]
        ),
        "passport": validate_input(
            f"Введите серию и номер паспорта, дату выдачи и выдавший орган {index + 1} автора\n"
            f"  (формат: 0000 000000 ГУ МВД по Московской области 01.01.2000): ",
            *PATTERNS["passport"]
        ),
        "snils": validate_input(
            f"Введите СНИЛС {index + 1} автора (формат: 00000000000): ",
            *PATTERNS["snils"]
        ),
        "birthday": validate_input(
            f"Введите дату рождения {index + 1} автора (формат: 01.01.2000): ",
            *PATTERNS["birthday"]
        ),
        "skill": input(
            f"Введите краткое описание творческого вклада {index + 1} автора: "
        ).strip(),
    }


def build_fio_string(authors: list[dict]) -> str:
    return ", ".join(author["fio"] for author in authors)


def generate_source_code(name: str, fio_of_authors: str):
    supported_formats = (
        "*.py, *.js, *.ts, *.java, *.c, *.cpp, *.cs, *.go, *.rs, *.rb, *.php, и т.д.\n"
        "Также поддерживаются архивы: .zip, .tar, .tar.gz, .tgz, .tar.bz2, .rar, .7z"
    )
    code_name = validate_file_exists(
        f"Положите файл с исходным кодом (или архив) в папку output и напишите его название:\n"
        f"  Поддерживаемые форматы: {supported_formats}\n"
    )

    code = read_code_from_path(code_name)

    doc = DocxTemplate("templates/source_code_template.docx")
    context = {
        "name": name,
        "fio_of_authors": fio_of_authors,
        "code": code,
    }
    doc.render(context)
    doc.save("output/source-code.docx")


def generate_pril1_211_1(name: str, quantity_of_authors: int, authors: list[dict]):
    author1 = authors[0]

    passport_parts = author1["passport"].split(" ")
    passport_series_number = f"{passport_parts[0]} {passport_parts[1]}"

    day, month, year = author1["birthday"].split(".")

    file_ref = validate_file_exists(
        "Положите файл реферата в папку output и напишите его название (формат: name.docx):\n"
    )

    nr = str(count_pages_exact(f"output/{file_ref}"))
    ns = str(count_pages_exact("output/source-code.docx"))

    doc = DocxTemplate("templates/pril1-211-1-1.docx")
    context = {
        "name": name,
        "fio_author1": author1["fio"],
        "quantity_of_authors": quantity_of_authors,
        "adres_author1": author1["address"],
        "phone_author1": author1["phone"],
        "email_author1": author1["email"],
        "inn_author1": author1["inn"],
        "passport_author1": passport_series_number,
        "skils_author1": author1["snils"],
    }
    doc.render(context)
    doc.save("output/pril1-211-1-1.docx")

    doc = DocxTemplate("templates/pril1-211-1-2.docx")
    context = {
        "name": name,
        "fio_author1": author1["fio"],
        "q": quantity_of_authors,
        "adres_author1": author1["address"],
        "d_a1": day,
        "m_a1": month,
        "y_a1": year,
        "skill_author1": author1["skill"],
        "ns": ns,
        "nr": nr,
    }
    doc.render(context)
    doc.save("output/pril1-211-1-2.docx")


def generate_pril1_211_2(name: str, quantity_of_authors: int, authors: list[dict]):
    if quantity_of_authors < 2:
        return

    for idx in range(1, quantity_of_authors):
        author = authors[idx]
        
        passport_parts = author["passport"].split(" ")
        passport_series_number = f"{passport_parts[0]} {passport_parts[1]}"

        day, month, year = author["birthday"].split(".")

        doc = DocxTemplate("templates/pril1-211-2-1.docx")
        context = {
            "name": name,
            "fio_author": author["fio"],
            "quantity_of_authors": quantity_of_authors,
            "adres_author": author["address"],
            "passport_author": passport_series_number,
            "snils_author": author["snils"],
        }
        doc.render(context)
        doc.save(f"output/pril1-211-2-1_author{idx + 1}.docx")

        doc = DocxTemplate("templates/pril1-211-2-2.docx")
        context = {
            "name": name,
            "fio_author": author["fio"],
            "adres_author": author["address"],
            "d_a": day,
            "m_a": month,
            "y_a": year,
            "skill_author": author["skill"],
        }
        doc.render(context)
        doc.save(f"output/pril1-211-2-2_author{idx + 1}.docx")


def generate_pril3_211(name: str, authors: list[dict]):
    for idx, author in enumerate(authors):
        doc = DocxTemplate("templates/pril3_211.docx")
        context = {
            "name": name,
            "fio_author": author["fio"],
            "adres_author": author["address"],
            "passport_author_fully": author["passport"],
        }
        doc.render(context)
        if len(authors) == 1:
            doc.save("output/pril3_211.docx")
        else:
            doc.save(f"output/pril3_211_author{idx + 1}.docx")


def generate_pril4_211(name: str, authors: list[dict]):
    for idx, author in enumerate(authors):
        day, month, year = author["birthday"].split(".")

        doc = DocxTemplate("templates/pril4_211 .docx")
        context = {
            "name": name,
            "fio_author": author["fio"],
            "adres_author": author["address"],
            "d_a": day,
            "m_a": month,
            "y_a": year,
        }
        doc.render(context)
        if len(authors) == 1:
            doc.save("output/pril4_211.docx")
        else:
            doc.save(f"output/pril4_211_author{idx + 1}.docx")


def main():
    name = input("Введите название программы для ЭВМ: ").strip()
    if not name:
        print("Ошибка: название программы не может быть пустым.")
        return

    quantity_of_authors = validate_positive_int("Введите количество авторов: ")
    authors = [input_author(i) for i in range(quantity_of_authors)]
    fio_of_authors = build_fio_string(authors)

    generate_source_code(name, fio_of_authors)
    generate_pril1_211_1(name, quantity_of_authors, authors)
    generate_pril1_211_2(name, quantity_of_authors, authors)
    generate_pril3_211(name, authors)
    generate_pril4_211(name, authors)


if __name__ == "__main__":
    main()