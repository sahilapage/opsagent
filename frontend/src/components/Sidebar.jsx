import { MessageSquare, Database, Brain, CheckSquare, Settings } from 'lucide-react';

const NAV = [
  { id: 'chat',      label: 'Chat',           icon: MessageSquare },
  { id: 'ingest',    label: 'Knowledge Base', icon: Database },
  { id: 'memory',    label: 'Memory',         icon: Brain },
  { id: 'approvals', label: 'Approvals',      icon: CheckSquare },
  { id: 'settings',  label: 'Settings',       icon: Settings },
];

export default function Sidebar({ view, setView, pendingCount }) {
  return (
    <div style={{
      width: 240,
      minWidth: 240,
      background: 'var(--bg2)',
      borderRight: '1px solid var(--border)',
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
    }}>
      <div style={{ padding: '20px 16px 16px' }}>
        <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text)', letterSpacing: '-0.01em' }}>
          OpsAgent
        </div>
        <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 2 }}>Autonomous AI</div>
      </div>

      <nav style={{ flex: 1, padding: '4px 8px', display: 'flex', flexDirection: 'column', gap: 1 }}>
        {NAV.map(({ id, label, icon: Icon }) => {
          const active = view === id;
          const hasBadge = id === 'approvals' && pendingCount > 0;
          return (
            <button
              key={id}
              onClick={() => setView(id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 9,
                padding: '8px 10px',
                borderRadius: 6,
                background: active ? '#fff' : 'transparent',
                color: active ? 'var(--text)' : 'var(--text2)',
                fontWeight: active ? 500 : 400,
                fontSize: 13,
                border: active ? '1px solid var(--border)' : '1px solid transparent',
                cursor: 'pointer',
                width: '100%',
                textAlign: 'left',
                boxShadow: active ? '0 1px 2px rgba(0,0,0,0.04)' : 'none',
                transition: 'all 0.1s',
              }}
              onMouseEnter={e => {
                if (!active) { e.currentTarget.style.background = '#fff'; e.currentTarget.style.color = 'var(--text)'; }
              }}
              onMouseLeave={e => {
                if (!active) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text2)'; }
              }}
            >
              <Icon size={14} strokeWidth={active ? 2 : 1.75} />
              <span style={{ flex: 1 }}>{label}</span>
              {hasBadge && (
                <span style={{
                  background: '#fef3c7',
                  color: '#92400e',
                  border: '1px solid #fde68a',
                  borderRadius: 99,
                  fontSize: 10,
                  fontWeight: 600,
                  minWidth: 17,
                  height: 17,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '0 4px',
                }}>
                  {pendingCount}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)' }}>
        <div style={{ fontSize: 11, color: 'var(--text3)', lineHeight: 1.6 }}>
          Groq · LangGraph · Qdrant
        </div>
      </div>
    </div>
  );
}
