import { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar.jsx';
import Chat from './components/Chat.jsx';
import Ingest from './components/Ingest.jsx';
import Memory from './components/Memory.jsx';
import Approvals from './components/Approvals.jsx';
import Settings from './components/Settings.jsx';

export default function App() {
  const [view, setView] = useState('chat');
  const [userId, setUserId] = useState(() => localStorage.getItem('opsagent_user_id') || 'default');
  const [pendingCount, setPendingCount] = useState(0);

  const handlePendingChange = useCallback((count) => {
    setPendingCount(count);
  }, []);

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: '#fff' }}>
      <Sidebar view={view} setView={setView} pendingCount={pendingCount} />
      <main style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {view === 'chat'      && <Chat userId={userId} />}
        {view === 'ingest'    && <Ingest />}
        {view === 'memory'    && <Memory userId={userId} />}
        {view === 'approvals' && <Approvals onPendingChange={handlePendingChange} />}
        {view === 'settings'  && <Settings userId={userId} setUserId={setUserId} />}
      </main>
    </div>
  );
}
