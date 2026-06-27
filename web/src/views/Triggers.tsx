import { useEffect, useState } from "react";
import { Copy, FileClock, Plus, Power, Trash2, Webhook, Zap } from "lucide-react";
import { Trigger, createTrigger, deleteTrigger, getTriggers, toggleTrigger } from "../api";
import { useToast } from "../components/Toast";

const fmt = (t: number | null) => (t ? new Date(t * 1000).toLocaleString() : "never");

export function Triggers() {
  const toast = useToast();
  const [list, setList] = useState<Trigger[]>([]);
  const [type, setType] = useState<"webhook" | "file">("webhook");
  const [name, setName] = useState("");
  const [spec, setSpec] = useState("");
  const [prompt, setPrompt] = useState("");
  const [mode, setMode] = useState("agent");

  const reload = () => getTriggers().then((r) => setList(r.triggers)).catch(() => {});
  useEffect(() => { reload(); }, []);

  const create = async () => {
    if (!name.trim() || !prompt.trim() || (type === "file" && !spec.trim())) {
      toast("name, prompt" + (type === "file" ? " and path" : "") + " are required", "error"); return;
    }
    const res = await createTrigger({ name: name.trim(), type, prompt: prompt.trim(), spec: spec.trim(), mode });
    if (res.ok) { toast("trigger created", "success"); setName(""); setSpec(""); setPrompt(""); reload(); }
  };

  const webhookUrl = (t: Trigger) => `${location.origin}/triggers/webhook/${t.spec}`;

  return (
    <div className="pane">
      <div className="pane-wide">
        <div className="page-head"><h1><Zap size={22} /> Triggers</h1>
          <span className="dim">event-driven · the agent acts on its own</span></div>
        <p className="dim">Run the agent automatically when a webhook is called or a watched file changes —
          beyond the time-based Schedules.</p>

        <div className="card">
          <h3><Plus size={16} /> New trigger</h3>
          <div className="row wrap" style={{ gap: 10 }}>
            <label className="bud"><span className="lbl-sm">Type</span>
              <select value={type} onChange={(e) => setType(e.target.value as any)}>
                <option value="webhook">webhook (inbound POST)</option>
                <option value="file">file / folder change</option>
              </select></label>
            <label className="bud" style={{ flex: 1, minWidth: 180 }}><span className="lbl-sm">Name</span>
              <input value={name} placeholder="e.g. on new invoice" onChange={(e) => setName(e.target.value)} style={{ width: "100%" }} /></label>
            <label className="bud"><span className="lbl-sm">Run as</span>
              <select value={mode} onChange={(e) => setMode(e.target.value)}><option value="agent">agent</option><option value="team">team</option></select></label>
          </div>
          {type === "file" && (
            <><label className="lbl-sm" style={{ marginTop: 10 }}>Path to watch (file or folder)</label>
              <input value={spec} placeholder="~/inbox" onChange={(e) => setSpec(e.target.value)} /></>
          )}
          <label className="lbl-sm" style={{ marginTop: 10 }}>Prompt <span className="dim">— event context (request body / changed path) is appended</span></label>
          <textarea className="md-edit" rows={3} value={prompt} placeholder="Summarize what just arrived and add it to my notes."
            onChange={(e) => setPrompt(e.target.value)} />
          <button className="btn primary" style={{ marginTop: 10 }} onClick={create}><Plus size={14} /> Create trigger</button>
        </div>

        <div className="card">
          <h3>Active triggers ({list.length})</h3>
          {list.length === 0 && <p className="dim">none yet</p>}
          <ul className="list">
            {list.map((t) => (
              <li key={t.id}>
                <span style={{ color: t.type === "webhook" ? "var(--cyan)" : "var(--magenta)" }}>
                  {t.type === "webhook" ? <Webhook size={15} /> : <FileClock size={15} />}</span>
                <span style={{ flex: 1 }}>
                  <b>{t.name}</b> <span className="dim">· {t.mode} · last: {fmt(t.last_fired)}{t.last_status ? ` (${t.last_status})` : ""}</span><br />
                  {t.type === "webhook"
                    ? <span className="dim mono" style={{ fontSize: 12 }}>POST {webhookUrl(t)}
                        <button className="linkx" onClick={() => { navigator.clipboard?.writeText(webhookUrl(t)); toast("URL copied", "success"); }}>
                          <Copy size={12} /></button></span>
                    : <span className="dim mono" style={{ fontSize: 12 }}>watching {t.spec}</span>}
                </span>
                <button className={`icon-btn ${t.enabled ? "" : "off"}`} title={t.enabled ? "enabled" : "disabled"}
                  onClick={() => toggleTrigger(t.id).then(reload)}><Power size={15} /></button>
                <button className="x" onClick={() => deleteTrigger(t.id).then(reload)}><Trash2 size={14} /></button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
