import { useEffect, useRef, useState } from "react";
import {
  ApprovalRequest, XplogentEvent, XplogentSocket,
  deleteSession, getSessionMessages, getSessions, getSkills, newSession,
  renameSession, searchMemory,
} from "./api";
import { GenChoice, ModelBar } from "./ModelBar";
import { MissionControl } from "./MissionControl";
import { Settings } from "./Settings";
import { Schedules } from "./Schedules";
import { Council } from "./Council";
import { Guide } from "./Guide";
import { Markdown } from "./Markdown";

interface LogLine {
  kind: "assistant" | "tool" | "result" | "note" | "user";
  text: string;
  ok?: boolean;
}

type Tab = "chat" | "council" | "mission" | "schedules" | "settings" | "guide";

export function App() {
  const [tab, setTab] = useState<Tab>("chat");
  const tabs: [Tab, string][] = [
    ["chat", "Chat"], ["council", "Council"], ["mission", "Mission Control"],
    ["schedules", "Schedules"], ["settings", "Settings"], ["guide", "Guide"],
  ];
  return (
    <div className="root">
      <nav className="topnav">
        <span className="brand">🧠 Xplogent</span>
        {tabs.map(([id, label]) => (
          <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>
            {label}
          </button>
        ))}
      </nav>
      {tab === "chat" && <ChatView />}
      {tab === "council" && <Council />}
      {tab === "mission" && <MissionControl />}
      {tab === "schedules" && <Schedules />}
      {tab === "settings" && <Settings />}
      {tab === "guide" && <Guide />}
    </div>
  );
}

interface Usage {
  input_tokens?: number; output_tokens?: number;
  session_input?: number; session_output?: number;
  session_cost?: number;
  context_used?: number; context_limit?: number;
}

function UsageBar({ u }: { u: Usage }) {
  const used = u.context_used ?? 0;
  const limit = u.context_limit ?? 0;
  const pct = limit ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  const sess = (u.session_input ?? 0) + (u.session_output ?? 0);
  return (
    <div className="usagebar">
      {u.input_tokens != null && (
        <span>turn: <b>{u.input_tokens}</b> in / <b>{u.output_tokens}</b> out</span>
      )}
      {sess > 0 && <span>session: <b>{sess.toLocaleString()}</b> tok</span>}
      {!!u.session_cost && <span>~<b>${u.session_cost.toFixed(4)}</b></span>}
      <span className="ctx">
        context
        <span className="meter"><span className="fill" style={{ width: `${pct}%` }} /></span>
        {used.toLocaleString()} / {limit.toLocaleString()}
      </span>
    </div>
  );
}

