import { useState } from 'react';
import type { Roadmap } from '../services/api';

interface Props {
  roadmaps: Roadmap[];
}

export default function RoadmapStats({ roadmaps }: Props) {
  const [tooltip, setTooltip] = useState<{ text: string; x: number; y: number } | null>(null);

  // 汇总数据
  const totalSteps = roadmaps.reduce((s, r) => s + r.steps.length, 0);
  const doneSteps = roadmaps.reduce((s, r) => s + r.steps.filter(st => st.done).length, 0);
  const overallPct = totalSteps > 0 ? Math.round((doneSteps / totalSteps) * 100) : 0;

  // 环形图参数
  const R = 48;
  const cx = 64;
  const cy = 64;
  const circumference = 2 * Math.PI * R;
  const dash = (overallPct / 100) * circumference;

  // 每条路线数据
  const rows = roadmaps.map(r => {
    const total = r.steps.length;
    const done = r.steps.filter(s => s.done).length;
    const pct = total > 0 ? Math.round((done / total) * 100) : 0;
    return { title: r.title, done, total, pct };
  });

  return (
    <div style={{
      display: 'flex',
      gap: 24,
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius)',
      padding: '20px 24px',
      marginBottom: 24,
      boxShadow: 'var(--shadow-sm)',
      alignItems: 'center',
      flexWrap: 'wrap',
    }}>
      {/* 左侧：总体进度环形图 */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, flexShrink: 0 }}>
        <svg width={128} height={128} viewBox="0 0 128 128" aria-label={`总体完成率 ${overallPct}%`}>
          {/* 背景圆 */}
          <circle
            cx={cx} cy={cy} r={R}
            fill="none"
            stroke="var(--border)"
            strokeWidth={10}
          />
          {/* 进度圆弧 */}
          <circle
            cx={cx} cy={cy} r={R}
            fill="none"
            stroke="var(--accent)"
            strokeWidth={10}
            strokeLinecap="round"
            strokeDasharray={`${dash} ${circumference}`}
            strokeDashoffset={circumference / 4}
            style={{ transition: 'stroke-dasharray 0.8s cubic-bezier(0.4,0,0.2,1)' }}
          />
          {/* 中心百分比 */}
          <text
            x={cx} y={cy - 4}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize={22}
            fontWeight={700}
            fill="var(--text-primary)"
            fontFamily="inherit"
          >
            {overallPct}%
          </text>
          <text
            x={cx} y={cy + 16}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize={11}
            fill="var(--text-muted)"
            fontFamily="inherit"
          >
            完成率
          </text>
        </svg>
        <div style={{ textAlign: 'center', fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6 }}>
          <div>共 <strong style={{ color: 'var(--text-primary)' }}>{totalSteps}</strong> 步</div>
          <div>已完成 <strong style={{ color: 'var(--accent)' }}>{doneSteps}</strong> 步</div>
        </div>
      </div>

      {/* 分隔线 */}
      <div style={{ width: 1, background: 'var(--border)', alignSelf: 'stretch', flexShrink: 0, minHeight: 80 }} />

      {/* 右侧：各路线条形图 */}
      <div style={{ flex: 1, minWidth: 180, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 2 }}>各路线进度</div>
        {rows.map((row, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {/* 路线名 */}
            <div style={{
              width: 120, flexShrink: 0,
              fontSize: 12, color: 'var(--text-primary)',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }} title={row.title}>
              {row.title}
            </div>
            {/* 条形图 */}
            <div style={{ flex: 1, position: 'relative' }}>
              <svg
                width="100%" height={14}
                style={{ display: 'block', cursor: 'default' }}
                onMouseMove={e => {
                  const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
                  setTooltip({ text: `${row.done}/${row.total} 步已完成`, x: e.clientX - rect.left, y: -28 });
                }}
                onMouseLeave={() => setTooltip(null)}
                aria-label={`${row.title}: ${row.pct}%`}
              >
                {/* 背景轨道 */}
                <rect x={0} y={3} width="100%" height={8} rx={4} fill="var(--border)" />
                {/* 进度条 */}
                <rect
                  x={0} y={3}
                  width={`${row.pct}%`}
                  height={8} rx={4}
                  fill="var(--accent)"
                  style={{ transition: 'width 0.8s cubic-bezier(0.4,0,0.2,1)' }}
                />
              </svg>
              {/* tooltip */}
              {tooltip && (
                <div style={{
                  position: 'absolute',
                  top: tooltip.y,
                  left: Math.min(tooltip.x, 120),
                  background: 'var(--text-primary)',
                  color: '#fff',
                  fontSize: 11,
                  padding: '3px 8px',
                  borderRadius: 6,
                  whiteSpace: 'nowrap',
                  pointerEvents: 'none',
                  zIndex: 10,
                }}>
                  {tooltip.text}
                </div>
              )}
            </div>
            {/* 百分比 */}
            <div style={{ width: 34, flexShrink: 0, fontSize: 12, color: 'var(--text-muted)', textAlign: 'right' }}>
              {row.pct}%
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
