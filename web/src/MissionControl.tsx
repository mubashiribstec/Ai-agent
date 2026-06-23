import { useRef, useState } from "react";
import { LayoutGrid, Rocket } from "lucide-react";
import { MonitorSocket, XplogentEvent, orchestrate } from "./api";
import { AgentCard, AgentState } from "./AgentCard";
import { TaskBoard, TaskState } from "./TaskBoard";
import { AgentMsg, MessageFeed } from "./MessageFeed";

export function MissionControl() {
  const [goal, setGoal] = useState("");
  const [maxConcurrent, setMaxConcurrent] = useState(3);
  const [autoApprove, setAutoApprove] = useState(true);
  const [running, setRunning] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [agents, setAgents] = useState<Record<string, AgentState>>({});
  const [tasks, setTasks] = useState<Record<string, TaskState>>({});
  const [messages, setMessages] = useState<AgentMsg[]>([]);
  const sock = useRef<MonitorSocket | null>(null);

  const upsertAgent = (id: string, patch: Partial<AgentState>) =>
    setAgents((prev) => {
      const cur = prev[id] ?? {
        agent_id: id, name: String(patch.name ?? id), role: String(patch.role ?? ""),
        status: "running", step: 0, tokens: 0, toolCalls: 0,
      };
      return { ...prev, [id]: { ...cur, ...patch } };
    });

  const handle = (ev: XplogentEvent) => {
    const id = String(ev.agent_id ?? "");
    switch (ev.type) {
      case "agent_spawn":
        upsertAgent(id, { name: String(ev.agent_name), role: String(ev.role), status: "running" });
        break;
      case "agent_status":
        upsertAgent(id, { status: String(ev.status), step: Number(ev.step ?? 0),
                          current_tool: (ev.current_tool as string) ?? null });
        break;
      case "step_start":
        upsertAgent(id, { step: Number(ev.step ?? 0) + 1, name: String(ev.agent_name) });
        break;
      case "token":
        upsertAgent(id, { tokens: (agents[id]?.tokens ?? 0) + Math.ceil(String(ev.text ?? "").length / 4) });
        break;
      case "tool_call":
        upsertAgent(id, { toolCalls: (agents[id]?.toolCalls ?? 0) + 1, current_tool: String(ev.tool) });
        break;
      case "message":
        upsertAgent(id, { lastMessage: String(ev.content) });
        break;
      case "task_update":
        setTasks((prev) => ({
          ...prev,
          [String(ev.id)]: {
            id: String(ev.id), title: String(ev.title), role: String(ev.role),
            status: String(ev.status), assignee: (ev.assignee as string) ?? null,
          },
        }));
        break;
      case "agent_message":
        setMessages((prev) => [...prev, {
          sender: String(ev.sender), recipient: (ev.recipient as string) ?? null,
          content: String(ev.content),
        }]);
        break;
    }
  };

  const launch = async () => {
    if (!goal.trim() || running) return;
    setAgents({}); setTasks({}); setMessages([]);
    setRunning(true);
    const { run_id } = await orchestrate({
      goal, max_concurrent: maxConcurrent, mode: "auto", auto_approve: autoApprove,
    });
    setRunId(run_id);
    sock.current = new MonitorSocket(run_id, handle);
  };

  return (
    <div className="mission">
      <div className="page-head" style={{ padding: "16px 24px 0" }}>
        <h1 style={{ fontSize: 20 }}><LayoutGrid size={20} /> Mission Control</h1>
      </div>
      <div className="mission-bar">
        <input
          value={goal}
          placeholder="Give the team a goal…"
          onChange={(e) => setGoal(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && launch()}
        />
        <label className="slider">
          max agents: <b>{maxConcurrent}</b>
          <input type="range" min={1} max={8} value={maxConcurrent}
                 onChange={(e) => setMaxConcurrent(Number(e.target.value))} />
        </label>
        <label className="slider" title="Agents run tools without prompting; critical ops still blocked.">
          <input type="checkbox" checked={autoApprove}
                 onChange={(e) => setAutoApprove(e.target.checked)} /> auto-approve
        </label>
        <button className="btn primary" onClick={launch} disabled={running && !!runId}>
          <Rocket size={16} /> Launch team</button>
      </div>

      <div className="mission-grid">
        <section>
          <h3>Agents</h3>
          <div className="agent-list">
            {Object.values(agents).length === 0 && <p className="dim">no active agents</p>}
            {Object.values(agents).map((a) => <AgentCard key={a.agent_id} a={a} />)}
          </div>
        </section>
        <section>
          <h3>Tasks</h3>
          <TaskBoard tasks={tasks} />
        </section>
        <section>
          <MessageFeed messages={messages} />
        </section>
      </div>
    </div>
  );
}
