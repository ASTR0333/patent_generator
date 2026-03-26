import { useEffect, useMemo, useState } from "react";
import {
    RiArrowLeftLine,
    RiArrowRightLine,
    RiCheckFill,
    RiDownload2Fill,
    RiErrorWarningFill,
    RiFileAiFill,
    RiFileCodeLine,
    RiFileWordLine,
    RiMoonClearLine,
    RiPlayFill,
    RiSunLine,
} from "@remixicon/react";
import axios from "axios";
import ReactQuill from "react-quill";
import "react-quill/dist/quill.snow.css";
import { AuthorForm, EMPTY_AUTHOR, isAuthorValid } from "./components/AuthorForm.jsx";
import { FileUpload } from "./components/FileUpload.jsx";

const API = import.meta.env.VITE_API_URL || "/api";

const SOURCE_ACCEPT = [
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h", ".hpp", ".cs",
    ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala", ".lua", ".sh", ".bash", ".sql",
    ".html", ".css", ".xml", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".dart", ".ex",
    ".hs", ".erl", ".clj", ".groovy", ".asm", ".bat", ".ps1", ".zip", ".tar", ".gz", ".tgz",
    ".bz2", ".rar", ".7z",
].join(",");

const THEME_KEY = "patent-generator-theme";
const WIZARD_KEY = "patent-generator-wizard-v3";

const STEP_WELCOME = 0;
const STEP_COUNT = 1;
const STEP_AUTHORS = 2;
const STEP_FILES = 3;
const STEPS = [
    { id: STEP_WELCOME, short: "1", title: "Старт" },
    { id: STEP_COUNT, short: "2", title: "Кол-во авторов" },
    { id: STEP_AUTHORS, short: "3", title: "Авторы" },
    { id: STEP_FILES, short: "4", title: "Файлы и реферат" },
];

const quillModules = {
    toolbar: [
        [{ header: [1, 2, 3, false] }],
        ["bold", "italic", "underline"],
        [{ color: [] }, { background: [] }],
        [{ list: "ordered" }, { list: "bullet" }],
        [{ align: [] }],
    ],
};

const quillFormats = ["header", "bold", "italic", "underline", "color", "background", "list", "bullet", "align"];

function htmlToPlainText(html) {
    if (!html) return "";
    const doc = new DOMParser().parseFromString(html, "text/html");
    return (doc.body.textContent || "").trim();
}

function prettyArchiveName(filename) {
    if (!filename) return "";
    return filename.replace(/_[0-9a-f]{8}(?=\.zip$)/i, "");
}

