import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { ingestApi } from '../api/client'
import { usePolling } from '../hooks/usePolling'
import ValidationReport from '../components/ValidationReport'

const TERMINAL_STATUSES = new Set(['ready', 'failed'])

const CloudUploadIcon = ({ size = 34, color = "#938575" }) => (
  <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242" />
    <path d="M12 12v9" />
    <path d="m16 16-4-4-4 4" />
  </svg>
)

const FileCheckIcon = ({ size = 34, color = "#938575" }) => (
  <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2v4a2 2 0 0 0 2 2h4" />
    <path d="M10 18H5a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9l5 5v2" />
    <path d="m16 22 2 2 4-4" />
  </svg>
)

function FileZone({ label, hint, file, onDrop }) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (files) => onDrop(files[0]),
    accept: { 'text/csv': ['.csv'], 'text/plain': ['.csv'] },
    multiple: false,
  })
  return (
    <div {...getRootProps()} className={`dropzone ${isDragActive ? 'active' : ''}`}>
      <input {...getInputProps()} />
      <div className="dropzone-icon" style={{ display: 'flex', justifyContent: 'center' }}>
        {file ? <FileCheckIcon /> : <CloudUploadIcon />}
      </div>
      <div className="dropzone-label">{label}</div>
      <div className="dropzone-hint">{hint}</div>
      {file && <div className="dropzone-file">✓ {file.name} ({(file.size / 1024).toFixed(1)} KB)</div>}
    </div>
  )
}

const STEPS = [
  { key: 'pending',       label: 'Queued',         desc: 'Files received, waiting for a worker.' },
  { key: 'validating',    label: 'Validating',      desc: '3-layer structural, schema & relational checks.' },
  { key: 'preprocessing', label: 'Preprocessing',   desc: 'Pruning singletons, normalising counts.' },
  { key: 'ready',         label: 'Ready',           desc: 'Data is validated and ready for analysis.' },
]

function stepIndex(status) {
  const i = STEPS.findIndex(s => s.key === status)
  return i === -1 ? 0 : i
}

// ── Shared Modal Overlay ─────────────────────────────────────────────────────
function ModalOverlay({ children }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(30, 25, 20, 0.45)',
      backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 24,
    }}>
      <div style={{
        background: '#fff', borderRadius: 16,
        boxShadow: '0 24px 64px rgba(0,0,0,0.18)',
        padding: '36px 32px', maxWidth: 460, width: '100%',
        fontFamily: 'Instrument Sans, sans-serif',
      }}>
        {children}
      </div>
    </div>
  )
}

