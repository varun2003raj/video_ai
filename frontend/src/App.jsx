import { useMemo, useState } from 'react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

function App() {
  const [file, setFile] = useState(null)
  const [title, setTitle] = useState('')
  const [videoUrl, setVideoUrl] = useState('')
  const [jobId, setJobId] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [progress, setProgress] = useState(0)
  const [downloadName, setDownloadName] = useState('doc-video-converter')
  const [includeNarration, setIncludeNarration] = useState(true)

  const fileHint = useMemo(() => {
    if (!file) return 'PDF, DOCX, or TXT — max 20 MB'
    return `${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} MB`
  }, [file])

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (!file) {
      setMessage('Please choose a document first.')
      return
    }

    const formData = new FormData()
    formData.append('file', file)
    if (title.trim()) formData.append('title', title.trim())
    formData.append('narration', includeNarration ? 'true' : 'false')

    setBusy(true)
    setMessage('Generating video… this can take a few seconds.')
    setVideoUrl('')
    setJobId('')
    setProgress(12)
    const timer = setInterval(() => {
      setProgress((p) => (p < 90 ? p + Math.random() * 8 : p))
    }, 400)

    try {
      const response = await fetch(`${API_BASE}/convert/`, {
        method: 'POST',
        body: formData,
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data?.detail || 'Conversion failed')
      }

      const safeName = (title.trim() || 'doc-video-converter').replace(/[\\/:*?"<>|]+/g, '_')
      setDownloadName(safeName)
      setVideoUrl(data.video_url)
      setJobId(data.job_id)
      setMessage('Done! Preview below.')
      setProgress(100)
    } catch (error) {
      setMessage(error.message)
      setProgress(0)
    } finally {
      setBusy(false)
      clearInterval(timer)
    }
  }

  const handleDownload = async (url, name) => {
    try {
      const res = await fetch(url)
      if (!res.ok) throw new Error('Download failed')
      const blob = await res.blob()
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = `${name}.mp4`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(link.href)
    } catch (err) {
      setMessage(err.message)
    }
  }

  return (
    <main className="page">
      <header className="hero">
        <p className="eyebrow">Doc → Video</p>
        <h1>Convert documents into dynamic videos</h1>
        <p className="lede">
          Upload a PDF, DOCX, or TXT file and watch it transform into a video you can preview or download.
        </p>
      </header>

      <section className="panel">
        <form className="uploader" onSubmit={handleSubmit}>
          <label className="field">
            <span>Document</span>
            <div className="drop">
              <input
                type="file"
                accept=".pdf,.docx,.txt"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                disabled={busy}
              />
              <p>{fileHint}</p>
            </div>
          </label>

          <label className="field">
            <span>Title (optional)</span>
            <input
              type="text"
              placeholder="e.g. Project Title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={busy}
            />
          </label>

          <div className="actions">
            <label className="checkbox">
              <input
                type="checkbox"
                checked={includeNarration}
                onChange={(e) => setIncludeNarration(e.target.checked)}
                disabled={busy}
              />
              <span>Include voice narration</span>
            </label>
            <button type="submit" disabled={busy}>
              {busy ? 'Converting…' : 'Generate Video'}
            </button>
          </div>
        </form>

        {message && <p className="status">{message}</p>}
        {busy && (
          <div className="progress">
            <div className="progress-fill" style={{ width: `${Math.min(progress, 100)}%` }} />
          </div>
        )}

        {videoUrl && (
          <div className="preview">
            <div className="preview-header">
              <div>
                <p className="eyebrow">Preview</p>
                <h3>Generated MP4</h3>
              </div>
              <button className="ghost" type="button" onClick={() => handleDownload(videoUrl, downloadName)}>
                Download MP4
              </button>
            </div>
            <video controls src={videoUrl} />
          </div>
        )}
      </section>
    </main>
  )
}

export default App