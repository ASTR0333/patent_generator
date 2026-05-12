export function FileUpload({
    label,
    accept,
    uploadedName,
    onUpload,
    hint,
    icon: Icon,
}) {
    return (
        <label
            className="glass-panel flex flex-1 flex-col gap-2 rounded-2xl border-2 border-dashed p-6 border-[var(--app-border-strong)] cursor-pointer transition-all hover:bg-[var(--app-surface-strong)] hover:border-[var(--app-tooltip)] group shadow-sm"
        >
            <div className="flex items-center gap-3">
                <div className="bg-[var(--app-surface-strong)] p-3 rounded-2xl text-[var(--app-icon)] group-hover:bg-[var(--app-tooltip)] group-hover:text-[var(--app-bg)] transition-colors shadow-sm">
                    <Icon size={28} />
                </div>
                <span className="font-extrabold tracking-tight text-lg text-[var(--app-text)]">{label}</span>
            </div>
            {hint && <div className="text-sm text-[var(--app-text-soft)] mt-1">{hint}</div>}
            <div className="file-upload-box mt-2 bg-[var(--app-surface)] rounded-xl p-3 border border-[var(--app-border)]">
                <span className={`file-name font-medium ${uploadedName ? "ok text-[var(--app-success)]" : "text-[var(--app-text-soft)]"}`}>
                    {uploadedName || "Нажмите, чтобы выбрать файл..."}
                </span>
                <input
                    type="file"
                    accept={accept}
                    className="sr-only"
                    onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) onUpload(file);
                        e.target.value = "";
                    }}
                />
            </div>
        </label>
    );
}
