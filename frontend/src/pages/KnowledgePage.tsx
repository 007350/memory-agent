import { useState, useRef, useCallback } from 'react';
import '../chat.css';
import { insertDocument, uploadDocumentFile } from '../services/api';
import { useServiceHealth } from '../hooks/useServiceHealth';

interface FileUploadState {
  name: string;
  status: 'uploading' | 'ok' | 'error';
  trackId?: string;
  error?: string;
}

export default function KnowledgePage() {
  const [text, setText] = useState('');
  const [fileSource, setFileSource] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ status: string; track_id: string } | null>(null);
  const [error, setError] = useState('');
  const { status: serviceStatus } = useServiceHealth();
  const [fileUploads, setFileUploads] = useState<FileUploadState[]>([]);
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleInsert = async () => {
    if (!text.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const resp = await insertDocument(text.trim(), fileSource.trim());
      setResult(resp);
    } catch (e: any) {
      setError(e.message ?? '插入失败');
    } finally {
      setLoading(false);
    }
  };

  const uploadFiles = useCallback(async (files: File[]) => {
    const allowed = files.filter(f => /\.(txt|md|pdf)$/i.test(f.name));
    const rejected = files.filter(f => !/\.(txt|md|pdf)$/i.test(f.name));
    const newEntries: FileUploadState[] = [
      ...rejected.map(f => ({ name: f.name, status: 'error' as const, error: '不支持的文件类型' })),
      ...allowed.map(f => ({ name: f.name, status: 'uploading' as const })),
    ];
    setFileUploads(prev => [...prev, ...newEntries]);
    await Promise.all(
      allowed.map(async (file, idx) => {
        try {
          const resp = await uploadDocumentFile(file);
          setFileUploads(prev => {
            const next = [...prev];
            const pos = prev.length - allowed.length + idx;
            if (next[pos]) next[pos] = { name: file.name, status: 'ok', trackId: resp.track_id };
            return next;
          });
        } catch (e: any) {
          setFileUploads(prev => {
            const next = [...prev];
            const pos = prev.length - allowed.length + idx;
            if (next[pos]) next[pos] = { name: file.name, status: 'error', error: e.message ?? '上传失败' };
            return next;
          });
        }
      })
    );
  }, []);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length) uploadFiles(files);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length) uploadFiles(files);
    e.target.value = '';
  };

  return (
    <div className="knowledge-page">
      <h2>知识库</h2>
      <p className="knowledge-subtitle">上传文档到 LightRAG，或在下方可视化工具中管理知识图谱。</p>

      <div className="page-status" data-status={serviceStatus}>
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: serviceStatus === "ok" ? "#16a34a" : serviceStatus === "error" ? "#e11d48" : "#d97706", display: "inline-block", flexShrink: 0 }} />
        {serviceStatus === "ok" && "知识库服务当前可用"}
        {serviceStatus === "loading" && "正在检查知识库服务..."}
        {serviceStatus === "degraded" && "知识库服务不可用，入库可能失败"}
        {serviceStatus === "error" && "后端异常，无法确认知识库状态"}
      </div>

      <div className="card">
        <div className="card-title">文件上传</div>
        <div
          className={`drop-zone${dragging ? ' drop-zone-active' : ''}`}
          onDragOver={e => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={e => e.key === "Enter" && fileInputRef.current?.click()}
          aria-label="上传文件区域"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.md,.pdf"
            multiple
            style={{ display: "none" }}
            onChange={handleFileInput}
          />
          <span className="drop-zone-icon">📄</span>
          <span className="drop-zone-text">拖拽文件到此处，或点击选择文件</span>
          <span className="drop-zone-hint">支持 .txt、.md、.pdf，可多选</span>
        </div>
        {fileUploads.length > 0 && (
          <div className="file-list">
            {fileUploads.map((fu, i) => (
              <div key={i} className="file-item">
                <span className="file-item-name" title={fu.name}>{fu.name}</span>
                {fu.status === "uploading" && <span className="file-item-status file-item-loading">上传中...</span>}
                {fu.status === "ok" && <span className="file-item-status file-item-ok">已提交 · {fu.trackId}</span>}
                {fu.status === "error" && <span className="file-item-status file-item-err">{fu.error}</span>}
              </div>
            ))}
            <button className="btn-sm" style={{ alignSelf: "flex-start", marginTop: 2 }} onClick={() => setFileUploads([])}>清空列表</button>
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-title">粘贴文本上传</div>
        <div className="insert-section">
          <div>
            <div className="field-label">文档内容</div>
            <textarea
              className="doc-textarea"
              value={text}
              onChange={e => setText(e.target.value)}
              placeholder="粘贴文档内容，支持纯文本或 Markdown..."
              rows={8}
            />
          </div>
          <div>
            <div className="field-label">来源标识（可选）</div>
            <input
              className="source-input"
              value={fileSource}
              onChange={e => setFileSource(e.target.value)}
              placeholder="例如：python_async_guide"
            />
          </div>
          <button className="btn-primary" onClick={handleInsert} disabled={loading || !text.trim()}>
            {loading ? '处理中...' : '上传并建立索引'}
          </button>
          {result && (
            <div className="result-box">
              <span className={`badge ${result.status === 'success' ? 'badge-ok' : 'badge-warn'}`}>
                {result.status === 'success' ? '已提交' : result.status}
              </span>
              <span className="track-id">任务 ID：{result.track_id}</span>
            </div>
          )}
          {error && <div className="error-box">{error}</div>}
        </div>
      </div>

      <div className="card kg-portal-card">
        <div className="webui-header">
          <div className="webui-title">知识图谱可视化</div>
        </div>
        <a
          className="kg-portal-link"
          href="http://localhost:9621"
          target="_blank"
          rel="noreferrer"
        >
          <span className="kg-portal-icon">🕸️</span>
          <div className="kg-portal-text">
            <div className="kg-portal-label">打开 LightRAG 知识库</div>
            <div className="kg-portal-hint">在新窗口中查看和管理知识图谱</div>
          </div>
          <span className="kg-portal-arrow">↗</span>
        </a>
      </div>
    </div>
  );
}