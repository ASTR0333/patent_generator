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
            className="flex-1 border-2 border-neutral-300 border-dashed rounded-2xl p-4 flex flex-col gap-1"
        >
            <Icon className="text-neutral-800 mb-1" size={24} />
            <span className="font-medium text-neutral-800">{label}</span>
            {hint && <div className="text-xs text-neutral-400">{hint}</div>}
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
