import { useState, useEffect, useCallback } from 'react';
import { CheckCircle2, XCircle, RefreshCw, Loader2 } from 'lucide-react';
import { getPending, approveAction, rejectAction } from '../api.js';

export default function Approvals({ onPendingChange }) {
  const [pendingIds, setPendingIds] = useState([]);
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(null);
  const [results, setResults] = useState([]);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const data = await getPending();
      const ids = data.pending || [];
      setPendingIds(ids);
      onPendingChange?.(ids.length);
    } catch {}
    finally { if (!silent) setLoading(false); }
  }, [onPendingChange]);

  useEffect(() => {
    load();
    const t = setInterval(() => load(true), 15000);
    return () => clearInterval(t);
  }, [load]);

  const handleApprove = async (traceId) => {
    setProcessing(traceId);
    try {
      const res = await approveAction(traceId);
      setResults(prev => [...prev, { id: Date.now(), type: 'success', msg: `Approved ${traceId.slice(0,8)}…`, detail: res.result }]);
      setPendingIds(prev => prev.filter(id => id !== traceId));
      onPendingChange?.(pendingIds.length - 1);
    } catch (e) {
      setResults(prev => [...prev, { id: Date.now(), type: 'error', msg: 'Approval failed', detail: e.response?.data?.detail || e.message }]);
    } finally { setProcessing(null); }
  };

  const handleReject = async (traceId) => {
    setProcessing(traceId);
    try {
      await rejectAction(traceId);
      setResults(prev => [...prev, { id: Date.now(), type: 'success', msg: `Rejected ${traceId.slice(0,8)}…` }]);
      setPendingIds(prev => prev.filter(id => id !== traceId));
      onPendingChange?.(pendingIds.length - 1);
    } catch (e) {
      setResults(prev => [...prev, { id: Date.now(), type: 'error', msg: 'Rejection failed' }]);
    } finally { setProcessing(null); }
  };

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '32px 24px' }}>
      <div style={{ maxWidth: 640, margin: '0 auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 24, gap: 12 }}>
          <div style={{ flex: 1 }}>
            <h2 style={{ margin: '0 0 2px', fontSize: 18, fontWeight: 600, letterSpacing: '-0.01em' }}>Approvals</h2>
            <p style={{ margin: 0, color: 'var(--text2)', fontSize: 13 }}>
              Actions that send emails, create events, or modify GitHub require your approval.
            </p>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={() => load()} disabled={loading}>
            {loading ? <Loader2 size={12} className="spin" /> : <RefreshCw size={12} />} Refresh
          </button>
        </div>

        {pendingIds.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '64px 0', color: 'var(--text3)' }}>
            <CheckCircle2 size={28} style={{ margin: '0 auto 12px', display: 'block', color: 'var(--border2)' }} />
            <p style={{ margin: '0 0 4px', fontSize: 14, color: 'var(--text2)' }}>No pending approvals</p>
            <p style={{ margin: 0, fontSize: 13 }}>Actions will appear here automatically. Refreshes every 15s.</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 24 }}>
            <div style={{ fontSize: 12, color: 'var(--text2)', fontWeight: 500 }}>
              {pendingIds.length} action{pendingIds.length > 1 ? 's' : ''} awaiting approval
            </div>
            {pendingIds.map(id => {
              const isProc = processing === id;
              return (
                <div key={id} className="fade-in" style={{
                  padding: '14px 16px',
                  border: '1px solid #fde68a',
                  borderRadius: 8,
                  background: '#fffbeb',
                  display: 'flex', gap: 14, alignItems: 'center',
                }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: '#92400e', marginBottom: 3 }}>
                      Action pending approval
                    </div>
                    <div style={{ fontSize: 11, fontFamily: 'monospace', color: '#b45309' }}>
                      {id.slice(0, 16)}…
                    </div>
                    <div style={{ fontSize: 12, color: '#b45309', marginTop: 3 }}>
                      Review the chat for details about what will happen.
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => handleReject(id)}
                      disabled={isProc}
                    >
                      {isProc ? <Loader2 size={12} className="spin" /> : <XCircle size={12} />} Reject
                    </button>
                    <button
                      className="btn btn-success btn-sm"
                      onClick={() => handleApprove(id)}
                      disabled={isProc}
                    >
                      {isProc ? <Loader2 size={12} className="spin" /> : <CheckCircle2 size={12} />} Approve
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {results.length > 0 && (
          <div>
            <div style={{ fontSize: 11, color: 'var(--text3)', fontWeight: 600, letterSpacing: '0.05em', marginBottom: 8 }}>
              HISTORY
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {[...results].reverse().slice(0, 10).map(r => (
                <div key={r.id} style={{
                  padding: '8px 12px',
                  background: r.type === 'success' ? '#f0fdf4' : '#fef2f2',
                  border: `1px solid ${r.type === 'success' ? '#86efac' : '#fca5a5'}`,
                  borderRadius: 6, fontSize: 12,
                  color: r.type === 'success' ? '#15803d' : '#dc2626',
                }}>
                  {r.msg}
                  {r.detail && typeof r.detail === 'string' && (
                    <span style={{ color: 'var(--text2)', marginLeft: 8 }}>{r.detail.slice(0, 80)}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
