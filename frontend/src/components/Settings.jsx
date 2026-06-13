import { useState, useEffect } from 'react';
import { Save, CheckCircle2, XCircle, Loader2, Activity } from 'lucide-react';
import { healthCheck } from '../api.js';

const AGENTS = [
  { id: 'rag',      label: 'RAG',      desc: 'Hybrid retrieval (dense + BM25 + reranking) over your knowledge base.' },
  { id: 'analysis', label: 'Analysis', desc: 'LLM reasoning for math, statistics, and data analysis.' },
  { id: 'browser',  label: 'Browser',  desc: 'Web search via Serper API + headless Playwright scraping.' },
  { id: 'action',   label: 'Action',   desc: 'Gmail, Google Calendar, Drive. Requires HITL approval for writes.' },
  { id: 'github',   label: 'GitHub',   desc: 'Issues, PRs, commits, auto-fix. HITL approval for destructive ops.' },
  { id: 'code',     label: 'Code',     desc: 'Generates and executes Python in a sandbox. Supports matplotlib.' },
  { id: 'general',  label: 'General',  desc: 'Fallback for world knowledge, conversations, and general questions.' },
];

const STACK = ['Groq LLM', 'LangGraph', 'LangChain', 'Qdrant', 'fastembed', 'pgvector', 'FastAPI', 'Whisper', 'Playwright', 'LangSmith'];

export default function Settings({ userId, setUserId }) {
  const [inputId, setInputId] = useState(userId);
  const [saved, setSaved] = useState(false);
  const [health, setHealth] = useState(null);
  const [healthLoading, setHealthLoading] = useState(false);

  const save = () => {
    const trimmed = inputId.trim() || 'default';
    setUserId(trimmed);
    localStorage.setItem('opsagent_user_id', trimmed);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const checkHealth = async () => {
    setHealthLoading(true);
    try { setHealth({ ok: true, ...(await healthCheck()) }); }
    catch (e) { setHealth({ ok: false, error: e.message }); }
    finally { setHealthLoading(false); }
  };

  useEffect(() => { checkHealth(); }, []);

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '32px 24px' }}>
      <div style={{ maxWidth: 580, margin: '0 auto' }}>
        <div style={{ marginBottom: 28 }}>
          <h2 style={{ margin: '0 0 2px', fontSize: 18, fontWeight: 600, letterSpacing: '-0.01em' }}>Settings</h2>
          <p style={{ margin: 0, color: 'var(--text2)', fontSize: 13 }}>Configure your OpsAgent instance.</p>
        </div>

        {/* User ID */}
        <section style={{ marginBottom: 28 }}>
          <h3 style={{ margin: '0 0 4px', fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>User identity</h3>
          <p style={{ margin: '0 0 10px', fontSize: 12, color: 'var(--text3)' }}>
            Used for memory, conversation history, and personalization.
          </p>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              value={inputId}
              onChange={e => setInputId(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && save()}
              placeholder="default"
              style={{
                flex: 1, padding: '8px 12px',
                border: '1px solid var(--border)', borderRadius: 6,
                background: 'var(--bg)', color: 'var(--text)', fontSize: 13,
              }}
            />
            <button className="btn btn-primary btn-sm" onClick={save}>
              {saved ? <CheckCircle2 size={12} /> : <Save size={12} />}
              {saved ? 'Saved' : 'Save'}
            </button>
          </div>
        </section>

        <div style={{ borderTop: '1px solid var(--border)', marginBottom: 28 }} />

        {/* Health */}
        <section style={{ marginBottom: 28 }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 10, gap: 8 }}>
            <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>System health</h3>
            <button className="btn btn-ghost btn-sm" onClick={checkHealth} disabled={healthLoading} style={{ marginLeft: 'auto' }}>
              {healthLoading ? <Loader2 size={12} className="spin" /> : <Activity size={12} />} Check
            </button>
          </div>
          {health ? (
            <div style={{ display: 'flex', gap: 16, fontSize: 13, flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                {health.ok
                  ? <CheckCircle2 size={13} color="var(--success)" />
                  : <XCircle size={13} color="var(--err)" />
                }
                <span style={{ color: health.ok ? 'var(--success)' : 'var(--err)' }}>
                  API {health.ok ? 'online' : 'offline'}
                </span>
              </div>
              {health.qdrant && (
                <span style={{ color: 'var(--text2)' }}>Qdrant: {health.qdrant}</span>
              )}
              {!health.ok && health.error && (
                <span style={{ color: 'var(--err)', fontSize: 12 }}>{health.error}</span>
              )}
            </div>
          ) : (
            <span style={{ fontSize: 13, color: 'var(--text3)' }}>Checking…</span>
          )}
        </section>

        <div style={{ borderTop: '1px solid var(--border)', marginBottom: 28 }} />

        {/* Agents */}
        <section style={{ marginBottom: 28 }}>
          <h3 style={{ margin: '0 0 12px', fontSize: 13, fontWeight: 600 }}>Agents</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {AGENTS.map((a, i) => (
              <div key={a.id} style={{
                display: 'flex', gap: 12, padding: '10px 0',
                borderBottom: i < AGENTS.length - 1 ? '1px solid var(--border)' : 'none',
              }}>
                <div style={{ width: 70, flexShrink: 0 }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>{a.label}</span>
                </div>
                <p style={{ margin: 0, fontSize: 12, color: 'var(--text2)', lineHeight: 1.6 }}>{a.desc}</p>
              </div>
            ))}
          </div>
        </section>

        <div style={{ borderTop: '1px solid var(--border)', marginBottom: 28 }} />

        {/* Stack */}
        <section>
          <h3 style={{ margin: '0 0 10px', fontSize: 13, fontWeight: 600 }}>Stack</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {STACK.map(t => (
              <span key={t} style={{
                padding: '3px 9px', borderRadius: 99,
                background: 'var(--bg2)', border: '1px solid var(--border)',
                fontSize: 12, color: 'var(--text2)',
              }}>
                {t}
              </span>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
