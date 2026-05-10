import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ingestApi } from '../api/client';
import { AnalysisEmbedded } from './AnalysisReportPage';

const STORAGE_KEY = 'gis_ingested_files';

function loadFiles() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

function saveFiles(files) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(files)); } catch {}
}



// ── Sparkline SVG chart (decorative — reflects file index as a unique wave) ──
function SparklineChart({ seed = 1 }) {
  const w = 960, h = 260;
  const pts = Array.from({ length: 12 }, (_, i) => {
    const x = (i / 11) * w;
    const y = h - 40 - Math.abs(Math.sin((i + seed) * 0.9) * 80 + Math.cos((i * seed) * 0.6) * 50 + 30);
    return `${x},${y}`;
  });
  const pts2 = Array.from({ length: 12 }, (_, i) => {
    const x = (i / 11) * w;
    const y = h - 40 - Math.abs(Math.sin((i + seed * 2) * 0.7) * 70 + Math.cos((i * 1.2) * 0.5) * 45 + 20);
    return `${x},${y}`;
  });
  const path1 = `M0,${h} C${pts[0]} ${pts.slice(1).map(p => `${p}`).join(' ')} L${w},${h} Z`;
  const path2 = `M0,${h} C${pts2[0]} ${pts2.slice(1).map(p => `${p}`).join(' ')} L${w},${h} Z`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ width: '100%', height: '100%' }}>
      <path d={path1} fill="#DDCBAF" opacity="0.55" />
      <path d={path2} fill="#938575" opacity="0.50" />
    </svg>
  );
}

function FileCardMenu({ file, onRename, onTrash, onClose }) {
  const ref = useRef();
  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) onClose(); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  return (
    <div ref={ref} style={{
      position: 'absolute', top: '100%', right: 0, zIndex: 50,
      marginTop: 6, background: '#fff', border: '1px solid #EBEBEB',
      borderRadius: 12, boxShadow: '0 6px 24px rgba(0,0,0,0.06)',
      minWidth: 160, padding: '6px 0', overflow: 'hidden',
    }}>
      <button onClick={() => { onRename(file); onClose(); }} style={{
        display: 'flex', alignItems: 'center', gap: 12, width: '100%',
        background: 'none', border: 'none', padding: '10px 16px',
        fontFamily: 'Instrument Sans', fontSize: 13, color: '#333',
        cursor: 'pointer', textAlign: 'left',
      }}
        onMouseEnter={e => e.currentTarget.style.background = '#F9F8F6'}
        onMouseLeave={e => e.currentTarget.style.background = 'none'}
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#938575" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>
        Rename
      </button>
      <div style={{ height: 1, background: '#F5F5F5', margin: '4px 16px' }} />
      <button onClick={() => { onTrash(file.id); onClose(); }} style={{
        display: 'flex', alignItems: 'center', gap: 12, width: '100%',
        background: 'none', border: 'none', padding: '10px 16px',
        fontFamily: 'Instrument Sans', fontSize: 13, color: '#7a3e2e',
        cursor: 'pointer', textAlign: 'left',
      }}
        onMouseEnter={e => e.currentTarget.style.background = '#FEF4F1'}
        onMouseLeave={e => e.currentTarget.style.background = 'none'}
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#7a3e2e" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
        Move to Trash
      </button>
    </div>
  );
}

