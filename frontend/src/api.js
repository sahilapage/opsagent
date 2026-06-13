import axios from 'axios';

const BASE = import.meta.env.VITE_API_URL || '/api';

const http = axios.create({ baseURL: BASE });

// Agent
export const runAgent = (task, userId = 'default', sessionId = null) =>
  http.post('/agent', { task, user_id: userId, session_id: sessionId }).then(r => r.data);

// RAG
export const queryKB = (query, collection = null, filters = null) =>
  http.post('/query', { query, collection, filters }).then(r => r.data);

// Ingest
export const ingestPDF = (file, collection = null) => {
  const fd = new FormData();
  fd.append('file', file);
  if (collection) fd.append('collection', collection);
  return http.post('/ingest/pdf', fd).then(r => r.data);
};

export const ingestCSV = (file, textColumns = null, collection = null) => {
  const fd = new FormData();
  fd.append('file', file);
  if (textColumns) fd.append('text_columns', textColumns);
  if (collection) fd.append('collection', collection);
  return http.post('/ingest/csv', fd).then(r => r.data);
};

export const ingestURL = (url, collection = null) =>
  http.post('/ingest/url', { url, collection }).then(r => r.data);

export const listCollections = () =>
  http.get('/collections').then(r => r.data);

// Memory
export const listMemories = (userId) =>
  http.get(`/memory/${userId}`).then(r => r.data);

export const storeMemory = (userId, content, memoryType = 'fact') =>
  http.post('/memory/store', { user_id: userId, content, memory_type: memoryType }).then(r => r.data);

export const deleteMemory = (memoryId) =>
  http.delete(`/memory/${memoryId}`).then(r => r.data);

export const consolidateMemories = (userId) =>
  http.post(`/memory/consolidate/${userId}`).then(r => r.data);

export const memorySummary = (userId) =>
  http.get(`/memory/summary/${userId}`).then(r => r.data);

// Conversation
export const conversationHistory = (userId, turns = 20) =>
  http.get(`/conversation/${userId}/history?turns=${turns}`).then(r => r.data);

// HITL
export const getPending = () =>
  http.get('/agent/pending').then(r => r.data);

export const approveAction = (traceId) =>
  http.post(`/agent/approve/${traceId}`).then(r => r.data);

export const rejectAction = (traceId) =>
  http.post(`/agent/reject/${traceId}`).then(r => r.data);

export const approveGitHub = (traceId) =>
  http.post(`/agent/approve/github/${traceId}`).then(r => r.data);

export const rejectGitHub = (traceId) =>
  http.post(`/agent/reject/github/${traceId}`).then(r => r.data);

// Health
export const healthCheck = () =>
  http.get('/health').then(r => r.data);

// Streaming (returns EventSource)
export const createStreamSource = (task, userId = 'default') => {
  const params = new URLSearchParams({ task, user_id: userId });
  return new EventSource(`${BASE}/stream?${params}`);
};
