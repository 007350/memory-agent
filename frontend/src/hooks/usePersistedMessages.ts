import { useState, useCallback } from 'react';
import type { ChatResponse } from '../services/api';

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  meta?: ChatResponse;
  error?: boolean;
}

export interface SessionMeta {
  id: string;
  title: string;
  updatedAt: number;
}

const SESSIONS_KEY = 'agentic_rag_sessions';
const CURRENT_KEY = 'agentic_rag_current_session';

function messagesKey(sessionId: string) {
  return `agentic_rag_messages_${sessionId}`;
}

function loadSessions(): SessionMeta[] {
  try {
    return JSON.parse(localStorage.getItem(SESSIONS_KEY) ?? '[]');
  } catch {
    return [];
  }
}

function saveSessions(sessions: SessionMeta[]) {
  localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
}

function loadMessages(sessionId: string): Message[] {
  try {
    const stored = JSON.parse(localStorage.getItem(messagesKey(sessionId)) ?? '[]');
    // error 气泡是临时提示，不作为历史保留
    return Array.isArray(stored) ? stored.filter(m => !m?.error) : [];
  } catch {
    return [];
  }
}

function saveMessages(sessionId: string, messages: Message[]) {
  localStorage.setItem(messagesKey(sessionId), JSON.stringify(messages.filter(m => !m.error)));
}

function createSession(): SessionMeta {
  return { id: 'session-' + Date.now(), title: '新对话', updatedAt: Date.now() };
}

export function useSessionManager() {
  const [sessions, setSessions] = useState<SessionMeta[]>(() => {
    const s = loadSessions();
    if (s.length === 0) {
      const first = createSession();
      saveSessions([first]);
      localStorage.setItem(CURRENT_KEY, first.id);
      return [first];
    }
    return s;
  });

  const [currentId, setCurrentId] = useState<string>(() => {
    const stored = localStorage.getItem(CURRENT_KEY);
    const all = loadSessions();
    if (stored && all.find(s => s.id === stored)) return stored;
    if (all.length > 0) return all[0].id;
    const first = createSession();
    saveSessions([first]);
    localStorage.setItem(CURRENT_KEY, first.id);
    return first.id;
  });

  const [messages, setMessagesRaw] = useState<Message[]>(() => loadMessages(
    localStorage.getItem(CURRENT_KEY) ?? ''
  ));

  const setMessages = useCallback((updater: Message[] | ((prev: Message[]) => Message[])) => {
    setMessagesRaw(prev => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      const id = localStorage.getItem(CURRENT_KEY) ?? '';
      saveMessages(id, next);
      return next;
    });
  }, []);

  const updateSessionTitle = useCallback((sessionId: string, firstUserMsg: string) => {
    const title = firstUserMsg.slice(0, 28);
    setSessions(prev => {
      const next = prev.map(s => s.id === sessionId ? { ...s, title, updatedAt: Date.now() } : s);
      saveSessions(next);
      return next;
    });
  }, []);

  const newSession = useCallback(() => {
    const s = createSession();
    setSessions(prev => {
      const next = [s, ...prev];
      saveSessions(next);
      return next;
    });
    localStorage.setItem(CURRENT_KEY, s.id);
    setCurrentId(s.id);
    setMessagesRaw([]);
  }, []);

  const switchSession = useCallback((id: string) => {
    localStorage.setItem(CURRENT_KEY, id);
    setCurrentId(id);
    setMessagesRaw(loadMessages(id));
  }, []);

  const deleteSession = useCallback((id: string) => {
    localStorage.removeItem(messagesKey(id));
    setSessions(prev => {
      const next = prev.filter(s => s.id !== id);
      saveSessions(next);
      if (id === localStorage.getItem(CURRENT_KEY)) {
        const fallback = next[0] ?? createSession();
        if (next.length === 0) {
          saveSessions([fallback]);
          setSessions([fallback]);
        }
        localStorage.setItem(CURRENT_KEY, fallback.id);
        setCurrentId(fallback.id);
        setMessagesRaw(loadMessages(fallback.id));
      }
      return next.length > 0 ? next : prev.filter(s => s.id !== id);
    });
  }, []);

  return {
    sessions,
    currentId,
    messages,
    setMessages,
    updateSessionTitle,
    newSession,
    switchSession,
    deleteSession,
  };
}
