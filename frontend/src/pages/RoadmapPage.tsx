import { useState, useEffect, useCallback } from 'react';
import '../chat.css';
import { getRoadmaps, updateRoadmapStep, deleteRoadmap, type Roadmap } from '../services/api';
import RoadmapStats from '../components/RoadmapStats';

function getUserId(): string {
  const key = 'agentic_rag_user_id';
  let id = localStorage.getItem(key);
  if (!id) {
    id = 'user-' + Math.random().toString(36).slice(2, 10);
    localStorage.setItem(key, id);
  }
  return id;
}

function formatDate(ts: number) {
  const d = new Date(ts * 1000);
  return d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export default function RoadmapPage() {
  const userId = getUserId();
  const [roadmaps, setRoadmaps] = useState<Roadmap[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getRoadmaps(userId);
      setRoadmaps(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggleExpand = (id: number) => {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const handleStepToggle = async (roadmapId: number, stepId: number, done: boolean) => {
    setRoadmaps(prev => prev.map(r =>
      r.id === roadmapId
        ? { ...r, steps: r.steps.map(s => s.id === stepId ? { ...s, done } : s) }
        : r
    ));
    try {
      await updateRoadmapStep(roadmapId, stepId, done);
    } catch {
      load();
    }
  };

  const handleDelete = async (roadmapId: number) => {
    if (!confirm('确定删除这条学习路线？')) return;
    try {
      await deleteRoadmap(roadmapId);
      setRoadmaps(prev => prev.filter(r => r.id !== roadmapId));
    } catch {
      alert('删除失败');
    }
  };

  return (
    <div className="roadmap-page">
      <h2>学习路线</h2>
      <p className="knowledge-subtitle">由 Agent 基于知识库为你规划的学习步骤，可跟踪完成进度。</p>

      {loading && <div className="roadmap-empty">加载中...</div>}

      {!loading && roadmaps.length === 0 && (
        <div className="roadmap-empty">
          <span>暂无学习路线</span>
          <span className="roadmap-empty-hint">在聊天中告诉 Agent「帮我规划 XXX 的学习路线」即可生成</span>
        </div>
      )}

      {!loading && roadmaps.length > 0 && (
        <RoadmapStats roadmaps={roadmaps} />
      )}

      {roadmaps.map(roadmap => {
        const doneCount = roadmap.steps.filter(s => s.done).length;
        const total = roadmap.steps.length;
        const pct = total > 0 ? Math.round((doneCount / total) * 100) : 0;
        const isOpen = expanded.has(roadmap.id);

        return (
          <div key={roadmap.id} className="roadmap-card">
            <div className="roadmap-card-header" onClick={() => toggleExpand(roadmap.id)}>
              <div className="roadmap-card-left">
                <span className="roadmap-expand-icon">{isOpen ? '▾' : '▸'}</span>
                <div>
                  <div className="roadmap-title">{roadmap.title}</div>
                  <div className="roadmap-meta">{formatDate(roadmap.created_at)} · {roadmap.doc_ref}</div>
                </div>
              </div>
              <div className="roadmap-card-right">
                <div className="roadmap-progress-text">{doneCount}/{total}</div>
                <div className="roadmap-progress-bar">
                  <div className="roadmap-progress-fill" style={{ width: `${pct}%` }} />
                </div>
                <button
                  className="btn-sm btn-danger"
                  onClick={e => { e.stopPropagation(); handleDelete(roadmap.id); }}
                >删除</button>
              </div>
            </div>

            {isOpen && (
              <div className="roadmap-steps">
                {roadmap.steps.map(step => (
                  <label key={step.id} className={`roadmap-step${step.done ? ' roadmap-step-done' : ''}`}>
                    <input
                      type="checkbox"
                      className="step-check"
                      checked={step.done}
                      onChange={e => handleStepToggle(roadmap.id, step.id, e.target.checked)}
                    />
                    <div className="roadmap-step-body">
                      <div className="roadmap-step-title">{step.id}. {step.title}</div>
                      {step.detail && <div className="roadmap-step-detail">{step.detail}</div>}
                    </div>
                  </label>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
