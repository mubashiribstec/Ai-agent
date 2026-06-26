import { useEffect, useState } from "react";
import { CheckCircle2, FlaskConical, Play, Plus, Trash2, XCircle } from "lucide-react";
import { EvalCase, EvalRun, EvalSuite, deleteEval, getEvals, runEval, saveEval } from "../api";
import { useToast } from "../components/Toast";

const pct = (r: EvalRun) => (r.total ? Math.round((r.passed / r.total) * 100) : 0);

// Tiny pass-rate sparkline from the suite's recent runs (newest-first → reversed).
function Spark({ runs }: { runs: EvalRun[] }) {
  if (runs.length === 0) return <span className="dim">never run</span>;
  const pts = [...runs].reverse().map((r) => pct(r));
  const W = 120, H = 28;
  const step = pts.length > 1 ? W / (pts.length - 1) : 0;
  const d = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${i * step} ${H - (p / 100) * H}`).join(" ");
  return (
    <svg className="spark" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="pass rate trend">
      <path d={d} fill="none" />
      <circle cx={(pts.length - 1) * step} cy={H - (pts[pts.length - 1] / 100) * H} r={3} />
    </svg>
  );
}

export function Evals() {
  const toast = useToast();
  const [evals, setEvals] = useState<EvalSuite[]>([]);
  const [busy, setBusy] = useState<number | null>(null);
  const [editing, setEditing] = useState<{ id?: number; name: string; cases: EvalCase[] } | null>(null);

  const reload = () => getEvals().then((r) => setEvals(r.evals)).catch(() => {});
  useEffect(() => { reload(); }, []);

  const run = async (id: number) => {
    setBusy(id);
    const res = await runEval(id);
    setBusy(null);
    if (res.ok === false) toast(res.error || "run failed", "error");
    else toast(`${res.passed}/${res.total} passed · score ${res.score}`, res.passed === res.total ? "success" : "info");
    reload();
  };

  const save = async () => {
    if (!editing) return;
    const cases = editing.cases.filter((c) => c.prompt.trim());
    if (!editing.name.trim() || cases.length === 0) { toast("name + at least one case required", "error"); return; }
    const res = await saveEval({ id: editing.id, name: editing.name.trim(), cases });
    if (res.ok) { toast("suite saved", "success"); setEditing(null); reload(); }
    else toast("save failed", "error");
  };

  if (editing) {
    return (
      <div className="pane"><div className="pane-wide">
        <div className="page-head"><h1><FlaskConical size={22} /> {editing.id ? "Edit" : "New"} suite</h1></div>
        <div className="card">
          <label className="lbl-sm">Suite name</label>
          <input value={editing.name} placeholder="e.g. coding-quality" onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
          <label className="lbl-sm" style={{ marginTop: 14 }}>Cases <span className="dim">— prompt + the criteria the LLM judge scores against</span></label>
          {editing.cases.map((c, i) => (
            <div key={i} className="card" style={{ padding: 12, marginTop: 8 }}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <b className="dim">case {i + 1}</b>
                <button className="x" onClick={() => setEditing({ ...editing, cases: editing.cases.filter((_, j) => j !== i) })}><Trash2 size={14} /></button>
              </div>
              <textarea className="md-edit" rows={2} placeholder="prompt to send the agent…" value={c.prompt}
                onChange={(e) => setEditing({ ...editing, cases: editing.cases.map((x, j) => j === i ? { ...x, prompt: e.target.value } : x) })} />
              <textarea className="md-edit" style={{ marginTop: 6 }} rows={2} placeholder="success criteria (what a good answer must contain/do)…" value={c.criteria}
                onChange={(e) => setEditing({ ...editing, cases: editing.cases.map((x, j) => j === i ? { ...x, criteria: e.target.value } : x) })} />
            </div>
          ))}
          <button className="btn" style={{ marginTop: 8 }} onClick={() => setEditing({ ...editing, cases: [...editing.cases, { prompt: "", criteria: "" }] })}>
            <Plus size={14} /> Add case</button>
          <div className="row" style={{ gap: 8, marginTop: 16 }}>
            <button className="btn primary" onClick={save}>Save suite</button>
            <button className="btn" onClick={() => setEditing(null)}>Cancel</button>
          </div>
        </div>
      </div></div>
    );
  }

  return (
    <div className="pane"><div className="pane-wide">
      <div className="page-head">
        <h1><FlaskConical size={22} /> Evals</h1>
        <button className="btn primary" onClick={() => setEditing({ name: "", cases: [{ prompt: "", criteria: "" }] })}><Plus size={14} /> New suite</button>
      </div>
      <p className="dim">Score the agent against repeatable test cases. Each answer is graded by an LLM judge so you can track quality over time.</p>

      {evals.length === 0 && <div className="empty"><FlaskConical size={28} /><div>No suites yet. Create one to start measuring quality.</div></div>}

      {evals.map((s) => {
        const last = s.runs[0];
        return (
          <div key={s.id} className="card">
            <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <h3 style={{ margin: 0 }}>{s.name}</h3>
                <span className="dim">{s.cases.length} case(s)</span>
              </div>
              <div className="row" style={{ gap: 6 }}>
                <Spark runs={s.runs} />
                {last && <span className={`badge ${last.passed === last.total ? "ok" : "warn"}`}>{pct(last)}%</span>}
                <button className="btn primary" disabled={busy === s.id} onClick={() => run(s.id)}>
                  <Play size={14} /> {busy === s.id ? "Running…" : "Run"}</button>
                <button className="btn" onClick={() => setEditing({ id: s.id, name: s.name, cases: s.cases.map((c) => ({ ...c })) })}>Edit</button>
                <button className="x" onClick={() => deleteEval(s.id).then(reload)}><Trash2 size={14} /></button>
              </div>
            </div>
            {last && (
              <div className="eval-cases">
                {s.cases.slice(0, last.total).map((c, i) => (
                  <div key={i} className="row" style={{ gap: 6, marginTop: 6 }}>
                    {i < last.passed ? <CheckCircle2 size={15} className="ok-i" /> : <XCircle size={15} className="bad-i" />}
                    <span className="dim ellipsis">{c.prompt}</span>
                  </div>
                ))}
                <span className="dim" style={{ fontSize: 12, marginTop: 6, display: "block" }}>
                  last run · {last.model} · score {last.score}</span>
              </div>
            )}
          </div>
        );
      })}
    </div></div>
  );
}
