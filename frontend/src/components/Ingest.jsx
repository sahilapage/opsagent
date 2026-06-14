import { useState, useRef, useEffect, useCallback } from 'react';
import { Upload, Link, FileText, FileSpreadsheet, Loader2, RefreshCw, Database, CheckCircle2, XCircle, Trash2 } from 'lucide-react';
import { ingestPDF, ingestCSV, ingestURL, listCollections, listDocuments, deleteDocument } from '../api.js';

function DropZone({ accept, onFile, loading, label, icon: Icon }) {
  const [dragOver, setDragOver] = useState(false);
  const ref = useRef();

  return (
    <div
      onClick={() => !loading && ref.current.click()}
      onDragOver={e => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={e => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files[0]; if (f) onFile(f); }}
      style={{
        border: `1.5px dashed ${dragOver ? 'var(--text)' : 'var(--border2)'}`,
        borderRadius: 10,
        padding: '36px 24px',
        textAlign: 'center',
        cursor: loading ? 'not-allowed' : 'pointer',
        background: dragOver ? 'var(--bg3)' : 'var(--bg2)',
        transition: 'all 0.12s',
        opacity: loading ? 0.7 : 1,
      }}
    >
      <input ref={ref} type="file" accept={accept} style={{ display: 'none' }} onChange={e => onFile(e.target.files[0])} />
      {loading
        ? <Loader2 size={24} style={{ margin: '0 auto 10px', display: 'block', color: 'var(--text2)', animation: 'spin 0.7s linear infinite' }} />
        : <Icon size={24} style={{ margin: '0 auto 10px', display: 'block', color: 'var(--text3)' }} />
      }
      <div style={{ color: 'var(--text2)', fontWeight: 500, fontSize: 13 }}>
        {loading ? 'Uploading…' : label}
      </div>
      <div style={{ color: 'var(--text3)', fontSize: 12, marginTop: 3 }}>
        {loading ? 'Please wait' : 'Click or drag & drop'}
      </div>
    </div>
  );
}

function Result({ result, indexed }) {
  if (!result) return null;
  const ok = result.status === 'success' || result.status === 'ok';
  return (
    <div style={{
      marginTop: 12, padding: '10px 14px',
      background: ok ? '#f0fdf4' : '#fef2f2',
      border: `1px solid ${ok ? '#86efac' : '#fca5a5'}`,
      borderRadius: 7, fontSize: 13,
    }}>
      {ok ? (
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          {indexed
            ? <CheckCircle2 size={13} color="#16a34a" />
            : <Loader2 size={13} color="#16a34a" style={{ animation: 'spin 0.7s linear infinite', flexShrink: 0 }} />
          }
          <span style={{ color: '#15803d', fontWeight: 500 }}>
            {indexed ? 'Indexed' : 'Indexing…'}
          </span>
          <span style={{ color: 'var(--text2)' }}>{result.source}</span>
          <span style={{ color: 'var(--text2)' }}>{result.chunks_upserted} chunks</span>
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <XCircle size={13} color="#dc2626" />
          <span style={{ color: '#dc2626' }}>{result.error || 'Upload failed'}</span>
        </div>
      )}
    </div>
  );
}

function DocTypeIcon({ source }) {
  if (source.startsWith('http://') || source.startsWith('https://')) return <Link size={14} />;
  if (source.toLowerCase().endsWith('.csv')) return <FileSpreadsheet size={14} />;
  return <FileText size={14} />;
}

function fmtDate(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now - d;
    const diffDays = Math.floor(diffMs / 86400000);
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: diffDays > 365 ? 'numeric' : undefined });
  } catch { return ''; }
}

