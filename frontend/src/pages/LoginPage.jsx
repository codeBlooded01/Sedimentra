import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import '../styles/login.css'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate   = useNavigate()
  const [form, setForm]     = useState({ email: '', password: '' })
  const [error, setError]   = useState('')
  const [pending, setPending] = useState(false)
  const [loading, setLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  const handle = async (e) => {
    e.preventDefault()
    setError('')
    setPending(false)
    setLoading(true)
    try {
      await login(form.email, form.password)
      navigate('/dashboard')
    } catch (err) {
      const detail = err.response?.data?.detail || 'Login failed. Please check your credentials.'
      if (detail.toLowerCase().includes('pending admin approval') ||
          detail.toLowerCase().includes('pending')) {
        setPending(true)
      } else {
        setError(detail)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page-wrapper">
      {/* LEFT PANE - Landing Page Variant */}
      <div className="login-left-pane">
        <nav className="login-left-nav">
          <Link to="/" style={{ textDecoration: 'none' }}>
            <div className="login-left-logo">Sedimentra</div>
          </Link>
        </nav>
        <main className="login-left-main">
          <h1 className="login-left-title">Sedimentra</h1>
          <p className="login-left-subtitle">
            This system transforms hidden microbial signals into early warnings <br />
            by detecting imbalance and predicting disturbance in coastal <br />
            ecosystems through genomic intelligence.
          </p>
        </main>
      </div>

      {/* RIGHT PANE - Login Panel */}
      <div className="login-right-pane">
        <div className="login-form-container">
          
          <div className="login-tabs">
            <Link to="/login" className="login-tab active">LOG IN</Link>
            <Link to="/signup" className="login-tab">SIGN UP</Link>
          </div>

          <h2 className="login-panel-title">Access Account</h2>
          <div className="login-separator"></div>

          {pending && (
            <div style={{
              background: '#FFF8E1',
              border: '1px solid #FFE082',
              borderRadius: 6,
              padding: '12px 14px',
              marginBottom: 20,
              display: 'flex',
              gap: 8,
              alignItems: 'flex-start',
            }}>
              <span className="spinner" style={{ display: 'inline-block', width: 16, height: 16 }}></span>
              <div>
                <div style={{ color: '#F57F17', fontSize: 11, fontWeight: 700, marginBottom: 2 }}>
                  ACCOUNT PENDING APPROVAL
                </div>
                <p style={{ color: '#F57F17', fontSize: 13, margin: 0 }}>
                  Your account is awaiting administrator approval.
                </p>
              </div>
            </div>
          )}

          {error && <div style={{ color: '#D32F2F', background: '#FFEBEE', padding: '10px 14px', borderRadius: '6px', marginBottom: '20px', fontSize: '0.9rem', border: '1px solid #FFCDD2' }}>{error}</div>}

          <form onSubmit={handle} style={{ display: 'flex', flexDirection: 'column' }}>
            <div className="login-form-group">
              <div className="login-label-row">
                <label className="login-label">Email Address</label>
              </div>
              <input
                className="login-input"
                type="email"
                placeholder="email@denr.gov.ph"
                value={form.email}
                onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                required
              />
            </div>

            <div className="login-form-group">
              <div className="login-label-row">
                <label className="login-label">Password</label>
                <Link to="/forgot-password" className="forgot-link">Forgot Password?</Link>
              </div>
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                <input
                  className="login-input"
                  style={{ paddingRight: '40px' }}
                  type={showPassword ? 'text' : 'password'}
                  placeholder="********"
                  value={form.password}
                  onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  style={{ 
                    position: 'absolute', right: '12px', background: 'none', 
                    border: 'none', cursor: 'pointer', color: '#B5B5B5', display: 'flex' 
                  }}
                >
                  {showPassword ? (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                  )}
                </button>
              </div>
            </div>

            <button
              className="login-submit-btn"
              type="submit"
              disabled={loading}
            >
              {loading ? 'SIGNING IN...' : 'LOG IN'}
            </button>
          </form>

          <div className="login-footer-text">
            Don't have an account? 
            <Link to="/signup" className="login-footer-link">Request Access</Link>
          </div>

        </div>
      </div>
    </div>
  )
}