export default function IngestPage() {
  const navigate = useNavigate()
  const [asvFile, setAsvFile]         = useState(null)
  const [taxFile, setTaxFile]         = useState(null)
  const [progress, setProgress]       = useState(0)
  const [job, setJob]                 = useState(null)
  const [readyJob, setReadyJob]       = useState(null)   // full-pass modal
  const [partialJob, setPartialJob]   = useState(null)   // partial-pass warning modal
  const [phantomProgress, setPhantomProgress] = useState(0)

  useEffect(() => {
    if (job) {
      const c = stepIndex(job.status)
      setPhantomProgress(prev => Math.max(prev, c * 33))
    }
  }, [job?.status])

  useEffect(() => {
    if (!job || TERMINAL_STATUSES.has(job.status)) return
    const interval = setInterval(() => {
      setPhantomProgress(prev => {
        const c = stepIndex(job.status)
        const maxForStep = Math.min(99, (c + 1) * 33)
        const increment = Math.random() > 0.4 ? 1 : 2
        return prev >= maxForStep ? maxForStep : prev + increment
      })
    }, 400)
    return () => clearInterval(interval)
  }, [job?.status])

  const [report, setReport]           = useState(null)
  const [error, setError]             = useState('')
  const [uploading, setUploading]     = useState(false)

  const poll = useCallback(async () => {
    if (!job?.job_id) return
    try {
      const { data } = await ingestApi.status(job.job_id)
      setJob(data)

      if (data.status === 'ready') {
        // Full success — show green confirmation modal
        setReadyJob({
          id: data.job_id, jobId: data.job_id,
          asvFileName: asvFile?.name ?? '',
          taxFileName: taxFile?.name ?? '',
          date: new Date().toISOString().slice(0, 10),
        })
      } else if (data.status === 'failed') {
        const r = await ingestApi.report(job.job_id)
        setReport(r.data)
        // If at least Structural + Schema passed, microbiome/classifier data exists —
        // offer partial report generation with an amber warning modal.
        const passed = new Set(r.data?.passed_layers ?? [])
        const hasEnough = passed.has('layer_1_structural') && passed.has('layer_2_schema')
        if (hasEnough) {
          setPartialJob({
            id: data.job_id, jobId: data.job_id,
            asvFileName: asvFile?.name ?? '',
            taxFileName: taxFile?.name ?? '',
            date: new Date().toISOString().slice(0, 10),
            passedLayers: [...passed],
          })
        }
      }
    } catch {}
  }, [job?.job_id, asvFile, taxFile])

  const { start: startPolling } = usePolling(poll, 3000, () => TERMINAL_STATUSES.has(job?.status))

  const submit = async () => {
    if (!asvFile || !taxFile) return

    if (!asvFile.name.toLowerCase().endsWith('.csv') || !taxFile.name.toLowerCase().endsWith('.csv')) {
      setError('Invalid file format. Please ensure both files are valid CSV (.csv) files.')
      return
    }

    setError('')
    setUploading(true)
    setProgress(0)
    try {
      const { data } = await ingestApi.upload(asvFile, taxFile, setProgress)
      setJob(data)
      startPolling()
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  const reset = () => {
    setAsvFile(null); setTaxFile(null); setJob(null)
    setReport(null); setError(''); setProgress(0)
    setReadyJob(null); setPartialJob(null)
    setPhantomProgress(0)
  }

  const goToFiles = (j) => navigate('/ingested-data', { state: { newJob: j } })

  const currentStep = job ? stepIndex(job.status) : -1

  return (
    <>
      <div className="page-header">
        <h2>Upload Data</h2>
        <p>Ingest paired feature/taxonomy tables</p>
        <hr className="divider" />
      </div>

      {!job && (
        <div className="card">
          <div className="card-title">Select Files</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
            <FileZone
              label="ASV Abundance Table"
              hint="CSV with ASV_ID + sample count columns"
              file={asvFile}
              onDrop={setAsvFile}
            />
            <FileZone
              label="Taxonomy Inventory"
              hint="CSV with ASV_ID, Kingdom, Phylum … Species"
              file={taxFile}
              onDrop={setTaxFile}
            />
          </div>
          {error && <div className="alert alert-error">{error}</div>}
          {uploading && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: 12, color: 'var(--text-muted)' }}>
                <span>Uploading…</span><span>{progress}%</span>
              </div>
              <div className="progress-track"><div className="progress-bar" style={{ width: `${progress}%` }} /></div>
            </div>
          )}
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              className="btn btn-primary"
              onClick={submit}
              disabled={!asvFile || !taxFile || uploading}
            >
              {uploading ? <><span className="spinner" /> Uploading…</> : 'Upload & Validate →'}
            </button>
          </div>
        </div>
      )}

      {job && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
            <div className="card-title" style={{ margin: 0 }}>Pipeline Progress</div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              {TERMINAL_STATUSES.has(job.status) && (
                <button className="btn btn-ghost" onClick={reset} style={{ padding: '8px 20px', fontSize: 13, fontFamily: 'Instrument Sans', fontWeight: 600 }}>New Upload</button>
              )}
            </div>
          </div>

          <div className="pipeline">
            {STEPS.map((step, i) => {
              const done   = i < currentStep || (step.key === 'ready' && job.status === 'ready')
              const active = i === currentStep && job.status !== 'failed'
              const failed = job.status === 'failed' && i === currentStep
              return (
                <div key={step.key} className="pipeline-step">
                  <div className={`step-dot ${done ? 'done' : active ? 'active' : failed ? 'failed' : ''}`}>
                    {done ? (
                      <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                    ) : active ? (
                      <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: '-0.5px' }}>{phantomProgress}%</span>
                    ) : i + 1}
                  </div>
                  <div className="step-body">
                    <div className="step-title">{step.label}</div>
                    <div className="step-desc">{active ? job.message : step.desc}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {report && <ValidationReport report={report} />}

      {/* ── Partial-pass warning modal (amber) ── */}
      {partialJob && !readyJob && (
        <ModalOverlay>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 20 }}>
            <div style={{ width: 52, height: 52, borderRadius: '50%', background: '#FAEEDA', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#BA7517" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
            </div>
          </div>
          <h3 style={{ fontSize: 18, fontWeight: 700, color: '#111', textAlign: 'center', marginBottom: 8 }}>
            Partial Data Available
          </h3>
          <p style={{ fontSize: 13.5, color: '#938575', textAlign: 'center', lineHeight: 1.6, marginBottom: 16 }}>
            Validation did not fully complete, but your files contain sufficient microbiome and
            classifier data to generate a descriptive and diagnostic report.
          </p>
          <div style={{ background: '#FAEEDA', border: '0.5px solid #E9C97A', borderRadius: 8, padding: '10px 14px', marginBottom: 20, fontSize: 12, color: '#6B4C10', lineHeight: 1.8 }}>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>Layers passed:</div>
            {partialJob.passedLayers.map(l => (
              <div key={l}>✓ {l.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</div>
            ))}
            <div style={{ marginTop: 6, color: '#9A6B1A' }}>Reports from partial data may have reduced accuracy.</div>
          </div>
          <div style={{ background: '#FAFAF8', border: '0.5px solid #E8E4DC', borderRadius: 8, padding: '10px 14px', marginBottom: 24, fontSize: 12, color: '#938575', lineHeight: 1.8 }}>
            <div>ASV: <span style={{ fontFamily: 'var(--mono)', color: '#555' }}>{partialJob.asvFileName}</span></div>
            <div>Taxonomy: <span style={{ fontFamily: 'var(--mono)', color: '#555' }}>{partialJob.taxFileName}</span></div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <button className="btn btn-primary"
              style={{ width: '100%', justifyContent: 'center', fontSize: 14, padding: '12px', background: '#BA7517', borderColor: '#BA7517' }}
              onClick={() => navigate(`/analysis/${partialJob.id}`, { state: { samples: [] } })}
            >
              Proceed with Partial Data →
            </button>
            <button className="btn btn-ghost"
              style={{ width: '100%', justifyContent: 'center', fontSize: 14, padding: '12px' }}
              onClick={() => setPartialJob(null)}
            >
              Dismiss
            </button>
          </div>
        </ModalOverlay>
      )}

      {/* ── Full-pass success modal (green) ── */}
      {readyJob && (
        <ModalOverlay>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 20 }}>
            <div style={{ width: 52, height: 52, borderRadius: '50%', background: '#E1F5EE', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#1D9E75" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
            </div>
          </div>
          <h3 style={{ fontSize: 18, fontWeight: 700, color: '#111', textAlign: 'center', marginBottom: 8 }}>
            Validation Passed
          </h3>
          <p style={{ fontSize: 13.5, color: '#938575', textAlign: 'center', lineHeight: 1.6, marginBottom: 28 }}>
            Your files have been validated and preprocessed successfully.
            Would you like to generate a descriptive and diagnostic report now?
          </p>
          <div style={{ background: '#FAFAF8', border: '0.5px solid #E8E4DC', borderRadius: 8, padding: '10px 14px', marginBottom: 24, fontSize: 12, color: '#938575', lineHeight: 1.8 }}>
            <div>ASV: <span style={{ fontFamily: 'var(--mono)', color: '#555' }}>{readyJob.asvFileName}</span></div>
            <div>Taxonomy: <span style={{ fontFamily: 'var(--mono)', color: '#555' }}>{readyJob.taxFileName}</span></div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <button className="btn btn-primary"
              style={{ width: '100%', justifyContent: 'center', fontSize: 14, padding: '12px' }}
              onClick={() => navigate(`/analysis/${readyJob.id}`, { state: { samples: [] } })}
            >
              Generate Report →
            </button>
            <button className="btn btn-ghost"
              style={{ width: '100%', justifyContent: 'center', fontSize: 14, padding: '12px' }}
              onClick={() => goToFiles(readyJob)}
            >
              Save to Files
            </button>
          </div>
        </ModalOverlay>
      )}
    </>
  )
}
