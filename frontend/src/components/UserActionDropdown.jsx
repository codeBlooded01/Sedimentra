import React, { useState, useRef, useEffect } from 'react';

export default function UserActionDropdown({ actions, busy }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (ref.current && !ref.current.contains(event.target)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="user-action-dropdown" ref={ref} style={{ position: 'relative', display: 'inline-block', minWidth: 100 }}>
      <button
        onClick={() => setOpen(!open)}
        disabled={busy}
        style={{
          background: '#ffffff',
          border: '1px solid #EAEAEA',
          borderRadius: open ? '6px 6px 0 0' : '6px',
          padding: '8px 14px',
          fontSize: 11,
          color: '#A3A3A3',
          cursor: busy ? 'not-allowed' : 'pointer',
          fontFamily: 'Instrument Sans',
          fontWeight: 700,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 6,
          textTransform: 'uppercase',
          boxShadow: '0 1px 2px rgba(0,0,0,0.02)',
          width: '100%',
        }}
      >
        <span>ACTION</span>
        <span style={{ 
          fontSize: 8, 
          transform: open ? 'rotate(180deg)' : 'none', 
          transition: 'transform 0.2s',
          marginTop: 1
        }}>
          ▲
        </span>
      </button>

      {open && (
        <div
          style={{
            position: 'absolute',
            right: 0,
            top: '100%',
            background: '#ffffff',
            border: '1px solid #EAEAEA',
            borderTop: 'none',
            borderRadius: '0 0 6px 6px',
            width: '100%',
            left: 0,
            zIndex: 100,
            display: 'flex',
            flexDirection: 'column',
            boxShadow: '0 4px 12px rgba(0,0,0,0.05)',
            overflow: 'hidden',
          }}
        >
          {actions.map((action, i) => (
            <button
              key={i}
              onClick={() => {
                setOpen(false);
                action.onClick();
              }}
              disabled={action.disabled}
              style={{
                background: '#ffffff',
                border: 'none',
                borderBottom: i !== actions.length - 1 ? '1px solid #F4F4F4' : 'none',
                color: '#A3A3A3',
                padding: '8px 14px',
                textAlign: 'center',
                fontSize: 11,
                fontFamily: 'Instrument Sans',
                fontWeight: 600,
                cursor: action.disabled ? 'not-allowed' : 'pointer',
                opacity: action.disabled ? 0.6 : 1,
                textTransform: 'uppercase',
                transition: 'background 0.2s, color 0.2s',
              }}
              onMouseEnter={(e) => {
                if (!action.disabled) {
                  e.target.style.background = '#F9F9F9';
                  e.target.style.color = '#333';
                }
              }}
              onMouseLeave={(e) => {
                if (!action.disabled) {
                  e.target.style.background = '#ffffff';
                  e.target.style.color = '#A3A3A3';
                }
              }}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
