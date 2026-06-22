import { useEffect, useRef, useState } from "react";
import {
  ApprovalRequest, XplogentEvent, XplogentSocket,
  getSessionMessages, getSkills, newSession,
} from "./api";
import { GenChoice, ModelBar } from "./ModelBar";
import { MissionControl } from "./MissionControl";
import { Settings } from "./Settings";
import { Guide } from "./Guide";

interface LogLine {
  kind: "assistant" | "tool" | "result" | "note" | "user";
  text: string;
  ok?: boolean;
}

type Tab = "chat" | "mission" | "settings" | "guide";

export function App() {
  const [tab, setTab] = useState<Tab>("chat");
  const tabs: [Tab, string][] = [
    ["chat", "Chat"], ["mission", "Mission Control"],
    ["settings", "Settings"], ["guide", "Guide"],
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
      {tab === "mission" && <MissionControl />}
      {tab === "settings" && <Settings />}
      {tab === "guide" && <Guide />}
    </div>
  );
}

function ChatView() {
  const [skills, setSkills] = useState<{ name: string; description: string; uses: number }[]>([]);
  const [log, setLog] = useState<LogLine[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [approval, setApproval] = useState<ApprovalRequest | null>(null);
  const [gen, setGen] = useState<GenChoice>({ model: "", effort: "off", thinking: false });
  const sock = useRef<XplogentSocket | null>(null);
  const bottom = useRef<HTMLDivElement | null>(null);
  const sessionId = useRef<number | null>(
    Number(localStorage.getItem("xplogent_session")) || null
  );

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
      case "session":
        sessionId.current = Number(ev.id);
        localStorage.setItem("xplogent_session", String(ev.id));
        break;
      case "approval_required":
        setApproval(ev as unknown as ApprovalRequest);
        break;
      case "done":
        setBusy(false);
        break;
    }
  };

  const refreshSkills = () => getSkills().then((s) => setSkills(s.skills)).catch(() => {});

  const connect = () => {
    sock.current?.close();
    sock.current = new XplogentSocket(handleEvent, sessionId.current);
  };

  useEffect(() => {
    refreshSkills();
    // Restore the previous conversation, then connect to that session.
    if (sessionId.current) {
      getSessionMessages(sessionId.current).then((r) => {
        setLog(r.messages.map((m: any) => ({
          kind: m.role === "user" ? "user" : "assistant", text: m.content,
        })));
      }).catch(() => {});
    }
    connect();
    return () => sock.current?.close();
  }, []);

  useEffect(() => bottom.current?.scrollIntoView({ behavior: "smooth" }), [log]);

  const newChat = async () => {
    const { id } = await newSession();
    sessionId.current = id;
    localStorage.setItem("xplogent_session", String(id));
    setLog([]);
    connect();
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
        <h2>Learned skills</h2>
        {skills.length === 0 && <p className="dim">none yet</p>}
        <ul>
          {skills.map((s) => (
            <li key={s.name} title={s.description}>
              <b>{s.name}</b> <span className="dim">×{s.uses}</span>
            </li>
          ))}
        </ul>
      </aside>

      <main className="chat">
        <ModelBar value={gen} onChange={setGen} />
        <div className="log">
          {log.map((line, i) => (
            <div key={i} className={`line ${line.kind}`}>
              {line.kind === "result" ? (line.ok ? "✓ " : "✗ ") : ""}
              {line.text}
            </div>
          ))}
          <div ref={bottom} />
        </div>

        <div className="composer">
          <input
            value={input}
            placeholder="Ask Xplogent to do something…"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
          />
          <button onClick={send} disabled={busy}>{busy ? "…" : "Send"}</button>
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
