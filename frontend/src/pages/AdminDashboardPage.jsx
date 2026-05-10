import { useState, useEffect, useCallback } from 'react'
import { adminApi } from '../api/client'
import { useAuth } from '../hooks/useAuth'

const STATUS_TABS = ['all', 'pending', 'approved', 'denied']

function statusOf(user) {
  if (!user.is_active) return 'denied'
  if (user.is_approved) return 'approved'
  return 'pending'
}

import UserActionDropdown from '../components/UserActionDropdown';

function UserRow({ user, isPrimaryAdmin, onApprove, onReject, onTest, onPromote, busy }) {
  const s = statusOf(user);
  
  // Calculate initials: first letter of first word + first letter of second word (if any)
  const words = (user.full_name || user.email).split(/[\s.@]+/);
  const initials = words.length > 1 
    ? (words[0][0] + words[1][0]).toUpperCase()
    : words[0].slice(0, 2).toUpperCase();

  // Build actions for dropdown
  let actions = [];
  if (user.role !== 'admin') {
    if (s !== 'approved') {
      actions.push({
        label: 'Approve',
        onClick: () => onApprove(user.id),
        disabled: busy === user.id,
      });
    }
    if (s !== 'denied') {
      actions.push({
        label: 'Deny',
        onClick: () => onReject(user.id),
        disabled: busy === user.id,
      });
    }
    if (s === 'approved') {
      if (isPrimaryAdmin) {
        actions.push({
          label: 'Promote',
          onClick: () => onPromote(user.id),
          disabled: busy === user.id,
        });
      }
    }
  }

  return (
    <tr style={{ borderBottom: '1px solid #f0f0f0' }}>
      <td style={{ padding: '16px 20px', width: '35%' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{
            width: 38, height: 38, borderRadius: '50%', background: '#A1978C',
            color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 14, fontWeight: 500, fontFamily: 'Instrument Sans'
          }}>
            {initials}
          </div>
          <div>
            <div style={{ color: '#333', fontSize: 14, fontWeight: 600, fontFamily: 'Instrument Sans' }}>
              {(user.full_name || user.email).split(/[\s_]+/).map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ')}
            </div>
            <div style={{ color: '#A3A3A3', fontSize: 12, fontWeight: 400, fontFamily: 'Instrument Sans', marginTop: 2 }}>
              {user.email}
            </div>
          </div>
        </div>
      </td>
      <td style={{ padding: '16px 20px', textAlign: 'center' }}>
        <span style={{ color: '#A3A3A3', fontSize: 11, fontWeight: 600, fontFamily: 'Instrument Sans', textTransform: 'uppercase' }}>
          {s}
        </span>
      </td>
      <td style={{ padding: '16px 20px', textAlign: 'center' }}>
        <span style={{ color: '#A3A3A3', fontSize: 11, fontWeight: 600, fontFamily: 'Instrument Sans', textTransform: 'uppercase' }}>
          {user.role}
        </span>
      </td>
      <td style={{ padding: '16px 20px', textAlign: 'center', color: '#A3A3A3', fontSize: 12, fontFamily: 'Instrument Sans', fontWeight: 500 }}>
        {new Date(user.created_at || Date.now()).toLocaleDateString([], { month: 'numeric', day: 'numeric', year: 'numeric' })}
      </td>
      <td style={{ padding: '16px 20px', textAlign: 'center' }}>
        {user.role !== 'admin' ? (
          actions.length > 0 ? (
            <UserActionDropdown actions={actions} busy={busy === user.id} />
          ) : (
            <span style={{ color: '#A3A3A3', fontSize: 12, fontFamily: 'Instrument Sans' }}>—</span>
          )
        ) : (
          <span style={{ color: '#A3A3A3', fontSize: 12, fontFamily: 'Instrument Sans', fontWeight: 500 }}>PROTECTED</span>
        )}
      </td>
    </tr>
  );
}

export default function AdminDashboardPage() {
  const { user: me } = useAuth()
  const [users, setUsers]   = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState('')
  const [toast, setToast]   = useState('')
  const [busy, setBusy]     = useState(null)
  const [confirmAction, setConfirmAction] = useState(null)
  const [tab, setTab]       = useState('all')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const { data } = await adminApi.listUsers()
      setUsers(data.users)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load users.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const showToast = (msg) => {
    setToast(msg)
    setTimeout(() => setToast(''), 3500)
  }

  const handleApprove = async (id) => {
    setBusy(id)
    try {
      await adminApi.approveUser(id)
      showToast('User approved successfully.')
      await load()
    } catch (err) {
      showToast(err.response?.data?.detail || 'Action failed.')
    } finally {
      setBusy(null)
    }
  }

  const handleReject = async (id) => {
    setBusy(id)
    try {
      await adminApi.rejectUser(id)
      showToast('User denied and deactivated.')
      await load()
    } catch (err) {
      showToast(err.response?.data?.detail || 'Action failed.')
    } finally {
      setBusy(null)
    }
  }

  const handleTestLogin = async (id) => {
    setBusy(id)
    try {
      const { data } = await adminApi.impersonateUser(id)
      // Open new tab with token in hash fragment
      window.open(`/test-session#access=${data.access_token}&refresh=${data.refresh_token}`, '_blank')
    } catch (err) {
      showToast(err.response?.data?.detail || 'Test login failed.')
    } finally {
      setBusy(null)
    }
  }

  const handlePromote = async (id) => {
    if (!window.confirm('Are you sure you want to promote this user to Admin?')) return
    setBusy(id)
    try {
      await adminApi.promoteUser(id)
      showToast('User promoted to admin.')
      await load()
    } catch (err) {
      showToast(err.response?.data?.detail || 'Promotion failed.')
    } finally {
      setBusy(null)
    }
  }

  const filtered = tab === 'all'
    ? users
    : users.filter(u => statusOf(u) === tab)

  const counts = {
    all: users.length,
    pending:  users.filter(u => statusOf(u) === 'pending').length,
    approved: users.filter(u => statusOf(u) === 'approved').length,
    denied: users.filter(u => statusOf(u) === 'denied').length,
  }

  return (
    <div>
      {/* Toast notification */}
      {toast && (
        <div style={{
          position: 'fixed', top: 20, right: 24, zIndex: 999,
          padding: '12px 20px', borderRadius: 8,
          background: 'var(--bg-raised)', border: '1px solid var(--border-lit)',
          color: 'var(--green)', fontFamily: 'var(--mono)', fontSize: 13,
          boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
          animation: 'pulse 0.3s ease',
        }}>
          ✓ {toast}
        </div>
      )}

      <div className="page-header">
        <h2>User Management</h2>
        <p>Administer user permissions and oversee platform access</p>
        <hr className="divider" />
      </div>



      {/* Stats row */}
      <div style={{ display: 'flex', gap: 32, marginBottom: 24, alignItems: 'center' }}>
        {['all', 'pending', 'approved', 'denied'].map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              background: 'none',
              border: 'none',
              borderBottom: tab === t ? '2px solid #9A9A9A' : '2px solid transparent',
              color: tab === t ? '#333' : '#B4B4B4',
              fontFamily: 'Instrument Sans',
              fontSize: 16,
              fontWeight: tab === t ? 700 : 500,
              padding: '0 4px 8px 4px',
              cursor: 'pointer',
              textTransform: 'capitalize',
              transition: 'all 0.2s',
            }}
          >
            {t}
          </button>
        ))}
          
    <button
        onClick={load}
        className="btn btn-ghost"
        style={{ marginLeft: 'auto', marginBottom: 12, padding: '8px 20px', fontSize: 13, fontFamily: 'Instrument Sans', fontWeight: 600 }}
        disabled={loading}
      >
        {loading ? <span className="spinner" style={{ width: 13, height: 13 }} /> : '↻ Refresh'}
      </button>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {error && (
          <div className="auth-error" style={{ margin: 16 }}>{error}</div>
        )}

        {loading && !users.length ? (
          <div style={{ padding: 40, textAlign: 'center' }}>
            <span className="spinner" style={{ width: 24, height: 24 }} />
            <p style={{ marginTop: 12, color: 'var(--text-muted)', fontSize: 13 }}>Loading users…</p>
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: 48, textAlign: 'center' }}>
            <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>
              No {tab === 'all' ? '' : tab} users found.
            </p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['User', 'Status', 'Role', 'Registered', 'Manage'].map((h, i) => (
                  <th key={h} style={{
                    padding: '16px 20px', textAlign: i === 0 ? 'left' : 'center',
                    fontFamily: 'Instrument Sans', fontSize: 11, fontWeight: 700,
                    color: "#9A9A9A", background: '#F9F9F9',
                    textTransform: 'uppercase', letterSpacing: '0.05em'
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map(u => (
                <UserRow
                  key={u.id}
                  user={u}
                  isPrimaryAdmin={me?.is_primary_admin}
                  onApprove={(id) => setConfirmAction({ type: 'approve', id, title: 'Approve User', msg: 'Are you sure you want to approve this user?' })}
                  onReject={(id) => setConfirmAction({ type: 'reject', id, title: 'Deny User', msg: 'Are you sure you want to deny and deactivate this account?' })}
                  onTest={handleTestLogin}
                  onPromote={(id) => setConfirmAction({ type: 'promote', id, title: 'Promote User', msg: 'Are you sure you want to promote this user to admin?' })}
                  busy={busy}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Quick-access note for admins */}
      <div className="alert alert-info" style={{ marginTop: 20 }}>
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#736453" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
        <span style={{ fontSize: 13 }}>
          Newly approved users can log in immediately. Denied users are deactivated and their
          existing sessions are invalidated on the next request.
        </span>
      </div>

      {confirmAction && (
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: '"Instrument Sans", sans-serif' }}>
          <div style={{ background: '#ffffff', borderRadius: 32, padding: '40px 32px', width: '90%', maxWidth: 340, textAlign: 'center', boxShadow: '0 10px 40px rgba(0,0,0,0.15)' }}>
            <h2 style={{ margin: '0 0 12px', fontSize: 22, fontWeight: 700, color: '#4c4c4c', letterSpacing: '-0.5px' }}>{confirmAction.title}</h2>
            <p style={{ margin: '0 0 32px', color: '#593e32', fontSize: 14, fontWeight: 400, lineHeight: 1.4 }}>{confirmAction.msg}</p>
            <div style={{ display: 'flex', gap: 8 }}>
              <button 
                onClick={() => setConfirmAction(null)} 
                style={{ flex: 1, padding: '12px', borderRadius: 30, border: '1px solid #E8E2DC', background: '#F9F7F5', color: '#938575', fontWeight: 700, fontSize: 12, cursor: 'pointer', letterSpacing: '0.5px' }}
              >
                CANCEL
              </button>
              <button 
                onClick={() => {
                  if (confirmAction.type === 'approve') handleApprove(confirmAction.id);
                  if (confirmAction.type === 'reject') handleReject(confirmAction.id);
                  if (confirmAction.type === 'promote') handlePromote(confirmAction.id);
                  setConfirmAction(null);
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
