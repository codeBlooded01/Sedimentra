import { useAuth } from '../hooks/useAuth'
import { useNavigate } from 'react-router-dom'
import { AnalysisEmbedded } from './AnalysisReportPage'

const STORAGE_KEY = 'gis_ingested_files'

function getRecentFiles() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]').slice(0, 3) } catch { return [] }
}

const STAT_CARDS = [
  { label: 'Data Ingestion',    desc: 'Upload ASV + taxonomy CSV pairs for validation and preprocessing.', icon: 'upload',    href: '/ingest',    cta: 'Upload Files' },
]

const ICONS = {
  upload: (
    <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#938575" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242" />
      <path d="M12 12v9" />
      <path d="m16 16-4-4-4 4" />
    </svg>
  ),
  accession: (
    <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#938575" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
      <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
      <line x1="12" y1="22.08" x2="12" y2="12"/>
    </svg>
  ),
}

export default function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const recentFiles = getRecentFiles()

  return (
    <>
      <div className="page-header">
        <h2>Dashboard</h2>
        <p>Overview of system metrics and status</p>
        <hr className="divider" />
      </div>

      {/* Status strip */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 28, flexWrap: 'wrap' }}>
        {[].map(s => (
          <div key={s.label} style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: 'var(--bg-surface)', border: '1px solid var(--border)',
            borderRadius: 99, padding: '4px 12px', fontSize: 12,
          }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: s.ok ? 'var(--green)' : 'var(--red)', display: 'inline-block' }} />
            <span style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{s.label}</span>
          </div>
        ))}
      </div>



      {/* Recent Ingestion Summary */}
      {recentFiles.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <div className="card-title" style={{ margin: 0 }}>Recent Ingestion Analysis</div>
            <button
              className="btn btn-ghost"
              style={{ fontSize: 12, padding: '5px 12px' }}
              onClick={() => navigate('/ingested-data')}
            >
              View all datasets →
            </button>
          </div>
          
          <div style={{ marginBottom: -8, color: '#938575', fontSize: 13 }}>
            Showing analysis for <span style={{ fontWeight: 600, color: '#333' }}>{recentFiles[0].name || 'Unnamed dataset'}</span> ingested on {recentFiles[0].date}.
          </div>
          
          <AnalysisEmbedded jobId={recentFiles[0].id} />
        </div>
      )}

      {/* About */}
      <div className="card">
        <div className="card-title">About this system</div>
        <p style={{ fontSize: 13.5, color: 'var(--text-muted)', lineHeight: 1.7, maxWidth: 640 }}>
          The Genomic Intelligence System (GIS) is designed for DENR Region VIII staff to ingest,
          validate, and preprocess metagenomic biodiversity data. Uploaded files are validated through
          a 3-layer pipeline — structural, schema, and relational checks — before being preprocessed
          for downstream ML analysis. Data can be uploaded directly as CSV pairs or imported via
          public accession numbers from NCBI SRA, EMBL-EBI ENA, or DDBJ.
        </p>
      </div>
    </>
  )
}
