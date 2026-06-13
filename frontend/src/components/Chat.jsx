import { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Send, Trash2, Copy, Check, Loader2, ArrowDown } from 'lucide-react';
import { runAgent, createStreamSource } from '../api.js';

const AGENT_LABELS = {
  rag: 'RAG', analysis: 'Analysis', browser: 'Browser',
  action: 'Action', github: 'GitHub', code: 'Code',
  general: 'General', planner: 'Planner', blocked: 'Blocked',
};

function AgentTag({ agent }) {
  if (!agent || agent === 'general') return null;
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      padding: '1px 7px',
      borderRadius: 99,
      fontSize: 11,
      fontWeight: 500,
      background: 'var(--bg3)',
      border: '1px solid var(--border)',
      color: 'var(--text2)',
    }}>
      {AGENT_LABELS[agent] || agent}
    </span>
  );
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
      style={{
        position: 'absolute', top: 8, right: 8,
        padding: '3px 7px', borderRadius: 5, fontSize: 11,
        background: 'var(--bg)', border: '1px solid var(--border)',
        color: 'var(--text2)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4,
      }}
    >
      {copied ? <Check size={11} /> : <Copy size={11} />}
      {copied ? 'Copied' : 'Copy'}
    </button>
  );
}

function Message({ msg }) {
  const isUser = msg.role === 'user';

  if (isUser) {
    return (
      <div className="fade-in" style={{ display: 'flex', justifyContent: 'flex-end', padding: '4px 0' }}>
        <div style={{
          maxWidth: '75%',
          background: 'var(--bg3)',
          border: '1px solid var(--border)',
          borderRadius: '16px 16px 4px 16px',
          padding: '10px 14px',
          fontSize: 14,
          lineHeight: 1.6,
          color: 'var(--text)',
          whiteSpace: 'pre-wrap',
        }}>
          {msg.content}
        </div>
      </div>
    );
  }

  return (
    <div className="fade-in" style={{ padding: '4px 0' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>OpsAgent</span>
        <AgentTag agent={msg.agentUsed} />
        {msg.streaming && (
          <span style={{ fontSize: 11, color: 'var(--text3)' }}>streaming…</span>
        )}
      </div>
      <div className="prose" style={{ maxWidth: '85%' }}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            code({ node, inline, className, children, ...props }) {
              const code = String(children).replace(/\n$/, '');
              if (inline) return <code {...props}>{children}</code>;
              return (
                <div style={{ position: 'relative' }}>
                  <pre><code {...props}>{code}</code></pre>
                  <CopyButton text={code} />
                </div>
              );
            },
          }}
        >
          {msg.content || (msg.streaming ? '…' : '')}
        </ReactMarkdown>
      </div>
      {msg.chartB64 && (
        <img
          src={`data:image/png;base64,${msg.chartB64}`}
          alt="Generated chart"
          style={{ marginTop: 12, maxWidth: '85%', borderRadius: 6, border: '1px solid var(--border)' }}
        />
      )}
      {msg.traceId && msg.needsApproval && (
        <div style={{
          marginTop: 8, display: 'inline-flex', alignItems: 'center', gap: 8,
          padding: '7px 12px',
          background: '#fffbeb', border: '1px solid #fde68a',
          borderRadius: 7, fontSize: 12, color: '#92400e',
        }}>
          <span>Action waiting for approval</span>
          <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#b45309' }}>
            {msg.traceId.slice(0, 8)}…
          </span>
          <span>→ Approvals tab</span>
        </div>
      )}
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="fade-in" style={{ padding: '4px 0' }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)', marginBottom: 8 }}>OpsAgent</div>
      <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
        {[0, 150, 300].map(d => (
          <span key={d} style={{
            width: 6, height: 6, borderRadius: '50%',
            background: 'var(--border2)',
            display: 'inline-block',
            animation: `pulse 1.2s ${d}ms infinite`,
          }} />
        ))}
      </div>
    </div>
  );
}

