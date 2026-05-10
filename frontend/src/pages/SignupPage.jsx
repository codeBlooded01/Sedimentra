import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { authApi } from '../api/client'
import '../styles/login.css'

export default function SignupPage() {
  const navigate = useNavigate()
  
  // Step State (1 or 2)
  const [step, setStep] = useState(1)
  
  // Form Data
  const [form, setForm] = useState({
    firstName: '',
    middleName: '',
    lastName: '',
    email: '',
    password: '',
    confirmPassword: ''
  })
  
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)

  // Handlers
  const handleNext = (e) => {
    e.preventDefault()
    if (!form.firstName.trim() || !form.lastName.trim()) {
      setError('First and Last name are required.')
      return
    }
    setError('')
    setStep(2)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    
    if (form.password !== form.confirmPassword) {
      setError('Passwords do not match.')
      return
    }
    
    setError('')
    setLoading(true)
    
    try {
      const parts = [form.firstName.trim(), form.middleName.trim(), form.lastName.trim()].filter(Boolean)
      const fullName = parts.join(' ')
      
      await authApi.signup(form.email, form.password, fullName)
      setSuccess(true)
    } catch (err) {
      const detail = err.response?.data?.detail
      if (Array.isArray(detail)) {
        setError(detail.map(d => d.msg).join(' · '))
      } else {
        setError(detail || 'Signup failed.')
      }
    } finally {
      setLoading(false)
    }
  }

  // Success State
  if (success) return (
    <div className="login-page-wrapper" style={{ justifyContent: 'center', alignItems: 'center', background: '#f5f5f5' }}>
      <div style={{ background: '#fff', padding: '40px', borderRadius: '24px', textAlign: 'center', maxWidth: '400px', boxShadow: '0 4px 20px rgba(0,0,0,0.05)' }}>
        <div className="spinner" style={{ width: 40, height: 40, marginBottom: 16 }}></div>
        <h2 style={{ fontFamily: 'Instrument Sans', fontSize: '1.4rem', fontWeight: 700, marginBottom: 10 }}>Request Submitted</h2>
        <p style={{ color: '#666', fontSize: '0.9rem', marginBottom: 16, lineHeight: 1.5 }}>
          Your account request has been submitted for <strong>admin review</strong>.
        </p>
        <p style={{ color: '#888', fontSize: '0.85rem', marginBottom: 30, lineHeight: 1.5 }}>
          You will be able to log in once an administrator approves your account. This may take some time.
        </p>
        <Link to="/login" className="login-submit-btn" style={{ textDecoration: 'none', display: 'inline-block' }}>
          ← Back to Login
        </Link>
      </div>
    </div>
  )

  return (
    <div className="login-page-wrapper">
      {/* LEFT PANE */}
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

      {/* RIGHT PANE */}
      <div className="login-right-pane">
        <div className="login-form-container">
          
          {/* TABS */}
          <div className="login-tabs">
            <Link to="/login" className="login-tab">LOG IN</Link>
            <Link to="/signup" className="login-tab active">SIGN UP</Link>
          </div>

          <h2 className="login-panel-title">Request Access</h2>
          <div className="login-separator"></div>

          {error && (
            <div style={{ color: '#D32F2F', background: '#FFEBEE', padding: '10px 14px', borderRadius: '6px', marginBottom: '20px', fontSize: '0.9rem', border: '1px solid #FFCDD2' }}>
              {error}
            </div>
          )}

          {/* DYNAMIC FORM */}
          <form style={{ display: 'flex', flexDirection: 'column' }} onSubmit={step === 1 ? handleNext : handleSubmit}>
            
            {step === 1 ? (
              <>
                <div style={{ fontSize: '1.05rem', fontWeight: 800, color: '#555', marginBottom: '20px' }}>Full Name</div>
                
                <div className="login-form-group">
                  <input className="login-input" placeholder="First Name" value={form.firstName}
                    onChange={e => setForm(f => ({ ...f, firstName: e.target.value }))} required />
                </div>
                
                <div className="login-form-group">
                  <input className="login-input" placeholder="Middle Name (Optional)" value={form.middleName}
                    onChange={e => setForm(f => ({ ...f, middleName: e.target.value }))} />
                </div>
                
                <div className="login-form-group">
                  <input className="login-input" placeholder="Last Name" value={form.lastName}
                    onChange={e => setForm(f => ({ ...f, lastName: e.target.value }))} required />
                </div>

                <div style={{ paddingBottom: '8px' }}></div>
                
                <button type="submit" className="login-submit-btn">
                  NEXT <span style={{ marginLeft: 6 }}>→</span>
                </button>
              </>
            ) : (
              <>
                {/* Back button strictly visual or functionally allows editing name */}
                <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: '10px' }}>
                  <button type="button" onClick={() => setStep(1)} style={{ background: 'none', border: 'none', color: '#938575', cursor: 'pointer', fontWeight: 700, fontSize: '0.85rem' }}>
                    ← Back to Name
                  </button>
                </div>

                <div className="login-form-group">
                  <label className="login-label" style={{ marginBottom: 8 }}>Email Address</label>
                  <input className="login-input" type="email" placeholder="email@denr.gov.ph" value={form.email}
                    onChange={e => setForm(f => ({ ...f, email: e.target.value }))} required />
                </div>
                
                <div className="login-form-group">
                  <label className="login-label" style={{ marginBottom: 8 }}>Password</label>
                  <input className="login-input" type="password" placeholder="********" value={form.password}
                    onChange={e => setForm(f => ({ ...f, password: e.target.value }))} required />
                </div>

                <div className="login-form-group">
                  <label className="login-label" style={{ marginBottom: 8 }}>Confirm Password</label>
                  <input className="login-input" type="password" placeholder="********" value={form.confirmPassword}
                    onChange={e => setForm(f => ({ ...f, confirmPassword: e.target.value }))} required />
                </div>
                
                <div style={{ paddingBottom: '8px' }}></div>

                <button type="submit" className="login-submit-btn" disabled={loading}>
                  {loading ? 'CREATING ACCOUNT...' : 'CREATE ACCOUNT'}
                </button>
              </>
            )}
          </form>

          {/* FOOTER LINK */}
          <div className="login-footer-text" style={{ marginTop: '30px' }}>
            Already have an account? 
            <Link to="/login" className="login-footer-link">Log In</Link>
          </div>

          {/* PAGINATION DOTS */}
          <div style={{ display: 'flex', gap: '10px', justifyContent: 'center', marginTop: '35px' }}>
            <div style={{ 
              width: '8px', height: '8px', borderRadius: '50%', 
              background: step === 1 ? '#CCC' : 'transparent',
              border: step === 1 ? 'none' : '1px solid #CCC'
            }}></div>
            <div style={{ 
              width: '8px', height: '8px', borderRadius: '50%', 
              background: step === 2 ? '#CCC' : 'transparent',
              border: step === 2 ? 'none' : '1px solid #CCC'
            }}></div>
          </div>

        </div>
      </div>
    </div>
  )
}
