import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

export default function TestSessionPage() {
  const navigate = useNavigate()

  useEffect(() => {
    // Read tokens from the URL hash part naturally (e.g. #access=xyz&refresh=abc)
    const params = new URLSearchParams(window.location.hash.slice(1))
    const access = params.get('access')
    const refresh = params.get('refresh')

    if (access && refresh) {
      // Isolate this session completely via tab-scoped sessionStorage
      sessionStorage.setItem('access_token', access)
      sessionStorage.setItem('refresh_token', refresh)
      
      // Erase the tokens from the URL for security
      window.history.replaceState(null, '', window.location.pathname)
      
      // Hard redirect to reboot the AuthProvider context
      window.location.href = '/dashboard'
    } else {
      // If someone just arrives here randomly, throw them to login
      navigate('/login')
    }
  }, [navigate])

  return (
    <div style={{ padding: 100, textAlign: 'center', fontFamily: 'var(--mono)', color: 'var(--text-muted)' }}>
      <div className="spinner" style={{ margin: '0 auto 20px', width: 30, height: 30 }} />
      <h2>Initializing Isolated Test Environment...</h2>
      <p style={{ fontSize: 13 }}>Please wait. Do not close this tab.</p>
    </div>
  )
}
