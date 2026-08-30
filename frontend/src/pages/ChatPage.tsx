import { useState, useRef, useEffect, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import '../chat.css';
import { sendChat, getMemory, clearMemory, deleteMemory, getUserProfile, updateUserProfile, getMemoryEvents, clearMemoryEvents, expireMemoryEvent, sendMemoryFeedback, summarizeProfile, rollbackProfile } from '../services/api';
import type { ChatResponse, Memory, UserProfile, MemoryEvent } from '../services/api';
import { useChatRequestState } from '../hooks/useChatRequestState';
import { useServiceHealth } from '../hooks/useServiceHealth';
import type { Message } from '../hooks/usePersistedMessages';
import ToolCallDisplay from '../components/ToolCallDisplay';

interface ChatPageProps {
  sessionId: string;
  messages: Message[];
  setMessages: (updater: Message[] | ((prev: Message[]) => Message[])) => void;
  onTitleUpdate: (sessionId: string, firstMsg: string) => void;
}

function getOrCreateUserId(): string {
  const key = 'agentic_rag_user_id';
  let id = localStorage.getItem(key);
  if (!id) {
    id = 'user-' + Math.random().toString(36).slice(2, 10);
    localStorage.setItem(key, id);
  }
  return id;
}

function classStatusMeta(meta?: ChatResponse) {
  if (!meta) return '';
  if (!meta.reflection_passed) return 'status-warn';
  if (meta.retrieval_mode === 'hybrid' && meta.sources.length > 0) return 'status-ok';
  return '';
}

type MemoryTab = 'conversation' | 'profile' | 'events';

const FIELD_META: Record<string, [string, string]> = {
  name:                ['👤', '姓名'],
  age:                 ['🎂', '年龄'],
  gender:              ['⚧', '性别'],
  occupation:          ['🎓', '职业'],
  location:            ['📍', '地点'],
  preferences:         ['❤️', '偏好'],
  goals:               ['🎯', '目标'],
  constraints:         ['⚠️', '约束'],
  profile_summary:     ['📝', '摘要'],
  last_summary_source: ['🔄', '摘要来源'],
};

function fieldMeta(key: string): [string, string] {
  return FIELD_META[key] ?? ['○', key];
}

export default function ChatPage({ sessionId, messages, setMessages, onTitleUpdate }: ChatPageProps) {
  const [input, setInput] = useState('');
  const chat = useChatRequestState();
  const { status: serviceStatus, refresh } = useServiceHealth();
  const [userId] = useState(() => getOrCreateUserId());
  const [memories, setMemories] = useState<Memory[]>([]);
  const [showMemory, setShowMemory] = useState(false);
  const [memoryType, setMemoryType] = useState<'all' | 'conversation' | 'preference' | 'fact'>('all');
  const [memoryTab, setMemoryTab] = useState<MemoryTab>('conversation');
  const bottomRef = useRef<HTMLDivElement>(null);
  const retryCountRef = useRef(0);

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [profileForm, setProfileForm] = useState<Record<string, string>>({});
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMessage, setProfileMessage] = useState('');

  const [events, setEvents] = useState<MemoryEvent[]>([]);
  const [eventLimit, setEventLimit] = useState(20);
  const [eventsClearing, setEventsClearing] = useState(false);
  const [feedbackLoading, setFeedbackLoading] = useState<Record<number, boolean>>({});
  const [profileSummary, setProfileSummary] = useState('');
  const [profileSummaryLoading, setProfileSummaryLoading] = useState(false);
  const [profileRollingBack, setProfileRollingBack] = useState(false);
  const [expandedMemoryIdx, setExpandedMemoryIdx] = useState<number | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, chat.error]);

  const visibleMemories = useMemo(() => {
    if (memoryType === 'all') return memories;
    return memories.filter(item => item.type === memoryType);
  }, [memories, memoryType]);

  const memoryCounts = useMemo(() => {
    const counts: Record<string, number> = { all: memories.length };
    for (const item of memories) {
      counts[item.type] = (counts[item.type] || 0) + 1;
    }
    return counts;
  }, [memories]);

  const loadMemory = async () => {
    try {
      const sessionMem = await getMemory(sessionId);
      setMemories(sessionMem);
    } catch {
      setMemories(prev => prev);
    }
  };

  const loadProfile = async () => {
    try {
      const data = await getUserProfile(userId);
      setProfile(data);
      setProfileForm(data.profile ?? {});
      setProfileMessage('');
    } catch {
      setProfileMessage('加载用户画像失败');
    }
  };

  const loadEvents = async () => {
    try {
      const data = await getMemoryEvents(userId, eventLimit);
      setEvents(data);
    } catch {
      setEvents([]);
    }
  };

  useEffect(() => {
    if (!showMemory) return;
    loadMemory();
    if (memoryTab === 'profile') {
      loadProfile();
    }
    if (memoryTab === 'events') {
      loadEvents();
    }
  }, [showMemory, memoryTab, userId, sessionId, eventLimit]);

  const handleSend = async () => {
    const query = input.trim();
    if (!query || chat.loading) return;
    setInput('');
    const isFirst = messages.length === 0;
    setMessages(prev => [...prev, { role: 'user', content: query }]);
    if (isFirst) onTitleUpdate(sessionId, query);
    const controller = chat.start();
    retryCountRef.current += 1;

    try {
      const resp = await sendChat(query, sessionId, userId, controller.signal);
      retryCountRef.current = 0;
      chat.finish();
      setMessages(prev => [...prev, { role: 'assistant', content: resp.answer, meta: resp }]);
    } catch (e: any) {
      chat.fail(e?.message === 'request_cancelled' ? '请求已取消' : '请求失败，请稍后重试');
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: '暂时无法得到回答。你可以重试、检查知识库是否已配置，或稍后再试。',
          error: true,
        },
      ]);
    }
  };

  const handleClearMemory = async () => {
    await clearMemory(sessionId);
    setMemories(prev => prev.filter(item => item.session !== sessionId));
  };

  const handleDeleteMemory = async (memoryId: number) => {
    await deleteMemory(sessionId, memoryId);
    setMemories(prev => prev.filter(item => item.id !== memoryId));
  };

  const handleSaveProfile = async () => {
    setProfileSaving(true);
    setProfileMessage('');
    try {
      const next = Object.fromEntries(
        Object.entries(profileForm).filter(([, value]) => value.trim() !== '')
      );
      const data = await updateUserProfile(userId, next);
      setProfile(data);
      setProfileForm(data.profile ?? {});
      setProfileMessage('用户画像已保存');
    } catch {
      setProfileMessage('保存失败，请稍后重试');
    } finally {
      setProfileSaving(false);
    }
  };

  const handleClearEvents = async () => {
    setEventsClearing(true);
    try {
      await clearMemoryEvents(userId);
      setEvents([]);
    } catch {
      setEvents([]);
    } finally {
      setEventsClearing(false);
    }
  };

  const handleExpireEvent = async (eventId: number) => {
    await expireMemoryEvent(userId, eventId);
    setEvents(prev => prev.filter(item => item.id !== eventId));
  };

  const handleFeedback = async (eventId: number, feedback: 'up' | 'down') => {
    setFeedbackLoading(prev => ({ ...prev, [eventId]: true }));
    try {
      await sendMemoryFeedback(userId, eventId, feedback);
      setEvents(prev => prev.map(item => item.id === eventId ? { ...item, feedback_score: (item.feedback_score || 0) + (feedback === 'up' ? 1 : -1), feedback_count: (item.feedback_count || 0) + 1 } : item));
    } finally {
      setFeedbackLoading(prev => ({ ...prev, [eventId]: false }));
    }
  };

  const handleSummarizeProfile = async () => {
    setProfileSummaryLoading(true);
    try {
      const data = await summarizeProfile(userId, profileSummary || undefined, 'manual');
      setProfile(data);
      setProfileForm(data.profile ?? {});
      setProfileMessage('画像摘要已更新');
      setProfileSummary('');
    } catch {
      setProfileMessage('摘要失败');
    } finally {
      setProfileSummaryLoading(false);
    }
  };

  const handleRollbackProfile = async () => {
    setProfileRollingBack(true);
    try {
      const data = await rollbackProfile(userId);
      setProfile(data);
      setProfileForm(data.profile ?? {});
      setProfileMessage('画像已回滚');
    } catch {
      setProfileMessage('回滚失败');
    } finally {
      setProfileRollingBack(false);
    }
  };

  const handleOpenLightRAG = () => {
    window.open('http://localhost:9621', '_blank', 'noreferrer');
  };

  return (
    <div className="chat-page">
      <div className="service-banner" data-status={serviceStatus}>
        <span className="service-indicator" />
        <span className="service-text">
          {serviceStatus === 'ok' && '服务正常'}
          {serviceStatus === 'loading' && '正在检查服务状态...'}
          {serviceStatus === 'degraded' && '知识库服务不可用，问答可能降级'}
          {serviceStatus === 'error' && '后端服务异常，请检查网络与后端'}
        </span>
        <button type="button" className="btn-sm" onClick={refresh}>刷新状态</button>
      </div>

      <div className="session-bar">
        <span className="session-label">会话：{sessionId}</span>
        <button
          className="btn-sm"
          onClick={() => {
            const next = !showMemory;
            setShowMemory(next);
            if (next) setMemoryTab('conversation');
          }}
        >
          {showMemory ? '隐藏记忆' : '查看记忆'}
        </button>
        {showMemory && (
          <button className="btn-sm btn-danger" onClick={handleClearMemory}>清空会话记忆</button>
        )}
        <button type="button" className="btn-sm" onClick={handleOpenLightRAG}>打开知识库</button>
      </div>

      {showMemory && (
        <div className="memory-panel">
          <div className="memory-tabs">
            <button className={`memory-tab ${memoryTab === 'conversation' ? 'memory-tab-active' : ''}`} onClick={() => setMemoryTab('conversation')}>对话记忆</button>
            <button className={`memory-tab ${memoryTab === 'profile' ? 'memory-tab-active' : ''}`} onClick={() => setMemoryTab('profile')}>长期画像</button>
            <button className={`memory-tab ${memoryTab === 'events' ? 'memory-tab-active' : ''}`} onClick={() => setMemoryTab('events')}>记忆事件</button>
          </div>

          {memoryTab === 'conversation' && (
            <>
              <div className="memory-filters">
                {(['all', 'conversation', 'preference', 'fact'] as const).map(type => (
                  <button
                    key={type}
                    className={`chip ${memoryType === type ? 'chip-active' : ''}`}
                    onClick={() => setMemoryType(type)}
                  >
                    {type === 'all' ? '全部' : type}
                    <span className="chip-count">{memoryCounts[type] ?? 0}</span>
                  </button>
                ))}
              </div>
              {visibleMemories.length === 0 ? (
                <div className="memory-empty" style={{padding: '8px 16px'}}>
                  <span>暂无记忆</span>
                  <span className="memory-hint">对话后会自动保留关键信息</span>
                </div>
              ) : (
                <div style={{padding: '8px 16px', display: 'flex', flexDirection: 'column', gap: 6}}>
                  {visibleMemories.map(m => (
                    <div key={m.id} className="memory-item">
                      <div className="memory-item-body">
                        <span className="badge badge-type" style={{marginRight: 8}}>{m.type}</span>
                        <span className="memory-content">{m.content}</span>
                      </div>
                      <button className="btn-sm btn-danger" onClick={() => handleDeleteMemory(m.id)}>删除</button>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {memoryTab === 'profile' && (
            <div className="long-memory">
              <div className="long-memory-section">
                <div className="long-memory-title">当前画像</div>
                {!profile || Object.keys(profile.profile).length === 0 ? (
                  <div className="memory-empty">还没有稳定画像字段，对话后系统会自动提取</div>
                ) : (
                  <div className="profile-list">
                    {Object.entries(profile.profile).map(([key, value]) => {
                      const [icon, label] = fieldMeta(key);
                      return (
                        <div key={key} className="profile-list-item">
                          <span className="profile-field-icon">{icon}</span>
                          <span className="profile-field-name">{label}</span>
                          <span className="profile-field-value">{String(value)}</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="long-memory-section">
                <div className="long-memory-title">编辑画像</div>
                <div style={{display: 'flex', flexDirection: 'column', gap: 6}}>
                  {['name', 'age', 'gender', 'occupation', 'location', 'preferences', 'goals', 'constraints'].map(key => {
                    const [icon, label] = fieldMeta(key);
                    return (
                      <div key={key} className="profile-form-row">
                        <label className="profile-form-label">
                          <span className="profile-form-label-icon">{icon}</span>
                          {label}
                        </label>
                        <input
                          className="profile-form-input"
                          placeholder={'填写' + label + '...'}
                          value={profileForm[key] ?? ''}
                          onChange={event => setProfileForm(prev => ({ ...prev, [key]: event.target.value }))}
                        />
                      </div>
                    );
                  })}
                </div>
                <div className="profile-actions" style={{marginTop: 8}}>
                  <button className="btn-send" disabled={profileSaving} onClick={handleSaveProfile}>
                    {profileSaving ? '保存中...' : '保存画像'}
                  </button>
                  {profileMessage && <span className="profile-message">{profileMessage}</span>}
                </div>
              </div>

              <div className="long-memory-section">
                <div className="profile-action-card">
                  <div className="profile-action-title">摘要 / 回滚</div>
                  <div className="profile-action-row">
                    <textarea
                      className="profile-summary-input"
                      placeholder="可选：输入补充说明，留空则自动摘要现有字段"
                      value={profileSummary}
                      rows={2}
                      onChange={event => setProfileSummary(event.target.value)}
                    />
                    <button className="btn-sm" disabled={profileSummaryLoading} onClick={handleSummarizeProfile}>
                      {profileSummaryLoading ? '生成中...' : '生成摘要'}
                    </button>
                    <button className="btn-sm btn-danger" disabled={profileRollingBack} onClick={handleRollbackProfile}>
                      {profileRollingBack ? '回滚中...' : '回滚'}
                    </button>
                  </div>
                  <div className="profile-action-hint">摘要会提取画像关键信息；回滚会清空所有画像字段</div>
                </div>
              </div>
            </div>
          )}

          {memoryTab === 'events' && (
            <div className="long-memory">
              <div className="long-memory-header">
                <div className="long-memory-title">记忆事件</div>
                <div className="event-controls">
                  <select className="event-select" value={eventLimit} onChange={event => setEventLimit(Number(event.target.value))}>
                    <option value="10">最近 10 条</option>
                    <option value="20">最近 20 条</option>
                    <option value="50">最近 50 条</option>
                  </select>
                  <button className="btn-sm btn-danger" disabled={eventsClearing} onClick={handleClearEvents}>
                    {eventsClearing ? '清空中...' : '清空长期事件'}
                  </button>
                </div>
              </div>
              {events.length === 0 ? (
                <div className="memory-empty">暂无长期记忆事件</div>
              ) : (
                events.map(event => (
                  <div key={event.id} className="event-item">
                    <div className="event-item-body">
                      <div className="event-meta">
                        <span className="badge badge-mode">{event.event_type}</span>
                        <span className="event-importance">importance：{event.importance.toFixed(1)}</span>
                        <span className="event-time">{new Date(event.created_at * 1000).toLocaleString()}</span>
                        <span className="event-source">source：{event.source ?? 'extraction'}</span>
                      </div>
                      <div className="memory-content">{event.content}</div>
                      <div className="feedback-actions">
                        <button className="btn-sm" disabled={feedbackLoading[event.id]} onClick={() => handleFeedback(event.id, 'up')}>有用</button>
                        <button className="btn-sm btn-danger" disabled={feedbackLoading[event.id]} onClick={() => handleFeedback(event.id, 'down')}>没用</button>
                      </div>
                    </div>
                    <button className="btn-sm btn-danger" onClick={() => handleExpireEvent(event.id)}>标记过期</button>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}

      <div className="messages" role="log" aria-live="polite">
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}${msg.error ? ' error' : ''}`}>
            <div className="bubble">
              {msg.role === 'assistant' ? (
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              ) : (
                msg.content
              )}
            </div>
            
            {/* 显示工具调用 */}
            {msg.meta?.tool_calls && msg.meta.tool_calls.length > 0 && (
              <ToolCallDisplay toolCalls={msg.meta.tool_calls} />
            )}

            <div className="message-status">
              {msg.error && <span className="status-label status-error">失败</span>}
              {msg.meta && (
                <>
                  <span className={`status-label ${classStatusMeta(msg.meta)}`}>
                    {msg.meta.reflection_passed ? '通过质检' : '需重试'}
                  </span>
                  <span className="badge badge-agent">{msg.meta.agent}</span>
                  <span className="badge badge-mode">{msg.meta.retrieval_mode}</span>
                  <span className="badge badge-latency">{msg.meta.latency.toFixed(2)}s</span>
                  {msg.meta.sources.length > 0 && (
                    msg.meta.retrieval_mode === 'web' ? (
                      <span className="badge badge-web">
                        🌐 网络搜索 · {msg.meta.sources.length} 条结果
                      </span>
                    ) : (
                      <span className="badge badge-src">
                        来源：{msg.meta.sources.map(s => s.file_path ?? s.reference_id).join(', ')}
                      </span>
                    )
                  )}
                  {(msg.meta.used_memories?.length ?? 0) > 0 && (
                    <button
                      type="button"
                      className="badge badge-memories"
                      onClick={() => setExpandedMemoryIdx(prev => prev === i ? null : i)}
                    >
                      🧠 参考记忆 · {msg.meta.used_memories!.length} 条
                    </button>
                  )}
                </>
              )}
            </div>

            {expandedMemoryIdx === i && (msg.meta?.used_memories?.length ?? 0) > 0 && (
              <div className="used-memories">
                <div className="used-memories-title">本次回答参考的长期记忆</div>
                {msg.meta!.used_memories!.map((m, idx) => (
                  <div key={idx} className="used-memory-item">
                    <span className="badge badge-type">{m.event_type}</span>
                    <span className="used-memory-content">{m.content}</span>
                    <span className="used-memory-score">相关度 {(m.score * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
        {chat.loading && (
          <div className="message assistant loading-message">
            <div className="bubble loading-bubble" aria-live="assertive">
              {chat.steps[chat.stepIndex]}
              <span className="loading-dots" aria-hidden="true">
                <span /><span /><span />
              </span>
              <button type="button" className="btn-text cancel-btn" onClick={() => chat.controller?.abort()}>
                取消
              </button>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="input-area">
        {chat.error ? (
          <div className="error-toast" role="alert">
            <span>{chat.error}</span>
            <div className="error-actions">
              <button type="button" className="btn-sm" onClick={() => { chat.finish(); refresh(); }}>重试</button>
              <button type="button" className="btn-sm" onClick={() => chat.fail('')}>忽略</button>
            </div>
          </div>
        ) : (
          <div className="input-wrap">
            <textarea
              className="chat-input"
              rows={1}
              value={input}
              onChange={e => {
                setInput(e.target.value);
                e.target.style.height = 'auto';
                e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px';
              }}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), handleSend())}
              placeholder="给 Agentic RAG 发送消息..."
              disabled={chat.loading}
            />
            <button className="btn-send" onClick={handleSend} disabled={chat.loading || !input.trim()} aria-label="发送">
              ↑
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
