import './App.css';
import ChatPage from './pages/ChatPage';
import KnowledgePage from './pages/KnowledgePage';
import RoadmapPage from './pages/RoadmapPage';
import { useSessionManager } from './hooks/usePersistedMessages';
import { useState } from 'react';

type View = 'chat' | 'knowledge' | 'roadmap';

function formatDate(ts: number) {
  const d = new Date(ts);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) return '今天';
  const diff = Math.floor((now.getTime() - d.getTime()) / 86400000);
  if (diff === 1) return '昨天';
  if (diff < 7) return `${diff} 天前`;
  return d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' });
}

export default function App() {
  const [view, setView] = useState<View>('chat');
  const session = useSessionManager();

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-top">
          <div className="app-brand">
            <div className="app-logo">A</div>
            <span className="app-title">Agentic RAG</span>
          </div>
          <button className="btn-new-chat" onClick={session.newSession}>
            <span className="btn-new-chat-icon">＋</span>
            新对话
          </button>
        </div>

        <nav className="session-list">
          {session.sessions.map(s => (
            <div
              key={s.id}
              className={`session-item ${s.id === session.currentId ? 'session-item-active' : ''}`}
              onClick={() => { setView('chat'); session.switchSession(s.id); }}
            >
              <div className="session-item-body">
                <div className="session-title">{s.title}</div>
                <div className="session-date">{formatDate(s.updatedAt)}</div>
              </div>
              <button
                className="session-delete-btn"
                onClick={e => { e.stopPropagation(); session.deleteSession(s.id); }}
                aria-label="删除会话"
              >✕</button>
            </div>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <button
            className={`sidebar-nav-btn ${view === 'knowledge' ? 'sidebar-nav-active' : ''}`}
            onClick={() => setView('knowledge')}
          >
            <span>📚</span> 知识库
          </button>
          <button
            className={`sidebar-nav-btn ${view === 'roadmap' ? 'sidebar-nav-active' : ''}`}
            onClick={() => setView('roadmap')}
          >
            <span>🗺️</span> 学习路线
          </button>
        </div>
      </aside>

      <main className="app-main">
        {view === 'chat' ? (
          <ChatPage
            sessionId={session.currentId}
            messages={session.messages}
            setMessages={session.setMessages}
            onTitleUpdate={session.updateSessionTitle}
          />
        ) : view === 'knowledge' ? (
          <KnowledgePage />
        ) : (
          <RoadmapPage />
        )}
      </main>
    </div>
  );
}
