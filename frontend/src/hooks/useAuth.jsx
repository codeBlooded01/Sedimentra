import { createContext, useContext, useState, useEffect } from 'react'
import { authApi } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const isSession = !!sessionStorage.getItem('access_token')
    const token = isSession ? sessionStorage.getItem('access_token') : localStorage.getItem('access_token')

    if (token) {
      authApi.me()
        .then(r => setUser(r.data))
        .catch(() => {
          if (isSession) sessionStorage.clear()
          else localStorage.clear()
        })
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const login = async (email, password) => {
    const { data } = await authApi.login(email, password)
    localStorage.setItem('access_token',  data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    const me = await authApi.me()
    setUser(me.data)
    return me.data
  }

  const logout = async () => {
    // Call backend logout endpoint for blacklisting
    const token = sessionStorage.getItem('access_token') || localStorage.getItem('access_token')
    if (token) {
      try {
        await fetch('/api/v1/auth/logout', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` },
        })
      } catch {}
    }
    if (sessionStorage.getItem('access_token')) {
      sessionStorage.clear()
    } else {
      localStorage.clear()
    }
    setUser(null)
  }

  const isAdmin = user?.role === 'admin'

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, isAdmin }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
