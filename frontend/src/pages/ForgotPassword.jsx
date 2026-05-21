import React, { useState } from 'react';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const res = await fetch('/api/v1/auth/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      if (!res.ok) throw new Error('Failed');
      setSent(true);
    } catch {
      setError('Could not send reset email.');
    }
  };

  return (
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
        <h1 style={{ margin: '0 0 16px', fontSize: 30, fontWeight: 700, color: '#4c4c4c', letterSpacing: '-0.5px' }}>
          Forgot Password?
        </h1>

        {sent ? (
          <div>
            <p style={{ margin: '0 0 40px', color: '#593e32', fontSize: 18, fontWeight: 400, lineHeight: 1.4 }}>
              Check you email for the<br />Reset Password link.
            </p>
            <button
              onClick={() => window.location.href = '/login'}
              style={{ width: '100%', padding: '16px', borderRadius: 30, border: 'none', background: '#938575', color: '#fff', fontWeight: 700, fontSize: 14, cursor: 'pointer', letterSpacing: '0.5px' }}
            >
              CLOSE
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <p style={{ margin: '0 0 32px', color: '#2b2b2b', fontSize: 16, fontWeight: 500, lineHeight: 1.4 }}>
              We will send you the updated<br />instructions shortly.
            </p>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              placeholder="Enter your email address."
              style={{ width: '100%', padding: '16px', borderRadius: 8, border: '1px solid #e0e0e0', marginBottom: 24, fontSize: 15, outline: 'none', fontFamily: 'inherit', color: '#333' }}
            />
            <button
              type="submit"
              style={{ width: '100%', padding: '16px', borderRadius: 30, border: 'none', background: '#938575', color: '#fff', fontWeight: 700, fontSize: 14, cursor: 'pointer', letterSpacing: '0.5px' }}
            >
              RESET PASSWORD
            </button>
            {error && <div style={{ marginTop: 12, color: '#dc2626', fontSize: 14 }}>{error}</div>}
          </form>
        )}
      </div>
    </div>
  );
}
