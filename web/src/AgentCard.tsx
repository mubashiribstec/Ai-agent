import { controlAgent } from "./api";

export interface AgentState {
  agent_id: string;
  name: string;
  role: string;
  status: string;
  step: number;
  current_tool?: string | null;
  tokens: number;
  toolCalls: number;
  lastMessage?: string;
}

const STATUS_COLOR: Record<string, string> = {
  running: "var(--accent)",
  paused: "var(--magenta)",
  done: "var(--green)",
  cancelled: "var(--red)",
  idle: "var(--dim)",
};

export function AgentCard({ a }: { a: AgentState }) {
  const live = a.status === "running" || a.status === "paused";
  return (
    <div className="agent-card">
      <div className="agent-head">
        <span className="dot" style={{ background: STATUS_COLOR[a.status] ?? "var(--dim)" }} />
        <b>{a.name}</b>
        <span className="dim role">{a.role}</span>
        <span className="status" style={{ color: STATUS_COLOR[a.status] }}>{a.status}</span>
      </div>
      <div className="agent-stats">
        <span>step {a.step}</span>
        <span>{a.toolCalls} tools</span>
        <span>{a.tokens} tok</span>
        {a.current_tool && <span className="tool">⚙ {a.current_tool}</span>}
      </div>
      {a.lastMessage && <div className="agent-last">{a.lastMessage}</div>}
      {live && (
        <div className="agent-actions">
          {a.status === "paused" ? (
            <button onClick={() => controlAgent(a.agent_id, "resume")}>Resume</button>
          ) : (
            <button onClick={() => controlAgent(a.agent_id, "pause")}>Pause</button>
          )}
          <button className="danger" onClick={() => controlAgent(a.agent_id, "cancel")}>Cancel</button>
        </div>
      )}
    </div>
  );
}
