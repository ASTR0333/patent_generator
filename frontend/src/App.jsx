import { useState } from "react";
import { RiCheckFill, RiFileAiFill, RiFileCodeLine, RiFileWordLine, RiUserAddFill, RiErrorWarningFill, RiDownload2Fill } from "@remixicon/react";
import axios from "axios";
import {
    AuthorForm,
    EMPTY_AUTHOR,
    isAuthorValid,
} from "./components/AuthorForm.jsx";
import { FileUpload } from "./components/FileUpload.jsx";

const API = "https://patent.ikb-mirea.ru/api";

const SOURCE_ACCEPT = [
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".scala",
    ".lua",
    ".sh",
    ".bash",
    ".sql",
    ".html",
    ".css",
    ".xml",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".dart",
    ".ex",
    ".hs",
    ".erl",
    ".clj",
    ".groovy",
    ".asm",
    ".bat",
    ".ps1",
    ".zip",
    ".tar",
    ".gz",
    ".tgz",
    ".bz2",
    ".rar",
    ".7z",
].join(",");

export default function App() {
    const [programName, setProgramName] = useState("");
    const [authors, setAuthors] = useState([{ ...EMPTY_AUTHOR }]);
    const [sourceFile, setSourceFile] = useState(null); // { name, serverName }
    const [referatFile, setReferatFile] = useState(null); // { name, serverName }
    const [generatedFiles, setGeneratedFiles] = useState({}); // { archive_filename, warning? }
    const [status, setStatus] = useState(null); // { type: 'error'|'success'|'info', msg }
    const [loading, setLoading] = useState(false);

    // ── Author management ────────────────────────────────────────────────────
    const handleAuthorChange = (idx, field, value) => {
        setAuthors((prev) =>
            prev.map((a, i) => (i === idx ? { ...a, [field]: value } : a)),
        );
    };

    const addAuthor = () =>
        setAuthors((prev) => [...prev, { ...EMPTY_AUTHOR }]);

    const removeAuthor = (idx) =>
        setAuthors((prev) => prev.filter((_, i) => i !== idx));

    // ── File upload helpers ──────────────────────────────────────────────────
    const uploadSource = async (file) => {
        setStatus({
            type: "info",
            msg: `Загрузка исходного кода: ${file.name}…`,
        });
        try {
            const fd = new FormData();
            fd.append("file", file);
            const { data } = await axios.post(`${API}/upload-source`, fd);
            setSourceFile({
                name: file.name,
                serverName: data.filename,
                codeFiles: data.code_files,
            });
            const extra = data.code_files?.length
                ? `\nВ архиве найдено ${data.code_files.length} файл(ов) с кодом`
                : "";
            setStatus({
                type: "success",
                msg: `Файл исходного кода загружен.${extra}`,
            });
        } catch (e) {
            setStatus({
                type: "error",
                msg: e.response?.data?.detail || e.message,
            });
        }
    };

    const uploadReferat = async (file) => {
        setStatus({ type: "info", msg: `Загрузка реферата: ${file.name}…` });
        try {
            const fd = new FormData();
            fd.append("file", file);
            const { data } = await axios.post(`${API}/upload-referat`, fd);
            setReferatFile({ name: file.name, serverName: data.filename });
            setStatus({ type: "success", msg: "Реферат загружен." });
        } catch (e) {
            setStatus({
                type: "error",
                msg: e.response?.data?.detail || e.message,
            });
        }
    };

    // ── Validation ───────────────────────────────────────────────────────────
    const canGenerate =
        programName.trim() &&
        authors.length > 0 &&
        authors.every(isAuthorValid) &&
        sourceFile?.serverName &&
        referatFile?.serverName;

    // ── Generate ─────────────────────────────────────────────────────────────
    const handleGenerate = async () => {
        if (!canGenerate) return;
        setLoading(true);
        setStatus({ type: "info", msg: "Генерация документов…" });
        try {
            const payload = {
                name: programName.trim(),
                authors,
                source_file: sourceFile.serverName,
                referat_file: referatFile.serverName,
            };
            const { data } = await axios.post(`${API}/generate`, payload);
            setGeneratedFiles(data);
            let msg = "Готово! Архив с документами создан.";
            if (data.warning) {
                msg += `\n⚠️ ${data.warning}`;
            }
            setStatus({ type: "success", msg });
        } catch (e) {
            const detail = e.response?.data?.detail || e.message;
            setStatus({ type: "error", msg: detail });
        } finally {
            setLoading(false);
        }
    };

    // ── Download ─────────────────────────────────────────────────────────────
    const download = (filename) => {
        window.open(
            `${API}/download/${encodeURIComponent(filename)}`,
            "_blank",
        );
    };

    const downloadArchive = () => {
        if (generatedFiles.archive_filename) {
            download(generatedFiles.archive_filename);
        }
    };

    // ── Render ───────────────────────────────────────────────────────────────
    return (
        <div className="mx-auto max-w-3xl flex flex-col gap-6 p-4 border-x border-neutral-100 min-h-screen">
            <div className="flex items-center gap-2">
                <RiFileAiFill size={12} />
                <h1 className="font-bold text-sm">Генератор патентной документации для программ ЭВМ</h1>
            </div>

            {/* Program name */}
            <div className="flex flex-col gap-3">
                <label
                    className="font-bold text-sm uppercase text-neutral-700"
                    htmlFor="progname"
                >
                    Название программы для ЭВМ *
                </label>
                <input
                    id="progname"
                    type="text"
                    value={programName}
                    onChange={(e) => setProgramName(e.target.value)}
                    placeholder="Программа для ЭВМ"
                    className="text-3xl outline-none placeholder-neutral-200"
                />
            </div>

            {/* Authors */}
            <div className="flex flex-col gap-3">
                <h3 className="font-bold text-sm uppercase text-neutral-700">
                    Авторы
                </h3>
                <div className="flex flex-col gap-3">
                    {authors.map((author, idx) => (
                        <AuthorForm
                            key={idx}
                            index={idx}
                            author={author}
                            onChange={handleAuthorChange}
                            onRemove={removeAuthor}
                            canRemove={authors.length > 1}
                        />
                    ))}
                </div>
                <button className="cursor-pointer bg-neutral-100 border-l-2 border-neutral-200 p-3 rounded-md outline-none focus:ring-2 ring-neutral-50 font-medium flex items-center gap-2" onClick={addAuthor}>
                    <RiUserAddFill size={16} />
                    Добавить автора
                </button>
            </div>

            {/* Files */}
            <div className="flex flex-col gap-3">
                <h3 className="font-bold text-sm uppercase text-neutral-700">
                    Файлы
                </h3>
                <div className="flex gap-3">
                    <FileUpload
                        label="Файл исходного кода *"
                        accept={SOURCE_ACCEPT}
                        uploadedName={sourceFile?.name}
                        onUpload={uploadSource}
                        hint="Поддерживаются: .py, .js, .java, .cpp, .go, и др. Также можно загрузить архив (.zip, .tar.gz, .rar, .7z)"
                        icon={RiFileCodeLine}
                    />
                    <FileUpload
                        label="Реферат *"
                        accept=".docx,.doc"
                        uploadedName={referatFile?.name}
                        onUpload={uploadReferat}
                        hint="Файл реферата программы в формате .docx"
                        icon={RiFileWordLine}
                    />
                </div>
                {/* Archive preview */}
                {sourceFile?.codeFiles?.length > 0 && (
                    <div className="flex flex-col gap-2 rounded-md pl-3 border-l-2 border-neutral-200 py-2">
                        <div className="font-bold text-xs">
                            Файлы с кодом в архиве:
                        </div>
                        {sourceFile.codeFiles.map((f) => (
                            <div className="flex items-center gap-1 text-neutral-900 font-medium text-sm px-2 py-1 bg-neutral-50 rounded-lg" key={f}>
                                <RiFileCodeLine size={14} />
                                {f}
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Status */}
            {status && (
                <div className={`flex items-center gap-1 text-sm ${status.type === "error" ? "text-red-900" : status.type === "success" ? "text-green-500" : "animate-pulse"}`}>
                    {status.type === "error" ? <RiErrorWarningFill size={14} /> : status.type === "success" ? <RiCheckFill size={14} /> : null}
                    {status.msg}
                </div>
            )}

            <button
                className={`cursor-pointer bg-neutral-100 outline-none ring-neutral-50 focus:ring-2 rounded-full p-4 font-medium flex items-center justify-center gap-2 ${loading ? "disabled:animate-pulse" : "disabled:opacity-25"}`}
                onClick={handleGenerate}
                disabled={!canGenerate || loading}
                title={
                    !canGenerate
                        ? "Заполните все поля и загрузите файлы"
                        : ""
                }
            >
                {loading && <div className="size-4 rounded-full border-2 border-transparent border-t-current animate-spin" />}
                {loading ? "Генерация…" : "Сгенерировать документы"}
            </button>

            {/* Generated files */}
            {generatedFiles.archive_filename && (
                <div className="flex flex-col gap-2 rounded-md pl-3 border-l-2 border-neutral-200 py-2">
                    <div className="font-bold text-xs">
                        Результат
                    </div>
                    <button onClick={downloadArchive} className="cursor-pointer flex items-center gap-1 text-neutral-900 font-medium text-sm px-2 py-1 bg-neutral-50 rounded-lg text-start">
                        <RiFileWordLine size={14} />
                        <span className="flex-1">
                            {generatedFiles.archive_filename}
                        </span>
                        <RiDownload2Fill size={14} />
                    </button>
                </div>
            )}
        </div>
    );
}
