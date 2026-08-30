import './ToolCallDisplay.css';

interface ToolCall {
  name: string;
  arguments: Record<string, any>;
  result: string;
  error: string;
  latency: number;
}

interface ToolCallDisplayProps {
  toolCalls: ToolCall[];
}

const TOOL_ICONS: Record<string, string> = {
  python_repl: '🐍',
  web_search: '🔍',
  calculator: '🧮',
};

export default function ToolCallDisplay({ toolCalls }: ToolCallDisplayProps) {
  if (!toolCalls || toolCalls.length === 0) return null;

  return (
    <div className="tool-calls">
      {toolCalls.map((tool, i) => (
        <div key={i} className="tool-call">
          <div className="tool-header">
            <span className="tool-icon">{TOOL_ICONS[tool.name] || '🔧'}</span>
            <span className="tool-name">{tool.name}</span>
            <span className="tool-latency">⏱️ {tool.latency.toFixed(2)}s</span>
          </div>
          
          <div className="tool-body">
            <div className="tool-section">
              <div className="tool-section-title">输入参数</div>
              <pre className="tool-code">
                {JSON.stringify(tool.arguments, null, 2)}
              </pre>
            </div>
            
            <div className="tool-section">
              <div className="tool-section-title">执行结果</div>
              {tool.error ? (
                <div className="tool-error">
                  ❌ 错误: {tool.error}
                </div>
              ) : (
                <div className="tool-result">
                  {tool.result}
                </div>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}