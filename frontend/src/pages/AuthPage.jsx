import { useState, useEffect } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { authApi } from '../api/client'
import '../styles/login.css'

export default function AuthPage() {
  const navigate = useNavigate()
  const location = useLocation()
  
  // Determine mode from the current URL path
  const mode = location.pathname.includes('signup') ? 'signup' : 'login'

  const switchMode = (newMode) => {
    navigate(`/${newMode}`, { replace: true })
  }

  // --- LOGIN LOGIC ---
  const { login } = useAuth()
  const [loginForm, setLoginForm] = useState({ email: '', password: '' })
  const [loginError, setLoginError] = useState('')
  const [pending, setPending] = useState(false)
  const [loadingLogin, setLoadingLogin] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  const handleLoginSubmit = async (e) => {
    e.preventDefault()
    setLoginError('')
    setPending(false)
    setLoadingLogin(true)
    try {
      await login(loginForm.email, loginForm.password)
      navigate('/dashboard')
    } catch (err) {
      const detail = err.response?.data?.detail || 'Login failed. Please check your credentials.'
      if (detail.toLowerCase().includes('pending admin approval') ||
          detail.toLowerCase().includes('pending')) {
        setPending(true)
      } else {
        setLoginError(detail)
      }
    } finally {
      setLoadingLogin(false)
    }
  }

  // --- SIGNUP LOGIC ---
  const [signupStep, setSignupStep] = useState(1)
  const [signupForm, setSignupForm] = useState({ firstName: '', middleName: '', lastName: '', email: '', password: '', confirmPassword: '' })
  const [signupError, setSignupError] = useState('')
  const [signupSuccess, setSignupSuccess] = useState(false)
  const [loadingSignup, setLoadingSignup] = useState(false)
  const [showSignupPassword, setShowSignupPassword] = useState(false)
  const [showSignupConfirmPassword, setShowSignupConfirmPassword] = useState(false)

  // Reset steps if we navigate away and back
  useEffect(() => {
    if (mode === 'login') {
      setSignupStep(1)
      setSignupError('')
      setLoginError('')
    }
  }, [mode])

  const handleSignupNext = (e) => {
    e.preventDefault()
    if (!signupForm.firstName.trim() || !signupForm.lastName.trim()) {
      setSignupError('First and Last name are required.')
      return
    }
    setSignupError('')
    setSignupStep(2)
  }

  const handleSignupSubmit = async (e) => {
    e.preventDefault()
    if (signupForm.password !== signupForm.confirmPassword) {
      setSignupError('Passwords do not match.')
      return
    }
    setSignupError('')
    setLoadingSignup(true)
    try {
      const parts = [signupForm.firstName.trim(), signupForm.middleName.trim(), signupForm.lastName.trim()].filter(Boolean)
      const fullName = parts.join(' ')
      await authApi.signup(signupForm.email, signupForm.password, fullName)
      setSignupSuccess(true)
    } catch (err) {
      const detail = err.response?.data?.detail
      if (Array.isArray(detail)) {
        setSignupError(detail.map(d => d.msg).join(' · '))
      } else {
        setSignupError(detail || 'Signup failed.')
      }
    } finally {
      setLoadingSignup(false)
    }
  }

  // Generic Success screen rendering
  if (signupSuccess) return (
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
          Request Submitted
        </h1>
        <p style={{ margin: '0 0 16px', color: '#593e32', fontSize: 16, fontWeight: 500, lineHeight: 1.4 }}>
          Your account request has been submitted for <strong>admin review</strong>.
        </p>
        <p style={{ margin: '0 0 40px', color: '#888', fontSize: 14, fontWeight: 400, lineHeight: 1.5 }}>
          You will be able to log in once an administrator approves your account. This may take some time.
        </p>
        <button
          onClick={() => { setSignupSuccess(false); switchMode('login'); }}
          style={{ display: 'inline-block', padding: '16px 40px', borderRadius: 30, border: 'none', background: '#938575', color: '#fff', fontWeight: 700, fontSize: 14, cursor: 'pointer', letterSpacing: '0.5px' }}
        >
          ← BACK TO LOGIN
        </button>
      </div>
    </div>
  )

  return (
    <div className="login-page-wrapper">
      
      {/* STATIC LEFT PANE (Never unmounts or animates) */}
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

      {/* STATIC RIGHT PANE WRAPPER (Never unmounts) */}
      <div className="login-right-pane">
        <div className="login-form-container">
          
          {/* Pill Toggle */}
          <div className="login-tabs">
            <button onClick={() => switchMode('login')} className={`login-tab ${mode === 'login' ? 'active' : ''}`}>Log In</button>
            <button onClick={() => switchMode('signup')} className={`login-tab ${mode === 'signup' ? 'active' : ''}`}>Create Account</button>
          </div>

          <div className="auth-forms-container">
            
            {/* LOGIN PANEL (Animated overlay) */}
            <div className={`auth-form-panel login-panel ${mode === 'login' ? 'active' : 'hidden'}`}>

              <h2 style={{ fontFamily: 'Instrument Sans', fontSize: '1.9rem', fontWeight: 700, color: '#1A1A1A', margin: '0 0 6px 0', letterSpacing: '-0.5px', lineHeight: 1.2 }}>
                Welcome back
              </h2>
              <p style={{ fontFamily: 'Instrument Sans', fontSize: '0.9rem', color: '#888', margin: '0 0 28px 0', fontWeight: 400 }}>
                Log in to your Sedimentra account.
              </p>

              {pending && (
                <div style={{ background: '#F5F5F5', border: '1px solid #E0E0E0', borderRadius: 8, padding: '12px 14px', marginBottom: 20, display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ color: '#666666', fontSize: 11, fontWeight: 700, marginBottom: 2 }}>ACCOUNT PENDING APPROVAL</div>
                    <p style={{ color: '#888888', fontSize: 13, margin: 0 }}>Your account is awaiting administrator approval.</p>
                  </div>
                </div>
              )}

              {loginError && (
                <div style={{ color: '#D32F2F', background: '#FFEBEE', padding: '10px 14px', borderRadius: '8px', marginBottom: '20px', fontSize: '0.85rem', border: '1px solid #FFCDD2' }}>
                  {loginError}
                </div>
              )}

              <form onSubmit={handleLoginSubmit} style={{ display: 'flex', flexDirection: 'column' }}>
                <div className="login-form-group">
                  <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: '#938575', marginBottom: 8, textTransform: 'uppercase' }}>Email Address</div>
                  <input className="login-input signup-input" type="email" placeholder="email@denr.gov.ph" value={loginForm.email} onChange={e => setLoginForm(f => ({ ...f, email: e.target.value }))} required />
                </div>

                <div className="login-form-group">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: '#938575', textTransform: 'uppercase' }}>Password</div>
                    <Link to="/forgot-password" className="forgot-link">Forgot Password?</Link>
                  </div>
                  <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                    <input className="login-input signup-input" style={{ paddingRight: '40px' }} type={showPassword ? 'text' : 'password'} placeholder="Enter your password" value={loginForm.password} onChange={e => setLoginForm(f => ({ ...f, password: e.target.value }))} required />
                    <button type="button" onClick={() => setShowPassword(!showPassword)} style={{ position: 'absolute', right: '12px', background: 'none', border: 'none', cursor: 'pointer', color: '#B5B5B5', display: 'flex' }}>
                      {showPassword ? (
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>
                      ) : (
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                      )}
                    </button>
                  </div>
                </div>

                <button className="login-submit-btn" type="submit" disabled={loadingLogin}
                  style={{ marginTop: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                  {loadingLogin ? 'Signing in...' : <><span>Sign In</span><span>→</span></>}
                </button>
              </form>

              <div className="login-footer-text" style={{ marginTop: '28px' }}>
                Don't have an account? <button onClick={() => switchMode('signup')} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }} className="login-footer-link">Request Account</button>
              </div>
            </div>

            {/* SIGNUP PANEL (Animated overlay) */}
            <div className={`auth-form-panel signup-panel ${mode === 'signup' ? 'active' : 'hidden'}`}>

              {/* Step Progress Dots + Back button on same row */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                <div style={{ display: 'flex', gap: 6 }}>
                  {[1, 2].map(step => (
                    <div key={step} style={{
                      height: 6,
                      width: signupStep === step ? 28 : 10,
                      borderRadius: 99,
                      background: signupStep === step ? '#938575' : '#D6CEC6',
                      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    }} />
                  ))}
                </div>
                {signupStep === 2 && (
                  <button
                    type="button"
                    onClick={() => setSignupStep(1)}
                    style={{ background: 'none', border: 'none', color: '#999', cursor: 'pointer', fontFamily: 'Instrument Sans', fontSize: '0.85rem', fontWeight: 500, display: 'flex', alignItems: 'center', gap: 4, padding: 0 }}
                  >
                    ← Back
                  </button>
                )}
              </div>

              {signupError && (
                <div style={{ color: '#D32F2F', background: '#FFEBEE', padding: '10px 14px', borderRadius: '8px', marginBottom: '16px', fontSize: '0.85rem', border: '1px solid #FFCDD2' }}>
                  {signupError}
                </div>
              )}

              <form style={{ display: 'flex', flexDirection: 'column' }} onSubmit={signupStep === 1 ? handleSignupNext : handleSignupSubmit}>
                {signupStep === 1 ? (
                  <>
                    {/* Step 1: Name */}
                    <h2 style={{ fontFamily: 'Instrument Sans', fontSize: '1.9rem', fontWeight: 700, color: '#1A1A1A', margin: '0 0 6px 0', letterSpacing: '-0.5px', lineHeight: 1.2 }}>
                      Request Access
                    </h2>
                    <p style={{ fontFamily: 'Instrument Sans', fontSize: '0.9rem', color: '#888', margin: '0 0 28px 0', fontWeight: 400 }}>
                      Account Requests are subject to approval by the system administrator.
                    </p>

                    <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: '#938575', marginBottom: 10, textTransform: 'uppercase' }}>Full Name</div>

                    {/* First + Middle side by side */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
                      <input
                        className="login-input signup-input"
                        placeholder="First Name"
                        value={signupForm.firstName}
                        onChange={e => setSignupForm(f => ({ ...f, firstName: e.target.value }))}
                        required
                      />
                      <input
                        className="login-input signup-input"
                        placeholder="Middle Name"
                        value={signupForm.middleName}
                        onChange={e => setSignupForm(f => ({ ...f, middleName: e.target.value }))}
                      />
                    </div>
                    {/* Last name full width */}
                    <div className="login-form-group">
                      <input
                        className="login-input signup-input"
                        placeholder="Last Name"
                        value={signupForm.lastName}
                        onChange={e => setSignupForm(f => ({ ...f, lastName: e.target.value }))}
                        required
                      />
                    </div>

                    <button type="submit" className="login-submit-btn" style={{ marginTop: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                      Continue <span>→</span>
                    </button>
                  </>
                ) : (
                  <>
                    {/* Step 2: Credentials (Back button is now in the dots row above) */}

                    <h2 style={{ fontFamily: 'Instrument Sans', fontSize: '1.9rem', fontWeight: 700, color: '#1A1A1A', margin: '0 0 6px 0', letterSpacing: '-0.5px', lineHeight: 1.2 }}>
                      Set your credentials
                    </h2>
                    <p style={{ fontFamily: 'Instrument Sans', fontSize: '0.9rem', color: '#888', margin: '0 0 28px 0', fontWeight: 400 }}>
                      Create the login details you'll use to sign in.
                    </p>

                    <div className="login-form-group">
                      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: '#938575', marginBottom: 8, textTransform: 'uppercase' }}>Email Address</div>
                      <input className="login-input signup-input" type="email" placeholder="email@denr.gov.ph" value={signupForm.email} onChange={e => setSignupForm(f => ({ ...f, email: e.target.value }))} required />
                    </div>
                    <div className="login-form-group">
                      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: '#938575', marginBottom: 8, textTransform: 'uppercase' }}>Password</div>
                      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                        <input className="login-input signup-input" style={{ paddingRight: '40px' }} type={showSignupPassword ? 'text' : 'password'} placeholder="Min. 8 characters, 1 uppercase, 1 number" value={signupForm.password} onChange={e => setSignupForm(f => ({ ...f, password: e.target.value }))} required />
                        <button type="button" onClick={() => setShowSignupPassword(!showSignupPassword)} style={{ position: 'absolute', right: '12px', background: 'none', border: 'none', cursor: 'pointer', color: '#B5B5B5', display: 'flex' }}>
                          {showSignupPassword ? (
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
                        <input className="login-input signup-input" style={{ paddingRight: '40px' }} type={showSignupConfirmPassword ? 'text' : 'password'} placeholder="Re-enter your password" value={signupForm.confirmPassword} onChange={e => setSignupForm(f => ({ ...f, confirmPassword: e.target.value }))} required />
                        <button type="button" onClick={() => setShowSignupConfirmPassword(!showSignupConfirmPassword)} style={{ position: 'absolute', right: '12px', background: 'none', border: 'none', cursor: 'pointer', color: '#B5B5B5', display: 'flex' }}>
                          {showSignupConfirmPassword ? (
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>
                          ) : (
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                          )}
                        </button>
                      </div>
                    </div>

                    <button type="submit" className="login-submit-btn" disabled={loadingSignup} style={{ marginTop: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                      {loadingSignup ? 'Creating Account...' : <><span>Create Account</span><span>→</span></>}
                    </button>
                  </>
                )}
              </form>

              <div className="login-footer-text" style={{ marginTop: '28px' }}>
                Already have an account? <button onClick={() => switchMode('login')} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }} className="login-footer-link">Sign in</button>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  )
}
