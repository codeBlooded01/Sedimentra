import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import './UserDropdown.css';

export default function UserDropdown() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const handleLogout = async () => {
    // Call backend logout endpoint
    try {
      await fetch('/api/v1/auth/logout', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token') || sessionStorage.getItem('access_token')}`,
        },
      });
    } catch {}
    logout();
    navigate('/login');
  };

  const handleSwitchAccount = () => {
    logout();
    navigate('/login');
  };

  const handleResetPassword = () => {
    navigate('/settings/security');
  };

  return (
    <div className="user-dropdown">
      <button className="user-dropdown-btn" onClick={() => setOpen(!open)}>
        {user?.full_name || user?.email}
        <span className="dropdown-arrow">▼</span>
      </button>
      {open && (
        <div className="user-dropdown-menu">
          <button onClick={handleResetPassword}>Reset Password</button>
          <button onClick={handleSwitchAccount}>Switch Account</button>
          <button onClick={handleLogout}>Logout</button>
        </div>
      )}
    </div>
  );
}
