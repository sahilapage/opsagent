import { useState, useEffect } from 'react';
import { Trash2, RefreshCw, Loader2, Plus, BookOpen } from 'lucide-react';
import { listMemories, deleteMemory, consolidateMemories, memorySummary, storeMemory } from '../api.js';

function ImportanceDots({ score }) {
  const filled = Math.round((score || 0) * 5);
  return (
    <div style={{ display: 'flex', gap: 2, alignItems: 'center' }}>
      {[1,2,3,4,5].map(i => (
        <div key={i} style={{
          width: 5, height: 5, borderRadius: 99,
          background: i <= filled ? '#1a1a1a' : 'var(--border)',
        }} />
      ))}
    </div>
  );
}

function Toast({ msg, type }) {
  return (
    <div className="fade-in" style={{
      position: 'fixed', top: 20, right: 20, zIndex: 999,
      padding: '9px 14px', borderRadius: 7,
      background: type === 'error' ? '#fef2f2' : '#f0fdf4',
      border: `1px solid ${type === 'error' ? '#fca5a5' : '#86efac'}`,
      color: type === 'error' ? '#dc2626' : '#16a34a',
      fontSize: 13, fontWeight: 500,
      boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
    }}>
      {msg}
    </div>
  );
}

export default function Memory({ userId }) {
  const [memories, setMemories] = useState([]);
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const [consolidating, setConsolidating] = useState(false);
  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [showSummary, setShowSummary] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [newMemory, setNewMemory] = useState('');
  const [addLoading, setAddLoading] = useState(false);
  const [toast, setToast] = useState(null);

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 2500);
  };

  const load = async () => {
    setLoading(true);
    try {
      const data = await listMemories(userId);
      setMemories(data.memories || []);
    } catch { showToast('Failed to load', 'error'); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [userId]);

  const handleDelete = async (id) => {
    setDeleting(id);
    try {
      await deleteMemory(id);
      setMemories(prev => prev.filter(m => m.id !== id));
    } catch { showToast('Delete failed', 'error'); }
    finally { setDeleting(null); }
  };

  const handleConsolidate = async () => {
    setConsolidating(true);
    try { await consolidateMemories(userId); showToast('Memories consolidated'); await load(); }
    catch { showToast('Failed', 'error'); }
    finally { setConsolidating(false); }
  };

  const handleSummary = async () => {
    if (showSummary) { setShowSummary(false); return; }
    setSummaryLoading(true);
    try { const d = await memorySummary(userId); setSummary(d.summary); setShowSummary(true); }
    catch { showToast('Summary failed', 'error'); }
    finally { setSummaryLoading(false); }
  };

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!newMemory.trim()) return;
    setAddLoading(true);
    try {
      await storeMemory(userId, newMemory.trim());
      showToast('Stored');
      setNewMemory(''); setShowAdd(false);
      await load();
    } catch { showToast('Failed', 'error'); }
    finally { setAddLoading(false); }
  };

  const sorted = [...memories].sort((a, b) => (b.importance || 0) - (a.importance || 0));

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '32px 24px' }}>
      {toast && <Toast {...toast} />}
      <div style={{ maxWidth: 680, margin: '0 auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 24, gap: 12 }}>
          <div style={{ flex: 1 }}>
            <h2 style={{ margin: '0 0 2px', fontSize: 18, fontWeight: 600, letterSpacing: '-0.01em' }}>Memory</h2>
            <p style={{ margin: 0, color: 'var(--text2)', fontSize: 13 }}>
              {memories.length} memories for {userId}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="btn btn-ghost btn-sm" onClick={load} disabled={loading}>
              {loading ? <Loader2 size={12} className="spin" /> : <RefreshCw size={12} />} Refresh
            </button>
            <button className="btn btn-ghost btn-sm" onClick={handleConsolidate} disabled={consolidating}>
              {consolidating ? <Loader2 size={12} className="spin" /> : null} Consolidate
            </button>
            <button className="btn btn-ghost btn-sm" onClick={handleSummary} disabled={summaryLoading}>
              {summaryLoading ? <Loader2 size={12} className="spin" /> : <BookOpen size={12} />} Summary
            </button>
            <button className="btn btn-primary btn-sm" onClick={() => setShowAdd(s => !s)}>
              <Plus size={12} /> Add
            </button>
          </div>
        </div>

        {showAdd && (
          <div className="fade-in" style={{
            marginBottom: 16, padding: '14px 16px',
            border: '1px solid var(--border)',
            borderRadius: 8, background: 'var(--bg)',
          }}>
            <form onSubmit={handleAdd} style={{ display: 'flex', gap: 8 }}>
              <input
                value={newMemory}
                onChange={e => setNewMemory(e.target.value)}
                placeholder="Enter a fact to remember…"
                autoFocus
                style={{
                  flex: 1, padding: '8px 12px',
                  border: '1px solid var(--border)', borderRadius: 6,
                  background: 'var(--bg)', color: 'var(--text)', fontSize: 13,
                }}
              />
              <button type="submit" className="btn btn-primary btn-sm" disabled={!newMemory.trim() || addLoading}>
                {addLoading ? <Loader2 size={12} className="spin" /> : null} Store
              </button>
            </form>
          </div>
        )}

        {showSummary && summary && (
          <div className="fade-in" style={{
            marginBottom: 16, padding: '14px 16px',
            border: '1px solid var(--border)', borderRadius: 8,
            background: 'var(--bg2)', fontSize: 13, color: 'var(--text2)', lineHeight: 1.7,
          }}>
            {summary}
          </div>
        )}

        {!loading && memories.length === 0 && (
          <div style={{ textAlign: 'center', padding: '64px 0', color: 'var(--text3)' }}>
            <p style={{ margin: '0 0 6px', fontSize: 14, color: 'var(--text2)' }}>No memories yet</p>
            <p style={{ margin: 0, fontSize: 13 }}>Memories are extracted automatically from conversations.</p>
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {sorted.map((mem, i) => (
            <div key={mem.id} className="fade-in" style={{
              display: 'flex', gap: 12, alignItems: 'flex-start',
              padding: '12px 0',
              borderBottom: i < sorted.length - 1 ? '1px solid var(--border)' : 'none',
            }}>
              <ImportanceDots score={mem.importance} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ margin: 0, fontSize: 13, lineHeight: 1.6, color: 'var(--text)' }}>
                  {mem.content}
                </p>
                <div style={{ display: 'flex', gap: 10, marginTop: 4, fontSize: 11, color: 'var(--text3)' }}>
                  {mem.memory_type && <span>{mem.memory_type}</span>}
                  {mem.created_at && <span>{new Date(mem.created_at).toLocaleDateString()}</span>}
                  {mem.access_count > 0 && <span>accessed {mem.access_count}×</span>}
                </div>
              </div>
              <button
                className="btn-icon"
                onClick={() => handleDelete(mem.id)}
                disabled={deleting === mem.id}
                style={{ flexShrink: 0 }}
                title="Delete"
              >
                {deleting === mem.id ? <Loader2 size={12} className="spin" /> : <Trash2 size={12} />}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
