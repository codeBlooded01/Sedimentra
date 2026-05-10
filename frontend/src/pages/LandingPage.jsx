import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import '../styles/landing.css'

export default function LandingPage() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span className="spinner" style={{ width: 28, height: 28 }} />
      </div>
    )
  }



  return (
    <div className="landing-container">
      <nav className="landing-nav">
        <div className="landing-logo">Sedimentra</div>
        <div className="landing-nav-links">
          <Link to="/login" className="landing-login">LOG IN</Link>
          <Link to="/signup" className="landing-signup">SIGN UP</Link>
        </div>
      </nav>

      <main className="landing-main">
        <h1 className="landing-title">Sedimentra</h1>
        <p className="landing-subtitle">
          This system transforms hidden microbial signals into early warnings <br />
          by detecting imbalance and predicting disturbance in coastal <br />
          ecosystems through genomic intelligence.
        </p>
      </main>
    </div>
  )
}
