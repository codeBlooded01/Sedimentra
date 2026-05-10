import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';

// Minimalist Vector Icons (Custom SVG)
const EyeIcon = ({ size = 18 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
    <circle cx="12" cy="12" r="3"></circle>
  </svg>
);

const EyeOffIcon = ({ size = 18 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 2.26-3.93m2.18-1.28A9.88 9.88 0 0 1 12 4c7 0 11 8 11 8a18.47 18.47 0 0 1-2.85 4.06"></path>
    <line x1="1" y1="1" x2="23" y2="23"></line>
  </svg>
);

const CheckIcon = ({ size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="3"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <polyline points="20 6 9 17 4 12"></polyline>
  </svg>
);

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [attemptedSubmit, setAttemptedSubmit] = useState(false);

  // Validation regex patterns
  const validationRules = {
    length: (pwd) => pwd.length >= 8,
    uppercase: (pwd) => /[A-Z]/.test(pwd),
    lowercase: (pwd) => /[a-z]/.test(pwd),
    number: (pwd) => /\d/.test(pwd),
    special: (pwd) => /[!@#$%^&*()_+=\-\[\]{};':"\\|,.<>\/?]/.test(pwd),
    match: (pwd, confirm) => pwd && confirm && pwd === confirm,
  };

  // Check if all requirements are met
  const allRequirementsMet =
    validationRules.length(password) &&
    validationRules.uppercase(password) &&
    validationRules.lowercase(password) &&
    validationRules.number(password) &&
    validationRules.special(password) &&
    validationRules.match(password, confirmPassword);

  // Dynamic input styling based on validation state
  const getPasswordInputStyle = () => {
    let borderColor = '#d1d5db'; // neutral gray
    let boxShadow = 'none';

    if (password) {
      if (attemptedSubmit && !allRequirementsMet) {
        // Error state: high-contrast red with flash animation
        borderColor = '#ef4444';
        boxShadow = '0 0 16px rgba(239, 68, 68, 0.5), inset 0 0 4px rgba(239, 68, 68, 0.2)';
      } else if (allRequirementsMet) {
        // Success state: cinematic emerald green with glow
        borderColor = '#10b981';
        boxShadow = '0 0 16px rgba(16, 185, 129, 0.4), inset 0 0 4px rgba(16, 185, 129, 0.1)';
      }
    }

    return {
      width: '100%',
      padding: '11px 40px 11px 14px',
      borderRadius: 6,
      border: `1.5px solid ${borderColor}`,
      outline: 'none',
      fontSize: 14,
      fontFamily: 'inherit',
      transition: 'all 0.3s ease-in-out',
      boxShadow,
      backgroundColor: '#fff',
    };
  };

  const getHintTextColor = () => {
    if (password) {
      if (attemptedSubmit && !allRequirementsMet) {
        return '#ef4444'; // high-contrast red for error
      } else if (allRequirementsMet) {
        return '#10b981'; // emerald green for success
      }
    }
    return '#9ca3af'; // muted gray for neutral state
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setAttemptedSubmit(true);

    if (!token) {
      setError('Invalid reset link. Please request a new password reset.');
      return;
    }

    if (!allRequirementsMet) {
      setError('Password does not meet all requirements.');
      return;
    }

    setLoading(true);
    try {
      const res = await fetch('/api/v1/auth/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: password }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to reset password');
      }

      setSuccess('Password reset successfully. Redirecting to login...');
      setTimeout(() => window.location.href = '/login', 2000);
    } catch (err) {
      setError(err.message || 'Could not reset password. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'url(/bg_main.png) center/cover no-repeat', fontFamily: '"Instrument Sans", sans-serif', padding: '16px' }}>
      <div style={{ background: '#ffffff', borderRadius: 40, padding: '40px', width: '100%', maxWidth: 460, boxShadow: '0 10px 40px rgba(0,0,0,0.08)' }}>
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
          marginBottom: 32,
          textAlign: 'center'
        }}>
          Sedimentra
        </h2>
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <h1 style={{ margin: '0 0 16px', fontSize: 32, fontWeight: 700, color: '#4c4c4c', letterSpacing: '-0.5px' }}>
            Reset Password
          </h1>
          <p style={{ margin: '0', fontSize: 16, color: '#2b2b2b', fontWeight: 500, lineHeight: 1.4 }}>
            Create a strong, secure password<br />for your account.
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ marginBottom: 20 }}>
          {/* New Password Field */}
          <div style={{ marginBottom: 28 }}>
            <label style={{ display: 'block', fontSize: 15, fontWeight: 700, color: '#494949', marginBottom: 12 }}>
              New Password
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter you new password"
                style={{ ...getPasswordInputStyle(), padding: '16px 40px 16px 16px', borderRadius: 8, border: '1px solid #e0e0e0', fontSize: 15, color: '#333' }}
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: '#c0c0c0' }}
                tabIndex={-1}
              >
                {showPassword ? <EyeIcon size={18} /> : <EyeOffIcon size={18} />}
              </button>
            </div>
            <div style={{ marginTop: 12, fontSize: 13, color: '#b3b3b3', fontWeight: 400, lineHeight: 1.4 }}>
              Password must include at least an uppercase letter, a lowercase letter, a numeric character, and a special symbol.
            </div>
          </div>

          {/* Confirm Password Field */}
          <div style={{ marginBottom: 32 }}>
            <label style={{ display: 'block', fontSize: 15, fontWeight: 700, color: '#494949', marginBottom: 12 }}>
              Confirm New Password
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type={showConfirmPassword ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter your new password"
                style={{ ...getPasswordInputStyle(), padding: '16px 40px 16px 16px', borderRadius: 8, border: '1px solid #e0e0e0', fontSize: 15, color: '#333' }}
                required
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: '#c0c0c0' }}
                tabIndex={-1}
              >
                {showConfirmPassword ? <EyeIcon size={18} /> : <EyeOffIcon size={18} />}
              </button>
            </div>
          </div>

          {/* CTA Button */}
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%', padding: '16px', borderRadius: 30, border: 'none', background: '#938575', color: '#fff', fontWeight: 700, fontSize: 14, cursor: loading ? 'not-allowed' : 'pointer', letterSpacing: '0.5px', opacity: loading ? 0.7 : 1
              }}
            >
              {loading ? 'Updating...' : 'UPDATE PASSWORD'}
            </button>
          </div>
        </form>

        {/* Error Message */}
        {error && (
          <div style={{ marginTop: 16, padding: '12px 14px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 6, fontSize: 14, color: '#7f1d1d', fontWeight: 500, display: 'flex', gap: 8, alignItems: 'flex-start' }}>
            <span>{error}</span>
          </div>
        )}

        {/* Success Message */}
        {success && (
          <div style={{ marginTop: 16, padding: '12px 14px', background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 6, fontSize: 14, color: '#166534', fontWeight: 500, display: 'flex', gap: 8, alignItems: 'flex-start' }}>
            <span>{success}</span>
          </div>
        )}
      </div>
    </div>
  );
}