export default function App() {
    const [theme, setTheme] = useState(() => {
        if (typeof window === "undefined") return "light";
        const savedTheme = window.localStorage.getItem(THEME_KEY);
        if (savedTheme === "light" || savedTheme === "dark") return savedTheme;
        return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    });

    const [currentStep, setCurrentStep] = useState(STEP_WELCOME);
    const [authorCount, setAuthorCount] = useState(1);
    const [authorCountInput, setAuthorCountInput] = useState("1");
    const [programName, setProgramName] = useState("");
    const [authors, setAuthors] = useState([{ ...EMPTY_AUTHOR }]);
    const [sourceFile, setSourceFile] = useState(null);
    const [referatFile, setReferatFile] = useState(null);
    const [referatText, setReferatText] = useState("");
    const [generatedFiles, setGeneratedFiles] = useState({});
    const [status, setStatus] = useState(null);
    const [loading, setLoading] = useState(false);
    const [queueJobId, setQueueJobId] = useState(null);

    useEffect(() => {
        document.documentElement.dataset.theme = theme;
        window.localStorage.setItem(THEME_KEY, theme);
    }, [theme]);

    useEffect(() => {
        try {
            const raw = window.sessionStorage.getItem(WIZARD_KEY);
            if (!raw) return;
            const saved = JSON.parse(raw);
            if (typeof saved.currentStep === "number") setCurrentStep(saved.currentStep);
            if (typeof saved.authorCount === "number" && saved.authorCount > 0) setAuthorCount(saved.authorCount);
            if (typeof saved.authorCountInput === "string") {
                setAuthorCountInput(saved.authorCountInput);
            } else if (typeof saved.authorCount === "number" && saved.authorCount > 0) {
                setAuthorCountInput(String(saved.authorCount));
            }
            if (typeof saved.programName === "string") setProgramName(saved.programName);
            if (Array.isArray(saved.authors) && saved.authors.length > 0) setAuthors(saved.authors);
            if (saved.sourceFile) setSourceFile(saved.sourceFile);
            if (saved.referatFile) setReferatFile(saved.referatFile);
            if (typeof saved.referatText === "string") setReferatText(saved.referatText);
            if (saved.generatedFiles) setGeneratedFiles(saved.generatedFiles);
        } catch {
            // ignore broken session payload
        }
    }, []);

    useEffect(() => {
        const payload = {
            currentStep,
            authorCount,
            authorCountInput,
            programName,
            authors,
            sourceFile,
            referatFile,
            referatText,
            generatedFiles,
        };
        window.sessionStorage.setItem(WIZARD_KEY, JSON.stringify(payload));
    }, [currentStep, authorCount, authorCountInput, programName, authors, sourceFile, referatFile, referatText, generatedFiles]);

    useEffect(() => {
        setAuthors((prev) => {
            if (authorCount === prev.length) return prev;
            if (authorCount > prev.length) {
                return [...prev, ...Array.from({ length: authorCount - prev.length }, () => ({ ...EMPTY_AUTHOR }))];
            }
            return prev.slice(0, authorCount);
        });
    }, [authorCount]);

    useEffect(() => {
        if (!queueJobId) return undefined;

        let active = true;
        const timer = setInterval(async () => {
            try {
                const { data } = await axios.get(`${API}/generate-status/${queueJobId}`);
                if (!active) return;

                if (data.status === "completed") {
                    setGeneratedFiles(data.result || {});
                    setStatus({ type: "success", msg: "Готово! Архив с документами создан." });
                    setLoading(false);
                    setQueueJobId(null);
                } else if (data.status === "failed") {
                    setStatus({ type: "error", msg: data.error || "Ошибка генерации." });
                    setLoading(false);
                    setQueueJobId(null);
                } else if (data.status === "processing") {
                    setStatus({ type: "info", msg: "Генерация выполняется в очереди…" });
                }
            } catch (e) {
                if (!active) return;
                setStatus({ type: "error", msg: e.response?.data?.detail || e.message });
                setLoading(false);
                setQueueJobId(null);
            }
        }, 2000);

        return () => {
            active = false;
            clearInterval(timer);
        };
    }, [queueJobId]);

    const handleAuthorChange = (idx, field, value) => {
        setAuthors((prev) => prev.map((a, i) => (i === idx ? { ...a, [field]: value } : a)));
    };

    const uploadSource = async (file) => {
        setStatus({ type: "info", msg: `Загрузка исходного кода: ${file.name}…` });
        try {
            const fd = new FormData();
            fd.append("file", file);
            fd.append("kind", "source");
            const { data } = await axios.post(`${API}/upload`, fd);
            setSourceFile({
                name: file.name,
                serverName: data.filename,
                codeFiles: data.code_files || [],
                language: data.language || "Не определён",
                sourceSizeHuman: data.source_size_human || "0 Б",
            });
            setStatus({ type: "success", msg: "Исходник загружен и проанализирован." });
        } catch (e) {
            setStatus({ type: "error", msg: e.response?.data?.detail || e.message });
        }
    };

    const uploadReferat = async (file) => {
        setStatus({ type: "info", msg: `Загрузка файла реферата: ${file.name}…` });
        try {
            const fd = new FormData();
            fd.append("file", file);
            fd.append("kind", "referat");
            const { data } = await axios.post(`${API}/upload`, fd);
            setReferatFile({ name: file.name, serverName: data.filename });
            setStatus({ type: "success", msg: "Файл реферата загружен." });
        } catch (e) {
            setStatus({ type: "error", msg: e.response?.data?.detail || e.message });
        }
    };

    const referatTextPlain = useMemo(() => htmlToPlainText(referatText), [referatText]);

    const canGoNextFromCount = /^\d+$/.test(authorCountInput) && Number(authorCountInput) >= 1;
    const hasProgramName = Boolean(programName.trim());
    const canGoNextFromAuthors = hasProgramName && authors.length === authorCount && authors.every(isAuthorValid);
    const canGenerate =
        authors.length > 0 &&
        authors.every(isAuthorValid) &&
        sourceFile?.serverName &&
        (referatFile?.serverName || referatTextPlain.length > 0);
    const maxUnlockedStep = canGoNextFromAuthors ? STEP_FILES : canGoNextFromCount ? STEP_AUTHORS : STEP_COUNT;
    const canNavigateToStep = (step) => step <= maxUnlockedStep;

    const handleGenerate = async () => {
        if (!canGenerate) return;
        setLoading(true);
        setStatus({ type: "info", msg: "Ставлю задачу в очередь генерации…" });

        try {
            const payload = {
                name: programName.trim(),
                authors,
                source_file: sourceFile.serverName,
                referat_file: referatFile?.serverName || null,
                referat_text: referatTextPlain || null,
            };

            const { data } = await axios.post(`${API}/generate-queued`, payload);
            setQueueJobId(data.job_id);
            setStatus({ type: "info", msg: "Задача поставлена в очередь. Ожидайте завершения генерации…" });
        } catch (e) {
            setStatus({ type: "error", msg: e.response?.data?.detail || e.message });
            setLoading(false);
        }
    };

    const downloadArchive = () => {
        if (!generatedFiles.archive_filename) return;
        window.open(`${API}/download/${encodeURIComponent(generatedFiles.archive_filename)}`, "_blank");
    };

    return (
        <div className="mx-auto max-w-3xl flex min-h-screen flex-col gap-6 border-x p-4 bg-[var(--app-bg)] border-[var(--app-border)] text-[var(--app-text)] transition-colors">
            <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                    <RiFileAiFill size={14} className="text-[var(--app-icon)]" />
                    <h1 className="font-bold text-sm">Генератор патентной документации для программ ЭВМ</h1>
                </div>

                <button
                    type="button"
                    onClick={() => setTheme((v) => (v === "dark" ? "light" : "dark"))}
                    className="relative cursor-pointer rounded-full border px-1 py-1 w-20 h-10 outline-none transition-colors border-[var(--app-border-strong)] bg-[var(--app-surface)] focus:ring-2 ring-[var(--app-ring)]"
                    aria-label="Переключить тему"
                    title={theme === "dark" ? "Включена темная тема" : "Включена светлая тема"}
                >
                    <span className="absolute inset-0 flex items-center justify-between px-2 text-[var(--app-text-soft)]">
                        <RiSunLine size={14} />
                        <RiMoonClearLine size={14} />
                    </span>
                    <span
                        className={`absolute top-1 size-8 rounded-full transition-all bg-[var(--app-bg)] border border-[var(--app-border-strong)] ${theme === "dark" ? "left-11" : "left-1"}`}
                    />
                </button>
            </div>

            <div className="rounded-2xl border p-3 bg-[var(--app-surface)] border-[var(--app-border-strong)]">
                <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                    {STEPS.map((step) => {
                        const isActive = currentStep === step.id;
                        const isDone = currentStep > step.id;
                        const canClick = canNavigateToStep(step.id);

                        return (
                            <button
                                key={step.id}
                                type="button"
                                onClick={() => canClick && setCurrentStep(step.id)}
                                disabled={!canClick}
                                className={`text-left rounded-xl border px-3 py-2 transition cursor-pointer disabled:cursor-not-allowed ${
                                    isActive
                                        ? "border-[var(--app-border-strong)] bg-[var(--app-bg)]"
                                        : "border-[var(--app-border)] bg-transparent"
                                } ${!canClick ? "opacity-45" : ""}`}
                                title={canClick ? `Перейти: ${step.title}` : "Сначала заполните предыдущие шаги"}
                            >
                                <div className="flex items-center gap-2">
                                    <span
                                        className={`inline-flex size-6 items-center justify-center rounded-full text-xs font-bold border ${
                                            isDone
                                                ? "bg-[var(--app-success)] text-white border-[var(--app-success)]"
                                                : isActive
                                                  ? "bg-[var(--app-bg)] border-[var(--app-border-strong)]"
                                                  : "bg-transparent border-[var(--app-border)]"
                                        }`}
                                    >
                                        {isDone ? "✓" : step.short}
                                    </span>
                                    <span className={`text-xs font-bold uppercase ${isActive ? "text-[var(--app-text)]" : "text-[var(--app-text-muted)]"}`}>
                                        {step.title}
                                    </span>
                                </div>
                            </button>
                        );
                    })}
                </div>
            </div>

            {currentStep === STEP_WELCOME && (
                <section className="flex flex-col gap-4 rounded-2xl border p-5 bg-[var(--app-surface)] border-[var(--app-border-strong)]">
                    <h2 className="text-xl font-bold">Добро пожаловать</h2>
                    <p className="text-sm text-[var(--app-text-soft)]">
                        Сайт помогает собрать пакет патентной документации для программы ЭВМ. Вы пройдете по шагам: укажете авторов,
                        загрузите исходник, добавите реферат (файлом или через редактор) и получите готовый архив.
                    </p>
                    <button
                        type="button"
                        onClick={() => setCurrentStep(STEP_COUNT)}
                        className="cursor-pointer rounded-full p-4 font-medium flex items-center justify-center gap-2 bg-[var(--app-bg)] border border-[var(--app-border-strong)]"
                    >
                        <RiPlayFill size={16} />
                        Начать генерацию
                    </button>
                </section>
            )}

            {currentStep === STEP_COUNT && (
                <section className="flex flex-col gap-4 rounded-2xl border p-5 bg-[var(--app-surface)] border-[var(--app-border-strong)]">
                    <label className="font-bold text-sm uppercase text-[var(--app-text-muted)]" htmlFor="authorCount">
                        Количество авторов
                    </label>
                    <input
                        id="authorCount"
                        type="text"
                        inputMode="numeric"
                        pattern="[0-9]*"
                        value={authorCountInput}
                        onChange={(e) => {
                            const next = e.target.value;
                            if (!/^\d*$/.test(next)) return;
                            setAuthorCountInput(next);
                            if (next === "") return;
                            const parsed = Number.parseInt(next, 10);
                            if (Number.isFinite(parsed) && parsed >= 1) {
                                setAuthorCount(parsed);
                            }
                        }}
                        className="text-3xl outline-none text-[var(--app-text)] bg-transparent"
                    />
                    {!canGoNextFromCount && (
                        <div className="text-xs text-[var(--app-error)]">
                            Введите корректное количество авторов: целое число от 1.
                        </div>
                    )}
                    <div className="flex gap-3">
                        <button
                            type="button"
                            onClick={() => setCurrentStep(STEP_WELCOME)}
                            className="cursor-pointer rounded-full p-3 border border-[var(--app-border-strong)] flex items-center gap-2"
                        >
                            <RiArrowLeftLine size={14} />
                            Назад
                        </button>
                        <button
                            type="button"
                            onClick={() => setCurrentStep(STEP_AUTHORS)}
                            disabled={!canGoNextFromCount}
                            className="cursor-pointer rounded-full p-3 border border-[var(--app-border-strong)] flex items-center gap-2 disabled:opacity-40"
                        >
                            Далее
                            <RiArrowRightLine size={14} />
                        </button>
                    </div>
                </section>
            )}

            {currentStep === STEP_AUTHORS && (
                <section className="flex flex-col gap-4 rounded-2xl border p-5 bg-[var(--app-surface)] border-[var(--app-border-strong)]">
                    <h3 className="font-bold text-sm uppercase text-[var(--app-text-muted)]">Данные авторов</h3>
                    <div className="flex flex-col gap-2">
                        <label
                            className="font-bold text-xs uppercase text-[var(--app-text-muted)]"
                            htmlFor="program-name"
                        >
                            Наименование программы для ЭВМ *
                        </label>
                        <input
                            id="program-name"
                            type="text"
                            value={programName}
                            onChange={(e) => setProgramName(e.target.value)}
                            placeholder="Введите название программы"
                            className="rounded-lg border px-3 py-2 bg-[var(--app-bg)] text-[var(--app-text)] border-[var(--app-border-strong)] outline-none focus:ring-2 ring-[var(--app-ring)]"
                        />
                    </div>
                    <div className="flex flex-col gap-3">
                        {authors.map((author, idx) => (
                            <AuthorForm
                                key={idx}
                                index={idx}
                                author={author}
                                onChange={handleAuthorChange}
                                onRemove={() => {}}
                                canRemove={false}
                            />
                        ))}
                    </div>
                    <div className="flex gap-3">
                        <button
                            type="button"
                            onClick={() => setCurrentStep(STEP_COUNT)}
                            className="cursor-pointer rounded-full p-3 border border-[var(--app-border-strong)] flex items-center gap-2"
                        >
                            <RiArrowLeftLine size={14} />
                            Назад
                        </button>
                        <button
                            type="button"
                            onClick={() => setCurrentStep(STEP_FILES)}
                            disabled={!canGoNextFromAuthors}
                            className="cursor-pointer rounded-full p-3 border border-[var(--app-border-strong)] flex items-center gap-2 disabled:opacity-40"
                        >
                            Далее
                            <RiArrowRightLine size={14} />
                        </button>
                    </div>
                </section>
            )}

            {currentStep === STEP_FILES && (
                <section className="flex flex-col gap-4 rounded-2xl border p-5 bg-[var(--app-surface)] border-[var(--app-border-strong)]">
                    <h3 className="font-bold text-sm uppercase text-[var(--app-text-muted)]">Файлы и реферат</h3>

                    <div className="flex gap-3 max-md:flex-col">
                        <FileUpload
                            label="Файл исходного кода *"
                            accept={SOURCE_ACCEPT}
                            uploadedName={sourceFile?.name}
                            onUpload={uploadSource}
                            hint="Поддерживаются файлы кода и архивы"
                            icon={RiFileCodeLine}
                        />
                        <FileUpload
                            label="Файл реферата (опционально)"
                            accept=".docx,.doc"
                            uploadedName={referatFile?.name}
                            onUpload={uploadReferat}
                            hint="Можно загрузить готовый файл, либо написать текст ниже"
                            icon={RiFileWordLine}
                        />
                    </div>

                    <div className="rounded-xl border p-3 border-[var(--app-border-strong)] bg-[var(--app-bg)] flex flex-col gap-2 text-sm">
                        <div><b>Наименование программы:</b> {programName.trim() || "Введите название на шаге «Авторы»"}</div>
                        <div><b>Язык программирования:</b> {sourceFile?.language || "Будет определено автоматически"}</div>
                        <div><b>Вес исходника:</b> {sourceFile?.sourceSizeHuman || "Будет рассчитан автоматически"}</div>
                    </div>

                    <div className="flex flex-col gap-2">
                        <label className="font-bold text-sm uppercase text-[var(--app-text-muted)]">Текст реферата (редактор)</label>
                        <div className="rounded-xl border border-[var(--app-border-strong)] overflow-hidden bg-[var(--app-bg)] referat-editor-wrap">
                            <ReactQuill
                                className="referat-editor"
                                theme="snow"
                                value={referatText}
                                onChange={setReferatText}
                                modules={quillModules}
                                formats={quillFormats}
                                placeholder="Введите текст реферата..."
                            />
                        </div>
                        <div className="text-xs text-[var(--app-text-soft)]">
                            Если текст заполнен, бэкенд автоматически соберет `referat.docx` из шаблона.
                        </div>
                    </div>

                    {sourceFile?.codeFiles?.length > 0 && (
                        <div className="flex flex-col gap-2 rounded-md pl-3 border-l-2 py-2 border-[var(--app-border-strong)]">
                            <div className="font-bold text-xs">Файлы с кодом в архиве:</div>
                            {sourceFile.codeFiles.map((f) => (
                                <div
                                    className="flex items-center gap-1 rounded-lg px-2 py-1 font-medium text-sm bg-[var(--app-bg)] text-[var(--app-text)]"
                                    key={f}
                                >
                                    <RiFileCodeLine size={14} />
                                    {f}
                                </div>
                            ))}
                        </div>
                    )}

                    <div className="flex gap-3">
                        <button
                            type="button"
                            onClick={() => setCurrentStep(STEP_AUTHORS)}
                            className="cursor-pointer rounded-full p-3 border border-[var(--app-border-strong)] flex items-center gap-2"
                        >
                            <RiArrowLeftLine size={14} />
                            Назад
                        </button>
                        <button
                            className="cursor-pointer outline-none focus:ring-2 rounded-full p-3 font-medium flex items-center justify-center gap-2 bg-[var(--app-bg)] border border-[var(--app-border-strong)] ring-[var(--app-ring)] disabled:opacity-40"
                            onClick={handleGenerate}
                            disabled={!canGenerate || loading}
                            title={!canGenerate ? "Нужен исходник и реферат (файл или текст)" : ""}
                        >
                            {loading && <div className="size-4 rounded-full border-2 border-transparent border-t-current animate-spin" />}
                            {loading ? "В очереди..." : "Сгенерировать документы"}
                        </button>
                    </div>
                </section>
            )}

            {status && (
                <div className={`flex items-center gap-1 text-sm ${status.type === "error" ? "text-[var(--app-error)]" : status.type === "success" ? "text-[var(--app-success)]" : "animate-pulse text-[var(--app-text-muted)]"}`}>
                    {status.type === "error" ? <RiErrorWarningFill size={14} /> : status.type === "success" ? <RiCheckFill size={14} /> : null}
                    {status.msg}
                </div>
            )}

            {generatedFiles.archive_filename && (
                <div className="flex flex-col gap-2 rounded-md pl-3 border-l-2 py-2 border-[var(--app-border-strong)]">
                    <div className="font-bold text-xs">Результат</div>
                    <button onClick={downloadArchive} className="cursor-pointer flex items-center gap-1 rounded-lg px-2 py-1 text-start font-medium text-sm bg-[var(--app-surface)] text-[var(--app-text)]">
                        <RiFileWordLine size={14} />
                        <span className="flex-1">{prettyArchiveName(generatedFiles.archive_filename)}</span>
                        <RiDownload2Fill size={14} />
                    </button>
                </div>
            )}
        </div>
    );
}
