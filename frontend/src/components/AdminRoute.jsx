import { Navigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

/**
 * Route guard that only allows users with role="admin".
 * Non-authenticated users → /login
 * Authenticated non-admin users → /dashboard
 */
export default function AdminRoute({ children }) {
  const { user, loading } = useAuth()

  if (loading) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <span className="spinner" style={{ width: 28, height: 28 }} />
    </div>
  )

  if (!user) return <Navigate to="/login" replace />

  if (user.role !== 'admin') return <Navigate to="/dashboard" replace />

  return children
}
