const LAYER_LABELS = {
  layer_1_structural: 'Layer 1 — Structural',
  layer_2_schema:     'Layer 2 — Schema',
  layer_3_relational: 'Layer 3 — Relational',
  preprocessing:      'Preprocessing',
}

const ALL_LAYERS = ['layer_1_structural', 'layer_2_schema', 'layer_3_relational', 'preprocessing']

export default function ValidationReport({ report }) {
  if (!report) return null

  const passed = new Set(report.passed_layers || [])
  const errorsByLayer = {}
  for (const e of report.errors || []) {
    if (!errorsByLayer[e.layer]) errorsByLayer[e.layer] = []
    errorsByLayer[e.layer].push(e)
  }

  // Warnings arrive as objects { step, code, message } — extract the message string safely
  const warnings = (report.warnings || []).map(w =>
    typeof w === 'string' ? w : (w?.message || w?.code || JSON.stringify(w))
  )

  const hasFailed = report.status !== 'ready'
  const hasNoErrors = (report.errors || []).length === 0

  return (
    <div className="card">
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div className="card-title" style={{ margin: 0 }}>Validation Report</div>
        <span
          className={`badge badge-${report.status === 'ready' ? 'ready' : 'failed'}`}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}
        >
          {report.status === 'ready' ? (
            <>
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              Passed
            </>
          ) : (
            <>
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              Failed
            </>
          )}
        </span>
      </div>

      {/* Summary banner */}
      {report.summary && (
        <div className={`alert ${report.status === 'ready' ? 'alert-success' : 'alert-error'}`} style={{ marginBottom: 20 }}>
          {report.summary}
        </div>
      )}

      {/* Fallback banner when job failed but backend sent no structured errors */}
      {hasFailed && hasNoErrors && !report.summary && (
        <div className="alert alert-error" style={{ marginBottom: 20 }}>
          Validation failed. The pipeline encountered an unexpected error while processing your files.
          Please verify that both CSV files match the required format and try again.
        </div>
      )}

      {/* Per-layer breakdown */}
      {ALL_LAYERS.map(layer => {
        const isPassed  = passed.has(layer)
        const errors    = errorsByLayer[layer] || []
        const hasErrors = errors.length > 0
        return (
          <div key={layer} className="report-layer">
            <div className="report-layer-header">
              <span style={{ color: isPassed ? '#938575' : hasErrors ? '#5c3d2e' : '#C8C4BE' }}>
                {isPassed ? '✓' : hasErrors ? '✗' : '—'}
              </span>
              <span style={{
                color: isPassed ? '#938575' : hasErrors ? '#3d2b1f' : '#C8C4BE',
                fontFamily: 'Instrument Sans, sans-serif',
                fontWeight: isPassed ? 600 : hasErrors ? 700 : 400,
              }}>
                {LAYER_LABELS[layer] || layer}
              </span>
            </div>
            {hasErrors && (
              <div className="report-layer-body">
                {errors.map((e, i) => (
                  <div key={i} className="error-item">
                    <div className="error-code">{e.code}</div>
                    <div>{e.user_message}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}

      {/* Warnings */}
      {warnings.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={{
            fontFamily: 'Instrument Sans, sans-serif',
            fontSize: 11, fontWeight: 600,
            color: '#9A9A9A', letterSpacing: '0.08em',
            textTransform: 'uppercase', marginBottom: 8,
          }}>
            Warnings ({warnings.length})
          </div>
          {warnings.map((w, i) => (
            <div key={i} className="warning-item">{w}</div>
          ))}
        </div>
      )}
    </div>
  )
}
