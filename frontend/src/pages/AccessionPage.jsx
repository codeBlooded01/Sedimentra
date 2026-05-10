import { useState, useCallback } from 'react'
import { accessionApi } from '../api/client'
import { usePolling } from '../hooks/usePolling'
import ValidationReport from '../components/ValidationReport'

const TERMINAL_PREVIEW  = new Set(['awaiting_confirmation', 'failed', 'cancelled'])
const TERMINAL_PIPELINE = new Set(['ready', 'failed', 'cancelled'])

const SOURCE_LABELS = { sra: 'NCBI SRA', ena: 'EMBL-EBI ENA', ddbj: 'DDBJ' }

function MetaRow({ label, value }) {
  if (!value) return null
  return (
    <div className="meta-item">
      <div className="meta-key">{label}</div>
      <div className="meta-value">{value}</div>
    </div>
  )
}

export default function AccessionPage() {
  const [accession, setAccession]   = useState('')
  const [job, setJob]               = useState(null)
  const [report, setReport]         = useState(null)
  const [error, setError]           = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [confirming, setConfirming] = useState(false)

  // ── Phase 1: poll until preview ready ────────────────────────────────────
  const pollPreview = useCallback(async () => {
    if (!job?.job_id) return
    try {
      const { data } = await accessionApi.preview(job.job_id)
      setJob(data)
    } catch {}
  }, [job?.job_id])

  const { start: startPreviewPoll } = usePolling(
    pollPreview, 3000,
    () => TERMINAL_PREVIEW.has(job?.status)
  )

  // ── Phase 2: poll pipeline after confirmation ─────────────────────────────
  const pollPipeline = useCallback(async () => {
    if (!job?.job_id) return
    try {
      const { data } = await accessionApi.status(job.job_id)
      setJob(data)
      if (data.status === 'ready' && data.validation_job_id) {
        // fetch the validation report via the ingest endpoint
        const { ingestApi } = await import('../api/client')
        const r = await ingestApi.report(data.validation_job_id)
        setReport(r.data)
      }
    } catch {}
  }, [job?.job_id])

  const { start: startPipelinePoll } = usePolling(
    pollPipeline, 3000,
    () => TERMINAL_PIPELINE.has(job?.status)
  )

  // ── Lookup ────────────────────────────────────────────────────────────────
  const handleLookup = async (e) => {
    e.preventDefault()
    setError('')
    setJob(null)
    setReport(null)
    setSubmitting(true)
    try {
      const { data } = await accessionApi.lookup(accession.trim().toUpperCase())
      setJob(data)
      startPreviewPoll()
    } catch (err) {
      const detail = err.response?.data?.detail
      if (Array.isArray(detail)) setError(detail.map(d => d.msg).join(' · '))
      else setError(detail || 'Lookup failed.')
    } finally {
      setSubmitting(false)
    }
  }

  // ── Confirm / Cancel ──────────────────────────────────────────────────────
  const handleConfirm = async (confirmed) => {
    setConfirming(true)
    try {
      const { data } = await accessionApi.confirm(job.job_id, confirmed)
      setJob(data)
      if (confirmed) startPipelinePoll()
    } catch (err) {
      setError(err.response?.data?.detail || 'Confirmation failed.')
    } finally {
      setConfirming(false)
    }
  }

  const reset = () => { setAccession(''); setJob(null); setReport(null); setError('') }

  const preview = job?.metadata_preview
  const phase = !job ? 'input'
    : job.status === 'awaiting_confirmation' ? 'preview'
    : TERMINAL_PIPELINE.has(job.status) ? 'done'
    : 'pipeline'

  const pipelineSteps = [
    { key: 'downloading',        label: 'Downloading',   desc: 'Retrieving raw files from the database.' },
    { key: 'converting',         label: 'Converting',    desc: 'Converting to ASV + taxonomy CSV format.' },
    { key: 'ready',              label: 'Ready',         desc: 'Conversion complete. Entering validation pipeline.' },
  ]
  const pipelineIdx = pipelineSteps.findIndex(s => s.key === job?.status)

  return (
    <>
      <div className="page-header">
        <h2>Ingested Files</h2>
        <p>Pull metagenomic data directly from NCBI SRA, EMBL-EBI ENA, or DDBJ</p>
        <hr className="divider" />
      </div>

      {/* ── Step 1: Input ── */}
      {phase === 'input' && (
        <div className="card">
          <div className="card-title">Enter Accession Number</div>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 18 }}>
            Accepted formats: <span className="font-mono" style={{ color: 'var(--green)' }}>SRR123456</span>,{' '}
            <span className="font-mono" style={{ color: 'var(--green)' }}>ERR123456</span>,{' '}
            <span className="font-mono" style={{ color: 'var(--green)' }}>DRR123456</span>,{' '}
            study IDs (SRP / ERP / DRP), etc.
          </p>
          {error && <div className="alert alert-error">{error}</div>}
          <form onSubmit={handleLookup} style={{ display: 'flex', gap: 12, alignItems: 'flex-end' }}>
            <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
              <label className="form-label">Accession Number</label>
              <input
                className="form-input font-mono"
                placeholder="e.g. SRR12345678"
                value={accession}
                onChange={e => setAccession(e.target.value)}
                required
              />
            </div>
            <button className="btn btn-primary" disabled={submitting || !accession.trim()}>
              {submitting ? <><span className="spinner" /> Looking up…</> : 'Lookup →'}
            </button>
          </form>
        </div>
      )}

      {/* ── Fetching metadata spinner ── */}
      {job && (job.status === 'pending' || job.status === 'fetching_metadata') && (
        <div className="card" style={{ textAlign: 'center', padding: '40px 24px' }}>
          <div className="spinner" style={{ width: 28, height: 28, margin: '0 auto 16px' }} />
          <div style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--text-muted)' }}>
            {job.message}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-faint)', marginTop: 8 }}>
            Polling every 3 seconds…
          </div>
        </div>
      )}

      {/* ── Step 2: Preview ── */}
      {phase === 'preview' && preview && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
            <div>
              <div className="card-title" style={{ marginBottom: 4 }}>Metadata Preview</div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <span className="font-mono" style={{ color: 'var(--green)', fontSize: 14 }}>{preview.accession}</span>
                <span className="badge badge-pending">{SOURCE_LABELS[preview.source] || preview.source}</span>
              </div>
            </div>
            <span className={`badge ${preview.has_processed_tables ? 'badge-ready' : 'badge-pending'}`}>
              {preview.has_processed_tables ? '✓ Tables found' : '⚠ No processed tables'}
            </span>
          </div>

          {preview.study_title && (
            <div style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '12px 16px', marginBottom: 18 }}>
              <div style={{ fontSize: 13.5, fontWeight: 500, marginBottom: 4 }}>{preview.study_title}</div>
              {preview.study_abstract && (
                <div style={{ fontSize: 12.5, color: 'var(--text-muted)', lineHeight: 1.6 }}>
                  {preview.study_abstract.length > 300 ? preview.study_abstract.slice(0, 300) + '…' : preview.study_abstract}
                </div>
              )}
            </div>
          )}

          <div className="meta-grid">
            <MetaRow label="Organism"             value={preview.organism} />
            <MetaRow label="Environment"          value={preview.environment} />
            <MetaRow label="Collection Date"      value={preview.collection_date} />
            <MetaRow label="Geo Location"         value={preview.geo_location} />
            <MetaRow label="Samples"              value={preview.sample_count} />
            <MetaRow label="Platform"             value={preview.sequencing_platform} />
            <MetaRow label="Instrument"           value={preview.instrument_model} />
            <MetaRow label="Submitted By"         value={preview.submitted_by} />
          </div>

          {preview.processed_files?.length > 0 && (
            <>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-faint)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 10 }}>
                Available Files ({preview.processed_files.length})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 18 }}>
                {preview.processed_files.map((f, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-raised)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '8px 14px' }}>
                    <div>
                      <span className="font-mono" style={{ fontSize: 12, color: 'var(--text)' }}>{f.filename}</span>
                      {f.description && <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 10 }}>{f.description}</span>}
                    </div>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      {f.size_bytes && <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>{(f.size_bytes / 1024 / 1024).toFixed(1)} MB</span>}
                      <span className="badge badge-pending">{f.file_type}</span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {preview.readiness_message && (
            <div className={`alert ${preview.has_processed_tables ? 'alert-success' : 'alert-info'}`} style={{ marginBottom: 20 }}>
              {preview.readiness_message}
            </div>
          )}

          <hr className="divider" />
          <div style={{ display: 'flex', gap: 10 }}>
            <button className="btn btn-primary" onClick={() => handleConfirm(true)} disabled={confirming}>
              {confirming ? <><span className="spinner" /> Starting…</> : '⬇ Confirm & Download'}
            </button>
            <button className="btn btn-danger" onClick={() => handleConfirm(false)} disabled={confirming}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* ── Step 3: Pipeline ── */}
      {(phase === 'pipeline' || (phase === 'done' && !TERMINAL_PIPELINE.has(job?.status))) && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
            <div className="card-title" style={{ margin: 0 }}>Download & Convert Pipeline</div>
            <span className={`badge badge-${job.status === 'ready' ? 'ready' : job.status === 'failed' ? 'failed' : 'running'}`}>
              {job.status}
            </span>
          </div>
          <div className="pipeline">
            {pipelineSteps.map((step, i) => {
              const done   = i < pipelineIdx || job.status === 'ready'
              const active = i === pipelineIdx && job.status !== 'failed' && job.status !== 'cancelled'
              const failed = job.status === 'failed' && i === pipelineIdx
              return (
                <div key={step.key} className="pipeline-step">
                  <div className={`step-dot ${done ? 'done' : active ? 'active' : failed ? 'failed' : ''}`}>
                    {done ? '✓' : i + 1}
                  </div>
                  <div className="step-body">
                    <div className="step-title">{step.label} {active && <span className="spinner" style={{ width: 12, height: 12, marginLeft: 8 }} />}</div>
                    <div className="step-desc">{active ? job.message : step.desc}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Cancelled / Failed ── */}
      {job?.status === 'cancelled' && (
        <div className="alert alert-info">
          Import cancelled. No data was downloaded.{' '}
          <button onClick={reset} style={{ background: 'none', border: 'none', color: 'var(--blue)', cursor: 'pointer', textDecoration: 'underline', fontSize: 'inherit' }}>
            Start a new lookup
          </button>
        </div>
      )}

      {job?.status === 'failed' && (
        <div className="alert alert-error">
          {job.message}{' '}
          <button onClick={reset} style={{ background: 'none', border: 'none', color: 'var(--red)', cursor: 'pointer', textDecoration: 'underline', fontSize: 'inherit' }}>
            Try again
          </button>
        </div>
      )}

      {report && <ValidationReport report={report} />}
    </>
  )
}
