import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { adminApi } from '../api/client'
import '../styles/login.css'

export default function AdminSetupPage() {
  const navigate = useNavigate()
  
  // Step State
  const [setupStep, setSetupStep] = useState(1)
  
  // Form State
  const [form, setForm] = useState({ firstName: '', middleName: '', lastName: '', email: '', password: '', confirm: '' })
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)
  
  // Password View Toggles
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)

  const handleNext = (e) => {
    e.preventDefault()
    if (!form.firstName.trim() || !form.lastName.trim()) {
      setError('First and Last name are required.')
      return
    }
    setError('')
    setSetupStep(2)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (form.password !== form.confirm) {
      setError('Passwords do not match.')
      return
    }

    setLoading(true)
    try {
      const parts = [form.firstName.trim(), form.middleName.trim(), form.lastName.trim()].filter(Boolean)
      const fullName = parts.join(' ')
      
      await adminApi.setup(form.email, form.password, fullName)
      setSuccess(true)
      setTimeout(() => navigate('/login'), 2500)
    } catch (err) {
      const detail = err.response?.data?.detail
      if (Array.isArray(detail)) {
        setError(detail.map(d => d.msg).join(' · '))
      } else if (err.response) {
        setError(`Error ${err.response.status}: ${JSON.stringify(err.response.data)}`)
      } else {
        setError(err.message || 'Admin setup failed.')
      }
    } finally {
      setLoading(false)
    }
  }

  // Generic Success screen rendering (Mimicked from AuthPage)
  if (success) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'url(/bg_main.png) center/cover no-repeat', fontFamily: '"Instrument Sans", sans-serif' }}>
      <div style={{ background: '#ffffff', borderRadius: 40, padding: '60px 40px', width: '100%', maxWidth: 400, textAlign: 'center', boxShadow: '0 10px 40px rgba(0,0,0,0.08)' }}>
        <h2 style={{
          margin: '0',
          fontSize: 26,
          fontWeight: 800,
          background: 'url(/text_bg.png) center/cover no-repeat',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
          color: 'transparent',
          paddingBottom: 24,
          borderBottom: '1px solid #f0f0f0',
          marginBottom: 32
        }}>
          Sedimentra
        </h2>
        <h1 style={{ margin: '0 0 16px', fontSize: 26, fontWeight: 700, color: '#4c4c4c', letterSpacing: '-0.5px' }}>
          Admin Account Created
        </h1>
        <p style={{ margin: '0 0 16px', color: '#593e32', fontSize: 16, fontWeight: 500, lineHeight: 1.4 }}>
          Redirecting you to login...
        </p>
      </div>
    </div>
  )

  return (
    <div className="login-page-wrapper">
      
      {/* STATIC LEFT PANE (Mimicked exactly from AuthPage) */}
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

      {/* RIGHT PANE WRAPPER */}
      <div className="login-right-pane">
        <div className="login-form-container">
          
          {/* We don't have Tabs here since it's just Admin Setup, but we wrap the content inside the auth-forms-container */}
          <div className="auth-forms-container" style={{ marginTop: '20px' }}>
            
            {/* SETUP PANEL */}
            <div className={`auth-form-panel signup-panel active`}>

              {/* Step Progress Dots + Back button on same row */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                <div style={{ display: 'flex', gap: 6 }}>
                  {[1, 2].map(step => (
                    <div key={step} style={{
                      height: 6,
                      width: setupStep === step ? 28 : 10,
                      borderRadius: 99,
                      background: setupStep === step ? '#938575' : '#D6CEC6',
                      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    }} />
                  ))}
                </div>
                {setupStep === 2 && (
                  <button
                    type="button"
                    onClick={() => setSetupStep(1)}
                    style={{ background: 'none', border: 'none', color: '#999', cursor: 'pointer', fontFamily: 'Instrument Sans', fontSize: '0.85rem', fontWeight: 500, display: 'flex', alignItems: 'center', gap: 4, padding: 0 }}
                  >
                    ← Back
                  </button>
                )}
              </div>

              {error && (
                <div style={{ color: '#D32F2F', background: '#FFEBEE', padding: '10px 14px', borderRadius: '8px', marginBottom: '16px', fontSize: '0.85rem', border: '1px solid #FFCDD2' }}>
                  {error}
                </div>
              )}

              <form style={{ display: 'flex', flexDirection: 'column' }} onSubmit={setupStep === 1 ? handleNext : handleSubmit}>
                {setupStep === 1 ? (
                  <>
                    {/* Step 1: Name */}
                    <h2 style={{ fontFamily: 'Instrument Sans', fontSize: '1.9rem', fontWeight: 700, color: '#1A1A1A', margin: '0 0 6px 0', letterSpacing: '-0.5px', lineHeight: 1.2 }}>
                      Admin Setup
                    </h2>
                    <p style={{ fontFamily: 'Instrument Sans', fontSize: '0.9rem', color: '#888', margin: '0 0 20px 0', fontWeight: 400 }}>
                      Genomic Intelligence System — One-time setup
                    </p>

                    <div style={{ background: '#F5F5F5', border: '1px solid #E0E0E0', borderRadius: 8, padding: '12px 14px', marginBottom: 24, display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                      <div>
                        <div style={{ color: '#666666', fontSize: 11, fontWeight: 700, marginBottom: 2 }}>RESTRICTED SETUP</div>
                        <p style={{ color: '#888888', fontSize: 13, margin: 0 }}>
                          This page is only accessible until an admin account has been created.
                          It will become unavailable once setup is complete.
                        </p>
                      </div>
                    </div>

                    <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: '#938575', marginBottom: 10, textTransform: 'uppercase' }}>Full Name</div>

                    {/* First + Middle side by side */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
                      <input
                        className="login-input signup-input"
                        placeholder="First Name"
                        value={form.firstName}
                        onChange={e => setForm(f => ({ ...f, firstName: e.target.value }))}
                        required
                      />
                      <input
                        className="login-input signup-input"
                        placeholder="Middle Name"
                        value={form.middleName}
                        onChange={e => setForm(f => ({ ...f, middleName: e.target.value }))}
                      />
                    </div>
                    {/* Last name full width */}
                    <div className="login-form-group">
                      <input
                        className="login-input signup-input"
                        placeholder="Last Name"
                        value={form.lastName}
                        onChange={e => setForm(f => ({ ...f, lastName: e.target.value }))}
                        required
                      />
                    </div>

                    <button type="submit" className="login-submit-btn" style={{ marginTop: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                      Continue <span>→</span>
                    </button>
                  </>
                ) : (
                  <>
                    {/* Step 2: Credentials */}

                    <h2 style={{ fontFamily: 'Instrument Sans', fontSize: '1.9rem', fontWeight: 700, color: '#1A1A1A', margin: '0 0 6px 0', letterSpacing: '-0.5px', lineHeight: 1.2 }}>
                      Set your credentials
                    </h2>
                    <p style={{ fontFamily: 'Instrument Sans', fontSize: '0.9rem', color: '#888', margin: '0 0 28px 0', fontWeight: 400 }}>
                      Create the admin login details you'll use to sign in.
                    </p>

                    <div className="login-form-group">
                      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: '#938575', marginBottom: 8, textTransform: 'uppercase' }}>Email Address</div>
                      <input className="login-input signup-input" type="email" placeholder="admin@denr.gov.ph" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} required />
                    </div>
                    
                    <div className="login-form-group">
                      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: '#938575', marginBottom: 8, textTransform: 'uppercase' }}>Password</div>
                      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                        <input className="login-input signup-input" style={{ paddingRight: '40px' }} type={showPassword ? 'text' : 'password'} placeholder="Min. 8 chars, 1 uppercase, 1 number" value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} required />
                        <button type="button" onClick={() => setShowPassword(!showPassword)} style={{ position: 'absolute', right: '12px', background: 'none', border: 'none', cursor: 'pointer', color: '#B5B5B5', display: 'flex' }}>
                          {showPassword ? (
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>
                          ) : (
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                          )}
                        </button>
                      </div>
                    </div>
                    
                    <div className="login-form-group">
                      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: '#938575', marginBottom: 8, textTransform: 'uppercase' }}>Confirm Password</div>
                      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                        <input className="login-input signup-input" style={{ paddingRight: '40px' }} type={showConfirmPassword ? 'text' : 'password'} placeholder="Re-enter your password" value={form.confirm} onChange={e => setForm(f => ({ ...f, confirm: e.target.value }))} required />
                        <button type="button" onClick={() => setShowConfirmPassword(!showConfirmPassword)} style={{ position: 'absolute', right: '12px', background: 'none', border: 'none', cursor: 'pointer', color: '#B5B5B5', display: 'flex' }}>
                          {showConfirmPassword ? (
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>
                          ) : (
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                          )}
                        </button>
                      </div>
                    </div>

                    <button type="submit" className="login-submit-btn" disabled={loading} style={{ marginTop: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                      {loading ? 'Creating...' : <><span>Create Admin Account</span><span>→</span></>}
                    </button>
                  </>
                )}
              </form>

              <div className="login-footer-text" style={{ marginTop: '28px', textAlign: 'center' }}>
                Already set up? <Link to="/login" style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }} className="login-footer-link">Sign in</Link>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  )
}
