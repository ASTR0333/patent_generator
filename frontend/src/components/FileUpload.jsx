import { useRef } from 'react'

export function FileUpload({ label, accept, uploadedName, onUpload, hint }) {
  const ref = useRef(null)

  return (
    <div className="field">
      <label>{label}</label>
      {hint && <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>{hint}</div>}
      <div className="file-upload-box">
        <button className="btn-secondary" onClick={() => ref.current?.click()}>
          Выбрать файл
        </button>
        <span className={`file-name ${uploadedName ? 'ok' : ''}`}>
          {uploadedName || 'Файл не выбран'}
        </span>
        <input
          ref={ref}
          type="file"
          accept={accept}
          style={{ display: 'none' }}
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) onUpload(file)
            e.target.value = ''
          }}
        />
      </div>
    </div>
  )
}