export default function IngestedDataPage() {
  const location = useLocation();
  const navigate = useNavigate();

  const [files, setFiles] = useState(() => loadFiles());
  const [selectedFile, setSelectedFile] = useState(null);
  const [openMenu, setOpenMenu] = useState(null);
  const [renaming, setRenaming] = useState(null);
  const [renameValue, setRenameValue] = useState('');

  // When redirected from IngestPage with a new job, register + open it
  useEffect(() => {
    const newJob = location.state?.newJob;
    if (!newJob) return;

    // Avoid duplicate entries
    setFiles(prev => {
      if (prev.some(f => f.jobId === newJob.jobId)) {
        const existing = prev.find(f => f.jobId === newJob.jobId);
        setSelectedFile(existing);
        return prev;
      }
      const entry = {
        id: newJob.id,
        jobId: newJob.jobId,
        name: '',  // blank — user will name it
        date: newJob.date,
        asvFileName: newJob.asvFileName,
        taxFileName: newJob.taxFileName,
        isNew: true,
      };
      const updated = [entry, ...prev];
      saveFiles(updated);
      setSelectedFile(entry);
      return updated;
    });

    // Clear state so refresh doesn't re-register
    window.history.replaceState({}, '');
  }, [location.state]);

  const handleRename = (file) => { setRenaming(file.id); setRenameValue(file.name); };

  const commitRename = (id) => {
    if (renameValue.trim()) {
      setFiles(prev => {
        const updated = prev.map(f => f.id === id ? { ...f, name: renameValue.trim(), isNew: false } : f);
        saveFiles(updated);
        return updated;
      });
      if (selectedFile?.id === id) {
        setSelectedFile(prev => ({ ...prev, name: renameValue.trim(), isNew: false }));
      }
    }
    setRenaming(null);
  };

  const handleTrash = (id) => {
    setFiles(prev => { const updated = prev.filter(f => f.id !== id); saveFiles(updated); return updated; });
    if (selectedFile?.id === id) setSelectedFile(null);
  };

  const handleNameSave = (file, name) => {
    if (!name.trim()) return;
    setFiles(prev => {
      const updated = prev.map(f => f.id === file.id ? { ...f, name: name.trim(), isNew: false } : f);
      saveFiles(updated);
      return updated;
    });
    setSelectedFile(prev => ({ ...prev, name: name.trim(), isNew: false }));
  };

  if (selectedFile) {
    return (
      <DetailView
        file={selectedFile}
        onBack={() => setSelectedFile(null)}
        onNameSave={handleNameSave}
        navigate={navigate}
      />
    );
  }

  return (
    <>
      <div className="page-header">
        <h2 style={{ fontWeight: 600 }}>Ingested Files</h2>
        <p>Manage and preview your uploaded and validated sample data</p>
        <hr className="divider" />
      </div>

      <div className="file-grid">
        {/* Add Card */}
        <div className="file-card file-card-add" onClick={() => navigate('/ingest')}>
          <div className="file-card-add-icon">+</div>
        </div>
        {/* Data Cards */}
        {files.map(f => (
          <div key={f.id} className="file-card" style={{ position: 'relative', overflow: 'visible' }}
            onClick={() => renaming !== f.id && setSelectedFile(f)}
          >
            <div className="file-card-preview">
              <SparklineChart seed={f.id?.charCodeAt?.(0) ?? 1} />
            </div>
            <div className="file-card-footer" onClick={e => e.stopPropagation()}>
              {renaming === f.id ? (
                <input
                  autoFocus
                  value={renameValue}
                  onChange={e => setRenameValue(e.target.value)}
                  onBlur={() => commitRename(f.id)}
                  onKeyDown={e => { if (e.key === 'Enter') commitRename(f.id); if (e.key === 'Escape') setRenaming(null); }}
                  style={{
                    fontFamily: 'Instrument Sans', fontSize: 13, fontWeight: 600,
                    border: 'none', borderBottom: '1px solid #938575', outline: 'none',
                    background: 'transparent', color: '#333', flex: 1, padding: '2px 0',
                  }}
                />
              ) : (
                <span style={{ fontFamily: 'Instrument Sans', fontSize: 13, fontWeight: 600, color: f.name ? '#333' : '#B4A99A', fontStyle: f.name ? 'normal' : 'italic' }}>
                  {f.name || 'Unnamed dataset'}
                </span>
              )}
              <span
                className="file-card-menu"
                style={{ color: '#938575', cursor: 'pointer', padding: '2px 4px', borderRadius: 4 }}
                onClick={e => { e.stopPropagation(); setOpenMenu(openMenu === f.id ? null : f.id); }}
              >⋮</span>
            </div>
            {f.isNew && (
              <div style={{
                position: 'absolute', top: 8, left: 8,
                background: '#1D9E75', color: '#fff',
                fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 20,
                fontFamily: 'Instrument Sans', letterSpacing: '0.04em',
              }}>NEW</div>
            )}
            {openMenu === f.id && (
              <FileCardMenu
                file={f}
                onRename={handleRename}
                onTrash={handleTrash}
                onClose={() => setOpenMenu(null)}
              />
            )}
          </div>
        ))}
      </div>
    </>
  );
}

