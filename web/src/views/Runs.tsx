import { useEffect, useState } from "react";
import { Activity, RefreshCw } from "lucide-react";
import { RunInfo, getRun, getRunEvents, getRunMessages, getRuns } from "../api";

const fmtDur = (a: number, b: number | null) => {
  const s = Math.round(((b ?? Date.now() / 1000) - a));
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
};
const fmtTime = (t: number) => new Date(t * 1000).toLocaleString();

export function Runs() {
  const [runs, setRuns] = useState<RunInfo[]>([]);
  const [active, setActive] = useState<string[]>([]);
  const [sel, setSel] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [messages, setMessages] = useState<any[]>([]);

  const refresh = () => getRuns().then((r) => { setRuns(r.runs); setActive(r.active); }).catch(() => {});
  useEffect(() => { refresh(); }, []);

  const open = (id: string) => {
    setSel(id);
    getRun(id).then((r) => setMetrics(r.metrics ?? [])).catch(() => setMetrics([]));
    getRunEvents(id).then((r) => setEvents(r.events ?? [])).catch(() => setEvents([]));
    getRunMessages(id).then((r) => setMessages(r.messages ?? [])).catch(() => setMessages([]));
  };

  // Derive per-agent metrics from events for finished runs (no live snapshot).
  const derived = metrics.length ? metrics : Object.values(events.reduce((acc: any, e: any) => {
    const id = e.agent_id || "_";
    const m = acc[id] ?? (acc[id] = { agent_id: id, name: e.data?.agent_name || id, steps: 0, tool_calls: 0, input_tokens: 0, output_tokens: 0 });
    if (e.type === "step_start") m.steps++;
    if (e.type === "tool_call") m.tool_calls++;
    if (e.type === "usage") { m.input_tokens += e.data?.input_tokens || 0; m.output_tokens += e.data?.output_tokens || 0; }
    return acc;
  }, {})).filter((m: any) => m.agent_id !== "_");

  const timeline = events.filter((e) =>
    ["agent_spawn", "task_update", "tool_call", "agent_message", "run_end", "run_progress"].includes(e.type));

  return (
    <div className="runs">
      <div className="runs-list">
        <div className="page-head" style={{ padding: "16px 16px 8px" }}>
          <h1 style={{ fontSize: 18 }}><Activity size={18} /> Runs</h1>
          <button className="icon-btn" onClick={refresh} aria-label="refresh"><RefreshCw size={16} /></button>
        </div>
        {runs.length === 0 && <div className="empty"><Activity size={26} /><div>No runs yet.<br />Launch a team in Mission Control.</div></div>}
        {runs.map((r) => (
          <div key={r.id} className={`run-item ${r.id === sel ? "active" : ""}`} onClick={() => open(r.id)}>
            <div className="g" title={r.goal}>{r.goal || "(team run)"}</div>
            <div className="row" style={{ justifyContent: "space-between", marginTop: 4 }}>
              <span className={`badge ${r.status === "done" ? "ok" : active.includes(r.id) ? "warn" : ""}`}>
                {active.includes(r.id) ? "running" : r.status}</span>
              <span className="dim" style={{ fontSize: 11 }}>{r.mode} · {fmtDur(r.started_at, r.ended_at)}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="run-detail">
        {!sel ? <div className="empty"><Activity size={30} /><div>Select a run to inspect its timeline, agents, and messages.</div></div> : (
          <>
            <h1 style={{ fontSize: 20, marginTop: 0 }}>Run {sel.slice(0, 8)}</h1>
            <p className="dim">{runs.find((r) => r.id === sel)?.started_at && fmtTime(runs.find((r) => r.id === sel)!.started_at)}</p>

            <h3 style={{ marginTop: 20 }}>Agents</h3>
            {derived.length === 0 ? <p className="dim">no agent metrics</p> : (
              <div className="grid2">
                {derived.map((m: any) => (
                  <div className="card" key={m.agent_id} style={{ padding: 14 }}>
                    <b>{m.name}</b>
                    <div className="agent-stats" style={{ marginTop: 8 }}>
                      <span>steps {m.steps}</span><span className="tool">tools {m.tool_calls}</span>
                      <span>{(m.input_tokens + m.output_tokens).toLocaleString()} tok</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <h3 style={{ marginTop: 24 }}>Timeline</h3>
            <div className="timeline">
              {timeline.length === 0 && <p className="dim">no events</p>}
              {timeline.map((e, i) => (
                <div className="tl-item" key={i}>
                  <span className="dim">{e.data?.agent_name || ""}</span>{" "}
                  <b>{e.type}</b>{" "}
                  {e.data?.tool ? <span className="mono">{e.data.tool}</span> : null}
                  {e.data?.title ? <span> — {e.data.title} ({e.data.status})</span> : null}
                  {e.data?.content ? <span> — {String(e.data.content).slice(0, 80)}</span> : null}
                </div>
              ))}
            </div>

            <h3 style={{ marginTop: 24 }}>Agent messages</h3>
            {messages.length === 0 ? <p className="dim">none</p> : (
              <div className="msg-feed">
                {messages.map((m, i) => (
                  <div className="m" key={i}><b>{m.sender}</b> <span className="arrow">→ {m.recipient || "all"}</span>: {m.content}</div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
