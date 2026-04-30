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
    RiSettings3Line,
    RiCloseLine,
    RiLayoutColumnLine,
    RiLayoutRowLine
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
const TABS_KEY = "patent-generator-tabs";
const ACCENT_KEY = "patent-generator-accent";
const WIZARD_KEY = "patent-generator-wizard-v3";

const ACCENT_COLORS = [
    { name: "Синий", value: "#3b82f6" },
    { name: "Изумрудный", value: "#10b981" },
    { name: "Фиолетовый", value: "#8b5cf6" },
    { name: "Розовый", value: "#f43f5e" },
    { name: "Оранжевый", value: "#f97316" },
    { name: "Бирюзовый", value: "#14b8a6" },
    { name: "Серый", value: "#64748b" },
    { name: "Черный", value: "#0f172a" },
];

const STEP_WELCOME = 0;
const STEP_COUNT = 1;
const STEP_AUTHORS = 2;
const STEP_FILES = 3;
const STEPS = [
    { id: STEP_WELCOME, short: "1", title: "Старт" },
    { id: STEP_COUNT, short: "2", title: "Кол-во авторов" },
    { id: STEP_AUTHORS, short: "3", title: "Авторы" },
    { id: STEP_FILES, short: "4", title: "Файлы" },
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

    const [accent, setAccent] = useState(() => {
        if (typeof window === "undefined") return "#3b82f6";
        return window.localStorage.getItem(ACCENT_KEY) || "#3b82f6";
    });

    const [tabsLayout, setTabsLayout] = useState(() => {
        if (typeof window === "undefined") return "horizontal";
        return window.localStorage.getItem(TABS_KEY) || "horizontal";
    });

    const [showSettings, setShowSettings] = useState(false);

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
        document.documentElement.style.setProperty('--app-accent', accent);
        window.localStorage.setItem(ACCENT_KEY, accent);
    }, [accent]);

    useEffect(() => {
        window.localStorage.setItem(TABS_KEY, tabsLayout);
    }, [tabsLayout]);

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
        <div className="mx-auto w-full min-h-screen flex flex-col gap-6 p-4 md:p-8 text-[var(--app-text)] transition-colors relative">
            <header className="glass-panel flex items-center justify-between gap-3 rounded-3xl p-4 md:px-6 z-10">
                <div className="flex items-center gap-4">
                    <div className="glass-panel p-2.5 rounded-2xl shadow-lg">
                        <RiFileAiFill size={28} className="text-[var(--app-text)]" />
                    </div>
                    <h1 className="font-extrabold tracking-tight text-xl md:text-2xl text-[var(--app-text)]">
                        Генератор патентной документации
                    </h1>
                </div>

                <button
                    onClick={() => setShowSettings(true)}
                    className="glass-button p-2.5 rounded-xl outline-none focus:ring-2 ring-[var(--app-ring)] text-[var(--app-icon)]"
                    aria-label="Настройки"
                    title="Настройки интерфейса"
                >
                    <RiSettings3Line size={22} />
                </button>
            </header>

            <div className={`flex flex-1 ${tabsLayout === "vertical" ? "flex-col md:flex-row" : "flex-col"} gap-6`}>
                <nav className={`glass-panel rounded-3xl p-3 z-10 ${tabsLayout === "vertical" ? "md:w-72 shrink-0 h-fit sticky top-8" : ""}`}>
                    <div className={tabsLayout === "horizontal" ? "grid grid-cols-2 md:grid-cols-4 gap-3" : "flex flex-col gap-3"}>
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
                                    className={`text-left rounded-2xl border px-4 py-3 transition-all cursor-pointer disabled:cursor-not-allowed ${
                                        isActive
                                            ? "border-[var(--app-ring)] bg-[var(--app-surface-strong)] shadow-md transform scale-[1.02]"
                                            : "border-transparent bg-transparent hover:bg-[var(--app-surface)]"
                                    } ${!canClick ? "opacity-40" : ""}`}
                                    title={canClick ? `Перейти: ${step.title}` : "Сначала заполните предыдущие шаги"}
                                >
                                    <div className="flex items-center gap-3">
                                        <span
                                            className={`inline-flex size-8 items-center justify-center rounded-xl text-sm font-bold shadow-sm transition-colors ${
                                                isActive || isDone
                                                    ? "bg-[var(--app-text)] text-[var(--app-bg)]"
                                                    : "glass-button text-[var(--app-text)]"
                                            }`}
                                        >
                                            {isDone ? <RiCheckFill size={18} /> : step.short}
                                        </span>
                                        <span className={`text-sm font-bold uppercase tracking-wide ${isActive ? "text-[var(--app-text)]" : "text-[var(--app-text-soft)]"}`}>
                                            {step.title}
                                        </span>
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                </nav>

                <main className="flex-1 flex flex-col gap-6 w-full max-w-5xl mx-auto z-10">
                    {currentStep === STEP_WELCOME && (
                        <section className="glass-panel flex flex-col gap-6 rounded-3xl p-8">
                            <div className="flex flex-col gap-2">
                                <h2 className="text-3xl font-extrabold tracking-tight">Добро пожаловать</h2>
                                <p className="text-[var(--app-text-soft)] text-lg">
                                    Сайт помогает собрать пакет патентной документации для программы ЭВМ. Вы пройдете по шагам: укажете авторов,
                                    загрузите исходник, добавите реферат (файлом или через редактор) и получите готовый архив.
                                </p>
                            </div>
                            <button
                                type="button"
                                onClick={() => setCurrentStep(STEP_COUNT)}
                                className="glass-button cursor-pointer rounded-2xl p-4 font-bold text-lg flex items-center justify-center gap-2 self-start px-8 shadow-lg hover:shadow-xl hover:scale-[1.02] transition-all"
                            >
                                <RiPlayFill size={24} />
                                Начать генерацию
                            </button>
                        </section>
                    )}

                    {currentStep === STEP_COUNT && (
                        <section className="glass-panel flex flex-col gap-6 rounded-3xl p-8">
                            <label className="font-extrabold text-sm uppercase tracking-wider text-[var(--app-text-soft)]" htmlFor="authorCount">
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
                                className="glass-input text-5xl font-black rounded-2xl px-6 py-4 w-full max-w-xs text-[var(--app-text)]"
                            />
                            {!canGoNextFromCount && (
                                <div className="text-sm font-medium text-[var(--app-error)] flex items-center gap-1 bg-[var(--app-error-ring)] p-3 rounded-xl w-fit">
                                    <RiErrorWarningFill size={16} />
                                    Введите корректное количество авторов: целое число от 1.
                                </div>
                            )}
                            <div className="flex gap-4 mt-4">
                                <button
                                    type="button"
                                    onClick={() => setCurrentStep(STEP_WELCOME)}
                                    className="glass-button cursor-pointer rounded-2xl px-6 py-3 font-semibold flex items-center gap-2"
                                >
                                    <RiArrowLeftLine size={18} />
                                    Назад
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setCurrentStep(STEP_AUTHORS)}
                                    disabled={!canGoNextFromCount}
                                    className="glass-button cursor-pointer rounded-2xl px-6 py-3 font-semibold flex items-center gap-2 disabled:opacity-40"
                                >
                                    Далее
                                    <RiArrowRightLine size={18} />
                                </button>
                            </div>
                        </section>
                    )}

                    {currentStep === STEP_AUTHORS && (
                        <section className="glass-panel flex flex-col gap-6 rounded-3xl p-8">
                            <h3 className="font-extrabold text-sm uppercase tracking-wider text-[var(--app-text-soft)]">Данные авторов</h3>
                            <div className="flex flex-col gap-3">
                                <label
                                    className="font-extrabold text-xs uppercase tracking-wider text-[var(--app-text-soft)]"
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
                                    className="glass-input rounded-2xl text-lg font-medium px-5 py-4 w-full text-[var(--app-text)]"
                                />
                            </div>
                            <div className="flex flex-col gap-6 mt-2">
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
                            <div className="flex gap-4 mt-4">
                                <button
                                    type="button"
                                    onClick={() => setCurrentStep(STEP_COUNT)}
                                    className="glass-button cursor-pointer rounded-2xl px-6 py-3 font-semibold flex items-center gap-2"
                                >
                                    <RiArrowLeftLine size={18} />
                                    Назад
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setCurrentStep(STEP_FILES)}
                                    disabled={!canGoNextFromAuthors}
                                    className="glass-button cursor-pointer rounded-2xl px-6 py-3 font-semibold flex items-center gap-2 disabled:opacity-40"
                                >
                                    Далее
                                    <RiArrowRightLine size={18} />
                                </button>
                            </div>
                        </section>
                    )}

                    {currentStep === STEP_FILES && (
                        <section className="glass-panel flex flex-col gap-6 rounded-3xl p-8">
                            <h3 className="font-extrabold text-sm uppercase tracking-wider text-[var(--app-text-soft)]">Файлы и реферат</h3>

                            <div className="flex gap-4 max-md:flex-col">
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
                                    hint="Загрузите готовый файл или напишите текст ниже"
                                    icon={RiFileWordLine}
                                />
                            </div>

                            <div className="glass-input rounded-2xl p-5 flex flex-col gap-3 text-sm">
                                <div className="flex justify-between border-b border-[var(--app-border)] pb-2">
                                    <span className="text-[var(--app-text-soft)]">Наименование:</span>
                                    <span className="font-semibold">{programName.trim() || "Не указано"}</span>
                                </div>
                                <div className="flex justify-between border-b border-[var(--app-border)] pb-2">
                                    <span className="text-[var(--app-text-soft)]">Язык:</span>
                                    <span className="font-semibold">{sourceFile?.language || "Автоопределение"}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-[var(--app-text-soft)]">Размер:</span>
                                    <span className="font-semibold">{sourceFile?.sourceSizeHuman || "0 Б"}</span>
                                </div>
                            </div>

                            <div className="flex flex-col gap-3">
                                <label className="font-extrabold text-sm uppercase tracking-wider text-[var(--app-text-soft)]">
                                    Текст реферата (редактор)
                                </label>
                                <div className="glass-input rounded-2xl overflow-hidden referat-editor-wrap">
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
                            </div>

                            {sourceFile?.codeFiles?.length > 0 && (
                                <div className="flex flex-col gap-3 rounded-2xl p-5 bg-[var(--app-surface-strong)] border border-[var(--app-border)]">
                                    <div className="font-extrabold text-xs uppercase tracking-wider text-[var(--app-text-soft)]">Файлы с кодом в архиве:</div>
                                    <div className="flex flex-wrap gap-2">
                                        {sourceFile.codeFiles.map((f) => (
                                            <div
                                                className="flex items-center gap-1.5 rounded-xl px-3 py-1.5 font-medium text-sm glass-button shadow-none"
                                                key={f}
                                            >
                                                <RiFileCodeLine size={16} />
                                                {f}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            <div className="flex gap-4 mt-4">
                                <button
                                    type="button"
                                    onClick={() => setCurrentStep(STEP_AUTHORS)}
                                    className="glass-button cursor-pointer rounded-2xl px-6 py-3 font-semibold flex items-center gap-2"
                                >
                                    <RiArrowLeftLine size={18} />
                                    Назад
                                </button>
                                <button
                                    className="glass-button cursor-pointer outline-none focus:ring-2 rounded-2xl px-8 py-3 font-bold text-lg flex items-center justify-center gap-2 shadow-lg hover:shadow-xl hover:scale-[1.02] transition-all disabled:opacity-50 disabled:scale-100 disabled:shadow-none"
                                    onClick={handleGenerate}
                                    disabled={!canGenerate || loading}
                                    title={!canGenerate ? "Нужен исходник и реферат (файл или текст)" : ""}
                                >
                                    {loading && <div className="size-5 rounded-full border-2 border-[var(--app-text)]/30 border-t-[var(--app-text)] animate-spin" />}
                                    {loading ? "В очереди..." : "Сгенерировать документы"}
                                </button>
                            </div>
                        </section>
                    )}

                    {status && (
                        <div className={`glass-panel p-4 rounded-2xl font-medium flex items-center gap-3 text-sm ${status.type === "error" ? "text-[var(--app-error)] border-[var(--app-error-border)] bg-[var(--app-error-ring)]" : status.type === "success" ? "text-[var(--app-success)] border-[var(--app-success)]" : "text-[var(--app-tooltip)]"}`}>
                            {status.type === "error" ? <RiErrorWarningFill size={20} /> : status.type === "success" ? <RiCheckFill size={20} /> : null}
                            {status.msg}
                        </div>
                    )}

                    {generatedFiles.archive_filename && (
                        <div className="glass-panel p-6 rounded-3xl flex flex-col gap-4 border-[var(--app-success)]">
                            <div className="font-extrabold text-sm uppercase tracking-wider text-[var(--app-success)] flex items-center gap-2">
                                <RiCheckFill size={18} />
                                Документы готовы
                            </div>
                            <button onClick={downloadArchive} className="glass-button cursor-pointer flex items-center gap-3 rounded-2xl p-4 text-start font-bold text-lg hover:bg-[var(--app-surface)] transition-all group">
                                <div className="glass-panel p-2 rounded-xl group-hover:bg-white/20 transition-colors">
                                    <RiFileWordLine size={24} />
                                </div>
                                <span className="flex-1">{prettyArchiveName(generatedFiles.archive_filename)}</span>
                                <RiDownload2Fill size={24} />
                            </button>
                        </div>
                    )}
                </main>
            </div>

            {showSettings && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/20 backdrop-blur-sm transition-opacity">
                    <div className="glass-panel w-full max-w-md rounded-[2rem] p-8 flex flex-col gap-8 relative shadow-2xl animate-in fade-in zoom-in duration-200">
                        <button
                            onClick={() => setShowSettings(false)}
                            className="absolute top-6 right-6 p-2 rounded-full glass-button text-[var(--app-text-soft)] hover:text-[var(--app-text)] transition-colors"
                        >
                            <RiCloseLine size={24} />
                        </button>
                        
                        <div className="flex items-center gap-3 text-xl font-bold">
                            <RiSettings3Line size={28} />
                            Настройки
                        </div>
                        
                        <div className="flex flex-col gap-6">
                            <div className="flex items-center justify-between glass-input p-4 rounded-2xl">
                                <span className="font-semibold text-lg">Тема оформления</span>
                                <button
                                    type="button"
                                    onClick={() => setTheme((v) => (v === "dark" ? "light" : "dark"))}
                                    className="glass-button relative cursor-pointer rounded-full w-16 h-10 outline-none transition-colors"
                                >
                                    <span className="absolute inset-0 flex items-center justify-between px-2.5 text-[var(--app-text-soft)]">
                                        <RiSunLine size={16} />
                                        <RiMoonClearLine size={16} />
                                    </span>
                                    <span
                                        className={`absolute top-1 left-1 size-8 rounded-full transition-transform duration-300 bg-[var(--app-text)] shadow-md ${theme === "dark" ? "translate-x-6" : "translate-x-0"}`}
                                    />
                                </button>
                            </div>
                            
                            <div className="flex flex-col gap-3 glass-input p-4 rounded-2xl">
                                <span className="font-semibold text-lg">Цвет акцента</span>
                                <div className="flex flex-wrap gap-3 mt-1">
                                    {ACCENT_COLORS.map(c => (
                                        <button
                                            key={c.value}
                                            onClick={() => setAccent(c.value)}
                                            className={`size-8 rounded-full shadow-md transition-all border-2 ${accent === c.value ? "scale-125 border-[var(--app-text)]" : "border-transparent hover:scale-110"}`}
                                            style={{ backgroundColor: c.value }}
                                            title={c.name}
                                        />
                                    ))}
                                </div>
                            </div>
                            
                            <div className="flex items-center justify-between glass-input p-4 rounded-2xl">
                                <span className="font-semibold text-lg">Вкладки</span>
                                <div className="flex bg-[var(--app-surface-strong)] rounded-xl p-1.5 border border-[var(--app-border)] shadow-inner">
                                    <button
                                        onClick={() => setTabsLayout("horizontal")}
                                        className={`p-2.5 rounded-lg transition-all ${tabsLayout === "horizontal" ? "bg-[var(--app-bg)] shadow-md text-[var(--app-text)]" : "text-[var(--app-text-soft)] hover:text-[var(--app-text)]"}`}
                                        title="Горизонтально"
                                    >
                                        <RiLayoutRowLine size={20} />
                                    </button>
                                    <button
                                        onClick={() => setTabsLayout("vertical")}
                                        className={`p-2.5 rounded-lg transition-all ${tabsLayout === "vertical" ? "bg-[var(--app-bg)] shadow-md text-[var(--app-text)]" : "text-[var(--app-text-soft)] hover:text-[var(--app-text)]"}`}
                                        title="Вертикально"
                                    >
                                        <RiLayoutColumnLine size={20} />
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
