import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

const USER_NAV = [
  { section: 'MAIN' },
  { to: '/dashboard', label: 'Dashboard' },
  { section: 'DATA IMPORT' },
  { to: '/ingest', label: 'Upload Files' },
  { to: '/ingested-data', label: 'Ingested Files' },
]

const ADMIN_NAV = [
  { section: 'ADMINISTRATION' },
  { to: '/admin', label: 'User Management' },
]

export default function AppShell({ children }) {
  const { user, isAdmin, logout } = useAuth()
  const navigate = useNavigate()
  const [showLogoutMenu, setShowLogoutMenu] = useState(false)
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false)
  const nav = isAdmin ? [...USER_NAV, ...ADMIN_NAV] : USER_NAV

  // Compute user initials
  const rawName = user?.full_name || user?.email?.split('@')[0] || 'User'
  const nameParts = rawName.toUpperCase().split(/[\s_]+/)
  const initials = nameParts.length > 1 
    ? `${nameParts[0][0]}${nameParts[nameParts.length - 1][0]}`
    : rawName.substring(0, 2).toUpperCase()
  
  const displayRole = isAdmin ? 'Admin' : (user?.role || 'User').replace(/^\w/, c => c.toUpperCase())

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-badge">Sedimentra</div>
          <p>Genomic Intelligence System</p>
        </div>

        <nav className="sidebar-nav">
          {nav.map((item, i) =>
            item.section ? (
              <div key={i} className="nav-section-label">
                {item.section}
                <div className="nav-section-line" />
              </div>
            ) : (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
              >
                {item.label}
              </NavLink>
            )
          )}
        </nav>

        {user && (
          <div className="sidebar-footer">
            <div className="sidebar-footer-gradient" />
            <div className="sidebar-footer-content" style={{ position: 'relative' }}>
              {showLogoutMenu && (
                <div style={{
                  position: 'absolute',
                  bottom: 'calc(100% + 10px)',
                  left: '0px',
                  background: '#FFFFFF',
                  border: '1px solid #E8E2DC',
                  borderRadius: '14px',
                  boxShadow: '0 8px 24px rgba(93,76,56,0.12)',
                  padding: '6px',
                  zIndex: 10,
                  minWidth: '160px',
                }}>
                  <button
                    onClick={() => { setShowLogoutMenu(false); setShowLogoutConfirm(true); }}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '10px',
                      background: 'transparent', border: 'none',
                      color: '#8B3A3A',
                      fontWeight: 600, padding: '10px 14px',
                      fontSize: 13, cursor: 'pointer',
                      fontFamily: 'Instrument Sans, sans-serif',
                      borderRadius: '10px', width: '100%',
                      textAlign: 'left', whiteSpace: 'nowrap',
                      transition: 'background 0.18s',
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = '#FDF5F5'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
                      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                      <polyline points="16 17 21 12 16 7" />
                      <line x1="21" y1="12" x2="9" y2="12" />
                    </svg>
                    Log Out
                  </button>
                </div>

              )}
              <div 
                className="sidebar-footer-avatar" 
                onClick={() => setShowLogoutMenu(!showLogoutMenu)}
                style={{ cursor: 'pointer' }}
              >
                {initials}
              </div>
              <div className="sidebar-footer-info">
                <div className="sidebar-footer-name">{rawName.split(/[\s_]+/).map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ')}</div>
                <div className="sidebar-footer-role">{displayRole}</div>
              </div>
            </div>
          </div>
        )}
      </aside>

      <main className="main-content">
        <header className="top-bar" />
        {children}
      </main>

      {showLogoutConfirm && (
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: '"Instrument Sans", sans-serif' }}>
          <div style={{ background: '#ffffff', borderRadius: 32, padding: '40px 32px', width: '90%', maxWidth: 340, textAlign: 'center', boxShadow: '0 10px 40px rgba(0,0,0,0.15)' }}>
            <h2 style={{ margin: '0 0 12px', fontSize: 22, fontWeight: 700, color: '#4c4c4c', letterSpacing: '-0.5px' }}>Log out?</h2>
            <p style={{ margin: '0 0 32px', color: '#593e32', fontSize: 14, fontWeight: 400, lineHeight: 1.4 }}>Are you sure you want to end your current session?</p>
            <div style={{ display: 'flex', gap: 8 }}>
              <button 
                onClick={() => setShowLogoutConfirm(false)} 
                style={{ flex: 1, padding: '12px', borderRadius: 30, border: '1px solid #E8E2DC', background: '#F9F7F5', color: '#938575', fontWeight: 700, fontSize: 12, cursor: 'pointer', letterSpacing: '0.5px' }}
              >
                CANCEL
              </button>
              <button 
                onClick={async () => {
                  setShowLogoutConfirm(false);
                  await logout();
                  navigate('/login');
                }} 
                style={{ flex: 1, padding: '12px', borderRadius: 30, border: 'none', background: '#938575', color: '#fff', fontWeight: 700, fontSize: 12, cursor: 'pointer', letterSpacing: '0.5px' }}
              >
                CONFIRM
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
