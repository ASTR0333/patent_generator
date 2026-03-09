import { useState } from 'react'
import axios from 'axios'
import { AuthorForm, EMPTY_AUTHOR, isAuthorValid } from './components/AuthorForm.jsx'
import { FileUpload } from './components/FileUpload.jsx'

const API = '/api'

const SOURCE_ACCEPT = [
  '.py','.js','.ts','.jsx','.tsx','.java','.c','.cpp','.h','.hpp',
  '.cs','.go','.rs','.rb','.php','.swift','.kt','.scala','.lua',
  '.sh','.bash','.sql','.html','.css','.xml','.json','.yaml','.yml',
  '.toml','.ini','.cfg','.dart','.ex','.hs','.erl','.clj','.groovy',
  '.asm','.bat','.ps1',
  '.zip','.tar','.gz','.tgz','.bz2','.rar','.7z',
].join(',')

export default function App() {
  const [programName, setProgramName] = useState('')
  const [authors, setAuthors] = useState([{ ...EMPTY_AUTHOR }])
  const [sourceFile, setSourceFile] = useState(null)   // { name, serverName }
  const [referatFile, setReferatFile] = useState(null) // { name, serverName }
  const [generatedFiles, setGeneratedFiles] = useState([])
  const [status, setStatus] = useState(null)  // { type: 'error'|'success'|'info', msg }
  const [loading, setLoading] = useState(false)

  // ── Author management ────────────────────────────────────────────────────
  const handleAuthorChange = (idx, field, value) => {
    setAuthors((prev) => prev.map((a, i) => (i === idx ? { ...a, [field]: value } : a)))
  }

  const addAuthor = () => setAuthors((prev) => [...prev, { ...EMPTY_AUTHOR }])

  const removeAuthor = (idx) => setAuthors((prev) => prev.filter((_, i) => i !== idx))

  // ── File upload helpers ──────────────────────────────────────────────────
  const uploadSource = async (file) => {
    setStatus({ type: 'info', msg: `Загрузка исходного кода: ${file.name}…` })
    try {
      const fd = new FormData()
      fd.append('file', file)
      const { data } = await axios.post(`${API}/upload-source`, fd)
      setSourceFile({ name: file.name, serverName: data.filename, codeFiles: data.code_files })
      const extra = data.code_files?.length
        ? `\nВ архиве найдено ${data.code_files.length} файл(ов) с кодом`
        : ''
      setStatus({ type: 'success', msg: `Файл исходного кода загружен.${extra}` })
    } catch (e) {
      setStatus({ type: 'error', msg: e.response?.data?.detail || e.message })
    }
  }

  const uploadReferat = async (file) => {
    setStatus({ type: 'info', msg: `Загрузка реферата: ${file.name}…` })
    try {
      const fd = new FormData()
      fd.append('file', file)
      const { data } = await axios.post(`${API}/upload-referat`, fd)
      setReferatFile({ name: file.name, serverName: data.filename })
      setStatus({ type: 'success', msg: 'Реферат загружен.' })
    } catch (e) {
      setStatus({ type: 'error', msg: e.response?.data?.detail || e.message })
    }
  }

  // ── Validation ───────────────────────────────────────────────────────────
  const canGenerate =
    programName.trim() &&
    authors.length > 0 &&
    authors.every(isAuthorValid) &&
    sourceFile?.serverName &&
    referatFile?.serverName

  // ── Generate ─────────────────────────────────────────────────────────────
  const handleGenerate = async () => {
    if (!canGenerate) return
    setLoading(true)
    setStatus({ type: 'info', msg: 'Генерация документов…' })
    try {
      const payload = {
        name: programName.trim(),
        authors,
        source_file: sourceFile.serverName,
        referat_file: referatFile.serverName,
      }
      const { data } = await axios.post(`${API}/generate`, payload)
      setGeneratedFiles(data.files)
      setStatus({ type: 'success', msg: `Готово! Сгенерировано ${data.files.length} файл(ов).` })
    } catch (e) {
      const detail = e.response?.data?.detail || e.message
      setStatus({ type: 'error', msg: detail })
    } finally {
      setLoading(false)
    }
  }

  // ── Download ─────────────────────────────────────────────────────────────
  const download = (filename) => {
    window.open(`${API}/download/${encodeURIComponent(filename)}`, '_blank')
  }

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="app">
      <div className="header">
        <h1>Patent Generator</h1>
        <p>Генератор патентной документации для программ ЭВМ</p>
      </div>

      {/* Program name */}
      <div className="card">
        <h2>Название программы</h2>
        <div className="field">
          <label htmlFor="progname">Название программы для ЭВМ *</label>
          <input
            id="progname"
            type="text"
            value={programName}
            onChange={(e) => setProgramName(e.target.value)}
            placeholder="Например: Система управления складом"
          />
        </div>
      </div>

      {/* Authors */}
      <div className="card">
        <div className="author-header">
          <h2 style={{ margin: 0 }}>Авторы</h2>
        </div>
        <div className="authors-list">
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
        <div className="add-author-row">
          <button className="btn-secondary" onClick={addAuthor}>
            + Добавить автора
          </button>
        </div>
      </div>

      {/* Files */}
      <div className="card">
        <h2>Файлы</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
          <FileUpload
            label="Файл исходного кода"
            accept={SOURCE_ACCEPT}
            uploadedName={sourceFile?.name}
            onUpload={uploadSource}
            hint="Поддерживаются: .py, .js, .java, .cpp, .go, и др. Также можно загрузить архив (.zip, .tar.gz, .rar, .7z)"
          />
          <FileUpload
            label="Реферат (.docx)"
            accept=".docx,.doc"
            uploadedName={referatFile?.name}
            onUpload={uploadReferat}
            hint="Файл реферата программы в формате .docx"
          />

          {/* Archive preview */}
          {sourceFile?.codeFiles?.length > 0 && (
            <div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
                Файлы с кодом в архиве:
              </div>
              <ul style={{ listStyle: 'disc', paddingLeft: '1.5rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                {sourceFile.codeFiles.map((f) => <li key={f}>{f}</li>)}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* Status */}
      {status && (
        <div className={`status-banner ${status.type}`}>
          {status.msg}
        </div>
      )}

      {/* Generate */}
      <div className="generate-row">
        <button
          className="btn-primary"
          onClick={handleGenerate}
          disabled={!canGenerate || loading}
          title={!canGenerate ? 'Заполните все поля и загрузите файлы' : ''}
        >
          {loading && <span className="spinner" />}
          {loading ? 'Генерация…' : 'Сгенерировать документы'}
        </button>
      </div>

      {/* Generated files */}
      {generatedFiles.length > 0 && (
        <div className="card" style={{ marginTop: '1.5rem' }}>
          <h2>Сгенерированные файлы</h2>
          <ul className="files-list">
            {generatedFiles.map((f) => (
              <li key={f}>
                <span>{f}</span>
                <button className="btn-success" onClick={() => download(f)}>
                  Скачать
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