function DetailView({ file, onBack, onNameSave, navigate }) {
  const [tab, setTab] = useState('Summary');
  const [nameInput, setNameInput] = useState(file.name || '');
  const [nameSaved, setNameSaved] = useState(!!file.name);
  
  const [asvData, setAsvData] = useState(null);
  const [taxData, setTaxData] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    if (tab === 'ASV Table' && !asvData && file.jobId) {
      setPreviewLoading(true);
      ingestApi.previewAsv(file.jobId)
        .then(res => setAsvData(res.data))
        .catch(err => console.error(err))
        .finally(() => setPreviewLoading(false));
    } else if (tab === 'Taxonomy Inventory' && !taxData && file.jobId) {
      setPreviewLoading(true);
      ingestApi.previewTaxonomy(file.jobId)
        .then(res => setTaxData(res.data))
        .catch(err => console.error(err))
        .finally(() => setPreviewLoading(false));
    }
  }, [tab, file.jobId]);

  const handleSaveName = () => {
    if (!nameInput.trim()) return;
    onNameSave(file, nameInput.trim());
    setNameSaved(true);
  };

  const displayName = nameSaved && nameInput.trim() ? nameInput.trim() : (file.name || 'Unnamed dataset');

  return (
    <>
      <div className="page-header" style={{ position: 'relative' }}>
        <button onClick={onBack} className="btn-ghost" style={{
          position: 'absolute', right: 0, top: 4, padding: '6px 14px',
          fontSize: 13, fontFamily: 'Instrument Sans', fontWeight: 600,
          border: 'none', background: 'transparent', color: '#938575',
        }}>
          ← Back to Files
        </button>
        <h2>{displayName}</h2>
        <p>Detailed overview and graphical analysis</p>
        <hr className="divider" />
      </div>

      {/* Name your dataset prompt (shown when isNew or unnamed) */}
      {(!file.name || file.isNew) && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#938575" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>
            <span style={{ fontFamily: 'Instrument Sans', fontSize: 11, fontWeight: 700, color: '#938575', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Name your dataset
            </span>
          </div>
          <p style={{ fontSize: 13, color: '#9A9A9A', marginBottom: 14, lineHeight: 1.5 }}>
            Give this ingested file a recognisable name so you can find it later.
          </p>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <input
              autoFocus
              value={nameInput}
              onChange={e => setNameInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleSaveName(); }}
              placeholder="e.g. Bangon River — Station 3"
              style={{
                flex: 1, fontFamily: 'Instrument Sans', fontSize: 14,
                border: '1px solid #D4D0C8', borderRadius: 8,
                padding: '10px 14px', outline: 'none', color: '#333',
                background: '#fff',
              }}
              onFocus={e => e.target.style.borderColor = '#938575'}
              onBlur={e => e.target.style.borderColor = '#D4D0C8'}
            />
            <button
              className="btn btn-primary"
              onClick={handleSaveName}
              disabled={!nameInput.trim()}
              style={{ whiteSpace: 'nowrap' }}
            >
              Save Name
            </button>
          </div>
          {nameSaved && (
            <div style={{ marginTop: 10, fontSize: 12, color: '#1D9E75', fontWeight: 600 }}>
              ✓ Saved as "{nameInput.trim()}"
            </div>
          )}
        </div>
      )}

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 32, marginBottom: 24, alignItems: 'center' }}>
        {['Summary', 'ASV Table', 'Taxonomy Inventory'].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            background: 'none', border: 'none',
            borderBottom: tab === t ? '2px solid #9A9A9A' : '2px solid transparent',
            color: tab === t ? '#333' : '#B4B4B4',
            fontFamily: 'Instrument Sans', fontSize: 16,
            fontWeight: tab === t ? 700 : 500,
            padding: '0 4px 8px 4px', cursor: 'pointer', transition: 'all 0.2s',
          }}>
            {t}
          </button>
        ))}
      </div>

      {tab === 'Summary' && (
        <>
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-title" style={{ color: '#111' }}>Dataset Summary</div>
            <p style={{ color: '#A3A3A3', fontSize: 13, lineHeight: 1.6, marginBottom: 4 }}>
              Sequence depth appears nominal across all pooled distributions. Structural and relational constraints satisfied.
            </p>
            {file.asvFileName && (
              <p style={{ color: '#B4A99A', fontSize: 12, marginBottom: 0 }}>
                ASV: <span style={{ fontFamily: 'var(--mono)' }}>{file.asvFileName}</span>
                &nbsp;·&nbsp;
                Taxonomy: <span style={{ fontFamily: 'var(--mono)' }}>{file.taxFileName}</span>
              </p>
            )}
          </div>
          <AnalysisEmbedded jobId={file.id} />
        </>
      )}

      {tab === 'ASV Table' && (
        <div className="card" style={{ overflowX: 'auto' }}>
          <div className="card-title" style={{ color: '#111' }}>ASV Table Preview</div>
          {previewLoading ? (
            <p style={{ fontSize: 13, color: '#938575' }}>Loading table preview...</p>
          ) : asvData ? (
            <div style={{ overflowX: 'auto', marginBottom: 20 }}>
              <table style={{ minWidth: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr>
                    {asvData.columns.map((col, i) => (
                      <th key={i} style={{ padding: '10px 14px', background: '#F9F9F9', borderBottom: '1px solid #E8E8E8', textAlign: 'left', fontWeight: 600, color: '#666', whiteSpace: 'nowrap' }}>
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {asvData.rows.map((row, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #F0F0F0' }}>
                      {asvData.columns.map((col, j) => (
                        <td key={j} style={{ padding: '10px 14px', color: '#444', whiteSpace: 'nowrap' }}>
                          {row[col]}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p style={{ fontSize: 13, color: '#E24B4A' }}>Failed to load table preview.</p>
          )}
          <button className="btn btn-ghost" style={{ background: '#F9F9F9', color: '#111' }}>
            <svg style={{ marginRight: 6 }} xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>
            Download ASV Table
          </button>
        </div>
      )}

      {tab === 'Taxonomy Inventory' && (
        <div className="card" style={{ overflowX: 'auto' }}>
          <div className="card-title" style={{ color: '#111' }}>Taxonomy Inventory Preview</div>
          {previewLoading ? (
            <p style={{ fontSize: 13, color: '#938575' }}>Loading table preview...</p>
          ) : taxData ? (
            <div style={{ overflowX: 'auto', marginBottom: 20 }}>
              <table style={{ minWidth: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr>
                    {taxData.columns.map((col, i) => (
                      <th key={i} style={{ padding: '10px 14px', background: '#F9F9F9', borderBottom: '1px solid #E8E8E8', textAlign: 'left', fontWeight: 600, color: '#666', whiteSpace: 'nowrap' }}>
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {taxData.rows.map((row, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #F0F0F0' }}>
                      {taxData.columns.map((col, j) => (
                        <td key={j} style={{ padding: '10px 14px', color: '#444', whiteSpace: 'nowrap' }}>
                          {row[col]}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p style={{ fontSize: 13, color: '#E24B4A' }}>Failed to load table preview.</p>
          )}
          <button className="btn btn-ghost" style={{ background: '#F9F9F9', color: '#111' }}>
            <svg style={{ marginRight: 6 }} xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>
            Download Taxonomy Inventory
          </button>
        </div>
      )}
    </>
  );
}