function ChatView() {
  const [skills, setSkills] = useState<any[]>([]);
  const [sessions, setSessions] = useState<any[]>([]);
  const [search, setSearch] = useState("");
  const [hits, setHits] = useState<any[]>([]);
  const [log, setLog] = useState<LogLine[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [approval, setApproval] = useState<ApprovalRequest | null>(null);
  const [gen, setGen] = useState<GenChoice>({ model: "", effort: "off", thinking: false });
  const sock = useRef<XplogentSocket | null>(null);
  const bottom = useRef<HTMLDivElement | null>(null);
  const sessionId = useRef<number | null>(
    Number(localStorage.getItem("xplogent_session")) || null
  );
  const [activeId, setActiveId] = useState<number | null>(sessionId.current);

  // Append to the streaming assistant line, or start a new one.
  const pushAssistantToken = (text: string) =>
    setLog((l) => {
      const last = l[l.length - 1];
      if (last && last.kind === "assistant") {
        return [...l.slice(0, -1), { ...last, text: last.text + text }];
      }
      return [...l, { kind: "assistant", text }];
    });

  const handleEvent = (ev: XplogentEvent) => {
    switch (ev.type) {
      case "token":
        pushAssistantToken(String(ev.text ?? ""));
        break;
      case "tool_call":
        setLog((l) => [...l, { kind: "tool", text: `→ ${ev.tool} ${JSON.stringify(ev.arguments ?? {})}` }]);
        break;
      case "tool_result":
        setLog((l) => [...l, { kind: "result", text: String(ev.output ?? ""), ok: Boolean(ev.ok) }]);
        break;
      case "memory":
        setLog((l) => [...l, { kind: "note", text: `🧠 recalled ${ev.facts} facts, ${ev.skills} skills` }]);
        break;
      case "skill":
        setLog((l) => [...l, { kind: "note", text: `✨ learned ${ev.facts} fact(s)${ev.skill ? `, skill '${ev.skill}'` : ""}` }]);
        refreshSkills();
        break;
      case "usage":
        setUsage(ev as unknown as Usage);
        break;
      case "session":
        sessionId.current = Number(ev.id);
        localStorage.setItem("xplogent_session", String(ev.id));
        break;
      case "approval_required":
        setApproval(ev as unknown as ApprovalRequest);
        break;
      case "done":
        setBusy(false);
        refreshSkills();
        refreshSessions();
        break;
    }
  };

  const refreshSkills = () => getSkills().then((s) => setSkills(s.skills)).catch(() => {});
  const refreshSessions = () => getSessions().then((s) => setSessions(s.sessions)).catch(() => {});

  const runSearch = (q: string) => {
    setSearch(q);
    if (!q.trim()) { setHits([]); return; }
    searchMemory(q).then((r) => setHits(r.messages ?? [])).catch(() => setHits([]));
  };

  const stop = () => { sock.current?.cancel(); setBusy(false); };

  const rename = async (id: number, current: string) => {
    const title = window.prompt("Rename chat:", current);
    if (title && title.trim()) { await renameSession(id, title.trim()); refreshSessions(); }
  };

  const connect = () => {
    sock.current?.close();
    sock.current = new XplogentSocket(handleEvent, sessionId.current);
  };

  const loadSession = (id: number | null) => {
    sessionId.current = id;
    setActiveId(id);
    if (id) {
      localStorage.setItem("xplogent_session", String(id));
      getSessionMessages(id).then((r) => {
        setLog(r.messages.map((m: any) => ({
          kind: m.role === "user" ? "user" : "assistant", text: m.content,
        })));
      }).catch(() => setLog([]));
    } else {
      setLog([]);
    }
    connect();
  };

  useEffect(() => {
    refreshSkills();
    refreshSessions();
    loadSession(sessionId.current);
    return () => sock.current?.close();
  }, []);

  useEffect(() => bottom.current?.scrollIntoView({ behavior: "smooth" }), [log]);

  const newChat = async () => {
    const { id } = await newSession();
    loadSession(id);
    refreshSessions();
  };

  const removeSession = async (id: number) => {
    await deleteSession(id);
    if (id === activeId) { localStorage.removeItem("xplogent_session"); loadSession(null); }
    refreshSessions();
  };

  const send = () => {
    if (!input.trim() || busy) return;
    setLog((l) => [...l, { kind: "user", text: input }]);
    sock.current?.sendTask(input, {
      model: gen.model || undefined, effort: gen.effort, thinking: gen.thinking,
    });
    setInput("");
    setBusy(true);
  };

  const resolve = (allowed: boolean) => {
    if (approval) sock.current?.resolveApproval(approval.id, allowed);
    setApproval(null);
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <h1>🧠 Xplogent</h1>
        <button className="newchat" onClick={newChat}>+ New chat</button>
        <input className="search" value={search} placeholder="🔍 search chats…"
               onChange={(e) => runSearch(e.target.value)} />
        {search && (
          <ul className="chatlist">
            {hits.length === 0 && <p className="dim">no matches</p>}
            {hits.map((h, i) => (
              <li key={i}>
                <button className="open" title={h.content}
                        onClick={() => { loadSession(h.session_id); runSearch(""); }}>
                  <span className="dim">[{h.role}]</span> {String(h.content).slice(0, 50)}
                </button>
              </li>
            ))}
          </ul>
        )}
        <h2>Chats</h2>
        {sessions.length === 0 && <p className="dim">no chats yet</p>}
        <ul className="chatlist">
          {sessions.map((s) => (
            <li key={s.id} className={s.id === activeId ? "active" : ""}>
              <button className="open" onClick={() => loadSession(s.id)}
                      onDoubleClick={() => rename(s.id, s.title)} title="double-click to rename">
                {s.title || "chat"} <span className="dim">· {s.message_count ?? 0}</span>
              </button>
              <button className="x" onClick={() => removeSession(s.id)}>✕</button>
            </li>
          ))}
        </ul>
        <h2>Learned skills</h2>
        {skills.length === 0 && <p className="dim">none yet</p>}
        <ul>
          {skills.map((s) => (
            <li key={s.name} title={`${s.description} — ${s.level ?? ""}`}>
              <b>{s.name}</b>{" "}
              <span className="stars">{"★".repeat(s.stars ?? 1)}{"☆".repeat(3 - (s.stars ?? 1))}</span>
              <span className="dim"> ×{s.uses}</span>
            </li>
          ))}
        </ul>
      </aside>

      <main className="chat">
        <ModelBar value={gen} onChange={setGen} />
        <div className="log">
          {log.map((line, i) => (
            <div key={i} className={`line ${line.kind}`}>
              {line.kind === "assistant"
                ? <Markdown text={line.text} />
                : <>{line.kind === "result" ? (line.ok ? "✓ " : "✗ ") : ""}{line.text}</>}
            </div>
          ))}
          <div ref={bottom} />
        </div>

        {usage && <UsageBar u={usage} />}

        <div className="composer">
          <input
            value={input}
            placeholder="Ask Xplogent to do something…"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
          />
          {busy
            ? <button className="stop" onClick={stop}>Stop</button>
            : <button onClick={send}>Send</button>}
        </div>
      </main>

      {approval && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>⚠ Approval required</h3>
            <p><b>{approval.tool}</b> — risk <b>{approval.risk}</b></p>
            {approval.reason && <p className="dim">{approval.reason}</p>}
            <pre>{JSON.stringify(approval.arguments, null, 2)}</pre>
            <div className="modal-actions">
              <button className="deny" onClick={() => resolve(false)}>Deny</button>
              <button className="allow" onClick={() => resolve(true)}>Approve</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