export default function Ingest() {
  const [tab, setTab] = useState('pdf');
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfResult, setPdfResult] = useState(null);
  const [csvLoading, setCsvLoading] = useState(false);
  const [csvResult, setCsvResult] = useState(null);
  const [csvCols, setCsvCols] = useState('');
  const [urlLoading, setUrlLoading] = useState(false);
  const [urlResult, setUrlResult] = useState(null);
  const [urlInput, setUrlInput] = useState('');
  const [collections, setCollections] = useState(null);
  const [documents, setDocuments] = useState(null);
  const [docLoading, setDocLoading] = useState(false);
  const [indexed, setIndexed] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [deleteLoading, setDeleteLoading] = useState(null);
  const pollRef = useRef(null);

  const loadDocuments = useCallback(async () => {
    setDocLoading(true);
    try {
      const data = await listDocuments();
      setDocuments(data.documents);
      return data.documents;
    } catch {
      setDocuments([]);
      return [];
    } finally {
      setDocLoading(false);
    }
  }, []);

  // Auto-load documents when switching to that tab
  useEffect(() => {
    if (tab === 'documents') loadDocuments();
  }, [tab, loadDocuments]);

  // Cleanup poll on unmount
  useEffect(() => () => clearInterval(pollRef.current), []);

  const startPolling = useCallback((prevPoints) => {
    setIndexed(false);
    let attempts = 0;
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      attempts++;
      try {
        const data = await listCollections();
        setCollections(data.collections);
        const total = data.collections.reduce((s, c) => s + (c.points || 0), 0);
        if (total > prevPoints || attempts >= 12) {
          setIndexed(true);
          clearInterval(pollRef.current);
          loadDocuments();
        }
      } catch {}
    }, 3000);
  }, [loadDocuments]);

  const handleIngest = useCallback(async (ingestFn, setLoading, setResult) => {
    setLoading(true);
    setResult(null);
    setIndexed(false);
    clearInterval(pollRef.current);

    let prevPoints = 0;
    try {
      const prev = await listCollections();
      prevPoints = prev.collections.reduce((s, c) => s + (c.points || 0), 0);
    } catch {}

    try {
      const result = await ingestFn();
      setResult(result);
      if (result.status === 'success' || result.status === 'ok') {
        startPolling(prevPoints);
      }
    } catch (e) {
      setResult({ status: 'error', error: e.response?.data?.detail || e.message });
    } finally {
      setLoading(false);
    }
  }, [startPolling]);

  const handleDelete = useCallback(async (source) => {
    setDeleteLoading(source);
    try {
      await deleteDocument(source);
      setDocuments(prev => prev?.filter(d => d.source !== source));
    } catch {
      await loadDocuments();
    } finally {
      setDeleteLoading(null);
      setConfirmDelete(null);
    }
  }, [loadDocuments]);

  const TABS = [
    { id: 'pdf',       label: 'PDF',       icon: FileText },
    { id: 'csv',       label: 'CSV',       icon: FileSpreadsheet },
    { id: 'url',       label: 'URL',       icon: Link },
    { id: 'documents', label: 'Documents', icon: Database },
  ];

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '32px 24px' }}>
      <div style={{ maxWidth: 640, margin: '0 auto' }}>
        <div style={{ marginBottom: 24 }}>
          <h2 style={{ margin: '0 0 4px', fontSize: 18, fontWeight: 600, letterSpacing: '-0.01em' }}>Knowledge Base</h2>
          <p style={{ margin: 0, color: 'var(--text2)', fontSize: 13 }}>
            Ingest documents for RAG retrieval.
          </p>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: 0, marginBottom: 20, borderBottom: '1px solid var(--border)' }}>
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '8px 14px', fontSize: 13,
                background: 'transparent',
                color: tab === id ? 'var(--text)' : 'var(--text2)',
                fontWeight: tab === id ? 500 : 400,
                border: 'none',
                borderBottom: tab === id ? '2px solid var(--text)' : '2px solid transparent',
                marginBottom: -1,
                cursor: 'pointer', transition: 'all 0.1s',
              }}
            >
              <Icon size={13} /> {label}
            </button>
          ))}
        </div>

        {tab === 'pdf' && (
          <div>
            <p style={{ margin: '0 0 14px', fontSize: 13, color: 'var(--text2)' }}>
              Extracts text, chunks it, and stores dense + sparse vectors in Qdrant.
            </p>
            <DropZone
              accept=".pdf"
              onFile={f => handleIngest(() => ingestPDF(f), setPdfLoading, setPdfResult)}
              loading={pdfLoading}
              label="Drop a PDF here"
              icon={FileText}
            />
            <Result result={pdfResult} indexed={indexed} />
          </div>
        )}

        {tab === 'csv' && (
          <div>
            <p style={{ margin: '0 0 14px', fontSize: 13, color: 'var(--text2)' }}>
              Each row becomes a chunk. Optionally specify which columns to embed.
            </p>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', fontSize: 12, color: 'var(--text2)', marginBottom: 5 }}>
                Text columns (comma-separated, optional)
              </label>
              <input
                value={csvCols}
                onChange={e => setCsvCols(e.target.value)}
                placeholder="e.g. title, description"
                style={{
                  width: '100%', padding: '8px 12px',
                  border: '1px solid var(--border)', borderRadius: 6,
                  background: 'var(--bg)', color: 'var(--text)', fontSize: 13,
                }}
              />
            </div>
            <DropZone
              accept=".csv"
              onFile={f => handleIngest(() => ingestCSV(f, csvCols || null), setCsvLoading, setCsvResult)}
              loading={csvLoading}
              label="Drop a CSV here"
              icon={FileSpreadsheet}
            />
            <Result result={csvResult} indexed={indexed} />
          </div>
        )}

        {tab === 'url' && (
          <div>
            <p style={{ margin: '0 0 14px', fontSize: 13, color: 'var(--text2)' }}>
              Fetches a URL, strips navigation, and indexes the content.
            </p>
            <form
              onSubmit={e => {
                e.preventDefault();
                if (urlInput.trim()) handleIngest(() => ingestURL(urlInput.trim()), setUrlLoading, setUrlResult);
              }}
              style={{ display: 'flex', gap: 8 }}
            >
              <input
                value={urlInput}
                onChange={e => setUrlInput(e.target.value)}
                placeholder="https://example.com/docs"
                type="url"
                style={{
                  flex: 1, padding: '8px 12px',
                  border: '1px solid var(--border)', borderRadius: 6,
                  background: 'var(--bg)', color: 'var(--text)', fontSize: 13,
                }}
              />
              <button type="submit" disabled={!urlInput.trim() || urlLoading} className="btn btn-primary">
                {urlLoading ? <Loader2 size={13} className="spin" /> : <Upload size={13} />} Ingest
              </button>
            </form>
            <Result result={urlResult} indexed={indexed} />
          </div>
        )}

        {tab === 'documents' && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
              <p style={{ margin: 0, flex: 1, fontSize: 13, color: 'var(--text2)' }}>
                {documents?.length
                  ? `${documents.length} document${documents.length !== 1 ? 's' : ''} in knowledge base`
                  : 'Ingested documents in knowledge base.'}
              </p>
              <button className="btn btn-ghost btn-sm" onClick={loadDocuments}>
                {docLoading ? <Loader2 size={12} className="spin" /> : <RefreshCw size={12} />} Refresh
              </button>
            </div>

            {docLoading && !documents && (
              <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text3)', fontSize: 13 }}>
                <Loader2 size={16} style={{ animation: 'spin 0.7s linear infinite', margin: '0 auto 8px', display: 'block' }} />
                Loading…
              </div>
            )}

            {!docLoading && documents?.length === 0 && (
              <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text3)', fontSize: 13 }}>
                No documents yet. Ingest a file or URL first.
              </div>
            )}

            {documents && documents.map(doc => {
              const isConfirming = confirmDelete === doc.source;
              const isDeleting = deleteLoading === doc.source;
              const isUrl = doc.source.startsWith('http://') || doc.source.startsWith('https://');
              const displayName = isUrl ? doc.source.replace(/^https?:\/\//, '') : doc.source;
              const uploadedOn = fmtDate(doc.ingested_at);

              return (
                <div key={doc.source} style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '12px 0',
                  borderBottom: '1px solid var(--border)',
                }}>
                  {/* icon */}
                  <span style={{ color: 'var(--text3)', flexShrink: 0, display: 'flex', marginTop: 1 }}>
                    <DocTypeIcon source={doc.source} />
                  </span>

                  {/* name + date stacked */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: 13, color: 'var(--text)', fontWeight: 500,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }} title={doc.source}>
                      {displayName}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 2 }}>
                      {uploadedOn && <span>{uploadedOn} · </span>}
                      <span>{doc.chunks} chunks</span>
                    </div>
                  </div>

                  {/* delete */}
                  {isConfirming ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0 }}>
                      <span style={{ fontSize: 12, color: 'var(--text2)' }}>Remove?</span>
                      <button
                        onClick={() => handleDelete(doc.source)}
                        disabled={isDeleting}
                        style={{
                          padding: '3px 10px', borderRadius: 4,
                          border: '1px solid #ef4444', background: '#ef4444',
                          color: '#fff', fontSize: 12, cursor: 'pointer',
                          display: 'flex', alignItems: 'center', gap: 4,
                        }}
                      >
                        {isDeleting
                          ? <Loader2 size={10} style={{ animation: 'spin 0.7s linear infinite' }} />
                          : 'Yes'}
                      </button>
                      <button
                        onClick={() => setConfirmDelete(null)}
                        style={{
                          padding: '3px 10px', borderRadius: 4,
                          border: '1px solid var(--border)', background: 'transparent',
                          color: 'var(--text2)', fontSize: 12, cursor: 'pointer',
                        }}
                      >
                        No
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setConfirmDelete(doc.source)}
                      title="Remove from knowledge base"
                      style={{
                        padding: '5px 8px', border: '1px solid var(--border)',
                        background: 'transparent', color: 'var(--text3)',
                        cursor: 'pointer', borderRadius: 6, flexShrink: 0,
                        display: 'flex', alignItems: 'center', gap: 5, fontSize: 12,
                      }}
                    >
                      <Trash2 size={12} /> Delete
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
