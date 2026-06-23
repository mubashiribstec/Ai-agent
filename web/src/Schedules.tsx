import { useEffect, useState } from "react";
import { Calendar, Pause, Play, Trash2 } from "lucide-react";
import {
  Schedule, addSchedule, deleteSchedule, getSchedules, toggleSchedule,
} from "./api";
import { useToast } from "./components/Toast";

const fmt = (t: number | null) =>
  t ? new Date(t * 1000).toLocaleString() : "—";

export function Schedules() {
  const [items, setItems] = useState<Schedule[]>([]);
  const [prompt, setPrompt] = useState("");
  const [when, setWhen] = useState("");
  const [mode, setMode] = useState("agent");
  const [error, setError] = useState("");
  const toast = useToast();

  const refresh = () => getSchedules().then((r) => setItems(r.schedules)).catch(() => {});
  useEffect(() => { refresh(); }, []);

  const add = async () => {
    setError("");
    if (!prompt.trim() || !when.trim()) return;
    const res = await addSchedule({ prompt, schedule: when, mode });
    if (res.ok) {
      setPrompt(""); setWhen("");
      refresh(); toast("scheduled", "success");
    } else {
      setError(res.detail || "could not schedule that");
    }
  };

  return (
    <div className="settings">
      <div className="page-head"><h1><Calendar size={22} /> Schedules</h1></div>
      <div className="card">
        <h3>New scheduled job</h3>
        <p className="dim">
          Runs unattended with full tools/memory (auto-approves up to high risk;
          critical stays blocked).
        </p>
        <label>What should the agent do?
          <input value={prompt} placeholder="e.g. summarize my unread email"
                 onChange={(e) => setPrompt(e.target.value)} />
        </label>
        <div className="row">
          <label style={{ flex: 1 }}>When
            <input value={when} placeholder='e.g. "every day at 9am" or "every 2 hours"'
                   onChange={(e) => setWhen(e.target.value)} />
          </label>
          <label>Mode
            <select value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="agent">single agent</option>
              <option value="team">agent team</option>
            </select>
          </label>
        </div>
        <p className="dim">
          Examples: <code>every day at 9am</code> · <code>every 2 hours</code> ·
          <code> every monday at 08:00</code> · <code>in 30 minutes</code> ·
          <code> 0 9 * * 1</code> (cron)
        </p>
        {error && <p className="warn">{error}</p>}
        <button className="btn primary" onClick={add}>Schedule it</button>
      </div>

      <div className="card">
        <h3>Scheduled jobs</h3>
        {items.length === 0 && <p className="dim">nothing scheduled yet</p>}
        <ul className="list">
          {items.map((s) => (
            <li key={s.id}>
              <span style={{ flex: 1 }}>
                <b>{s.name}</b> <span className="dim">· {s.spec}</span><br />
                <span className="dim">
                  next {fmt(s.next_run)} · last {fmt(s.last_run)}
                  {s.last_status ? ` (${s.last_status})` : ""}
                </span>
              </span>
              <button onClick={() => toggleSchedule(s.id).then(refresh)}>
                {s.enabled ? <Pause size={13} /> : <Play size={13} />}{s.enabled ? "pause" : "resume"}
              </button>
              <button className="x" aria-label="delete"
                onClick={() => deleteSchedule(s.id).then(refresh)}><Trash2 size={14} /></button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
