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
            className="flex flex-1 flex-col gap-1 rounded-2xl border-2 border-dashed p-4 bg-[var(--app-bg)] border-[var(--app-border-strong)]"
        >
            <Icon className="mb-1 text-[var(--app-icon)]" size={24} />
            <span className="font-medium text-[var(--app-text)]">{label}</span>
            {hint && <div className="text-xs text-[var(--app-text-soft)]">{hint}</div>}
            <div className="file-upload-box">
                <span className={`file-name ${uploadedName ? "ok" : ""}`}>
                    {uploadedName || ""}
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