const SUGGESTIONS = [
  'What can you help me with?',
  'Search the web for latest AI news',
  'Write and run a Python fibonacci script',
  'List my recent GitHub issues',
];

export default function Chat({ userId }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [streamMode, setStreamMode] = useState(false);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const bottomRef = useRef(null);
  const listRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  useEffect(() => { scrollToBottom(); }, [messages]);

  const handleScroll = () => {
    const el = listRef.current;
    if (!el) return;
    setShowScrollBtn(el.scrollHeight - el.scrollTop - el.clientHeight > 200);
  };

  const now = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  const sendMessage = useCallback(async (text) => {
    const task = (text || input).trim();
    if (!task || loading) return;
    setInput('');
    setLoading(true);

    setMessages(prev => [...prev, { id: Date.now(), role: 'user', content: task, time: now() }]);

    if (streamMode) {
      const assistantId = Date.now() + 1;
      setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '', streaming: true, time: now() }]);
      let fullContent = '';

      const es = createStreamSource(task, userId);
      es.onmessage = (e) => {
        if (e.data === '[DONE]') {
          es.close();
          setLoading(false);
          setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, content: fullContent, streaming: false } : m));
          return;
        }
        if (e.data.startsWith('[CONTEXT]')) return;
        fullContent += e.data;
        setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, content: fullContent } : m));
      };
      es.onerror = () => {
        es.close();
        setLoading(false);
        setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, content: fullContent || 'Stream error.', streaming: false } : m));
      };
    } else {
      try {
        const res = await runAgent(task, userId);
        const answerText = res.answer || res.result || JSON.stringify(res);
        const hasApproval = answerText.toLowerCase().includes('approval') || answerText.toLowerCase().includes('approve');
        setMessages(prev => [...prev, {
          id: Date.now() + 1,
          role: 'assistant',
          content: answerText,
          agentUsed: res.agent_used,
          traceId: res.trace_id,
          needsApproval: hasApproval && res.trace_id,
          chartB64: res.chart_b64,
          time: now(),
        }]);
      } catch (err) {
        const detail = err.response?.data?.detail;
        const errMsg = !detail ? err.message
          : typeof detail === 'string' ? detail
          : Array.isArray(detail) ? detail.map(d => d.msg || JSON.stringify(d)).join('; ')
          : JSON.stringify(detail);
        setMessages(prev => [...prev, { id: Date.now() + 1, role: 'assistant', content: `Error: ${errMsg}`, time: now() }]);
      } finally {
        setLoading(false);
      }
    }
    inputRef.current?.focus();
  }, [input, loading, streamMode, userId]);

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', background: 'var(--bg)' }}>
      {/* Header */}
      <div style={{
        padding: '12px 24px',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 12,
        background: 'var(--bg)',
        flexShrink: 0,
      }}>
        <div style={{ flex: 1, fontSize: 13, color: 'var(--text2)' }}>
          {userId} · {messages.length} messages
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', userSelect: 'none' }}>
          <span style={{ fontSize: 12, color: 'var(--text2)' }}>Stream</span>
          <div
            onClick={() => setStreamMode(s => !s)}
            style={{
              width: 32, height: 18, borderRadius: 99,
              background: streamMode ? '#1a1a1a' : 'var(--border2)',
              position: 'relative', cursor: 'pointer', transition: 'background 0.15s',
            }}
          >
            <div style={{
              width: 12, height: 12, borderRadius: 99, background: '#fff',
              position: 'absolute', top: 3, left: streamMode ? 17 : 3,
              transition: 'left 0.15s',
            }} />
          </div>
        </label>
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => setMessages([])}
          style={{ gap: 5 }}
        >
          <Trash2 size={12} /> Clear
        </button>
      </div>

      {/* Messages */}
      <div
        ref={listRef}
        onScroll={handleScroll}
        style={{ flex: 1, overflowY: 'auto', padding: '0 24px', position: 'relative' }}
      >
        <div style={{ maxWidth: 720, margin: '0 auto', paddingBottom: 24 }}>
          {messages.length === 0 ? (
            <div style={{ padding: '64px 0 32px', textAlign: 'center' }}>
              <h2 style={{ margin: '0 0 8px', fontSize: 22, fontWeight: 600, color: 'var(--text)', letterSpacing: '-0.02em' }}>
                How can I help you?
              </h2>
              <p style={{ margin: '0 0 32px', color: 'var(--text2)', fontSize: 14 }}>
                Search the web, run code, manage GitHub, send emails, query documents.
              </p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
                {SUGGESTIONS.map(s => (
                  <button
                    key={s}
                    onClick={() => sendMessage(s)}
                    style={{
                      padding: '8px 14px', borderRadius: 99,
                      background: 'var(--bg)', border: '1px solid var(--border)',
                      color: 'var(--text2)', fontSize: 13, cursor: 'pointer',
                      transition: 'all 0.1s',
                    }}
                    onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg3)'; e.currentTarget.style.color = 'var(--text)'; e.currentTarget.style.borderColor = 'var(--border2)'; }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'var(--bg)'; e.currentTarget.style.color = 'var(--text2)'; e.currentTarget.style.borderColor = 'var(--border)'; }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ paddingTop: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
              {messages.map(msg => <Message key={msg.id} msg={msg} />)}
              {loading && !streamMode && <TypingIndicator />}
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {showScrollBtn && (
        <button
          onClick={scrollToBottom}
          style={{
            position: 'absolute', bottom: 90, right: 32,
            width: 30, height: 30, borderRadius: 99,
            background: 'var(--bg)', border: '1px solid var(--border)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 2px 8px rgba(0,0,0,0.08)', cursor: 'pointer',
          }}
        >
          <ArrowDown size={14} color="var(--text2)" />
        </button>
      )}

      {/* Input */}
      <div style={{
        padding: '12px 24px 16px',
        borderTop: '1px solid var(--border)',
        background: 'var(--bg)',
        flexShrink: 0,
      }}>
        <div style={{ maxWidth: 720, margin: '0 auto' }}>
          <div
            style={{
              display: 'flex', gap: 0, alignItems: 'flex-end',
              background: 'var(--bg)',
              border: '1px solid var(--border2)',
              borderRadius: 12,
              padding: '8px 8px 8px 16px',
              boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
              transition: 'border-color 0.1s, box-shadow 0.1s',
            }}
            onFocusCapture={e => { e.currentTarget.style.borderColor = '#a0a0a0'; e.currentTarget.style.boxShadow = '0 1px 6px rgba(0,0,0,0.08)'; }}
            onBlurCapture={e => { e.currentTarget.style.borderColor = 'var(--border2)'; e.currentTarget.style.boxShadow = '0 1px 4px rgba(0,0,0,0.04)'; }}
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Message OpsAgent…"
              disabled={loading}
              rows={1}
              style={{
                flex: 1, resize: 'none', background: 'transparent',
                padding: '4px 0', lineHeight: 1.6, fontSize: 14,
                maxHeight: 140, overflowY: 'auto',
                border: 'none', color: 'var(--text)',
              }}
              onInput={e => {
                e.target.style.height = 'auto';
                e.target.style.height = Math.min(e.target.scrollHeight, 140) + 'px';
              }}
            />
            <button
              onClick={() => sendMessage()}
              disabled={!input.trim() || loading}
              style={{
                width: 34, height: 34, borderRadius: 8, flexShrink: 0,
                background: input.trim() && !loading ? 'var(--text)' : 'var(--bg3)',
                border: 'none',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                cursor: input.trim() && !loading ? 'pointer' : 'not-allowed',
                transition: 'background 0.1s',
              }}
            >
              {loading
                ? <Loader2 size={15} color="var(--text2)" style={{ animation: 'spin 0.7s linear infinite' }} />
                : <Send size={14} color={input.trim() ? '#fff' : 'var(--text3)'} />
              }
            </button>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 6, textAlign: 'center' }}>
            Enter to send · Shift+Enter for newline
          </div>
        </div>
      </div>
    </div>
  );
}
