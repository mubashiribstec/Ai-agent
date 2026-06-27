import { useEffect, useState } from "react";
import { CheckCircle2, FlaskConical, GitCompare, Play, Plus, Trash2, Trophy, XCircle } from "lucide-react";
import {
  AbResult, AbVariant, EvalCase, EvalRun, EvalSuite,
  deleteEval, getEvals, promoteEval, runEval, runEvalAB, saveEval,
} from "../api";
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
  const [ab, setAb] = useState<EvalSuite | null>(null);

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

  if (ab) return <AbPanel suite={ab} onClose={() => { setAb(null); reload(); }} />;

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
                <button className="btn" title="A/B test prompts/models" onClick={() => setAb(s)}><GitCompare size={14} /> A/B</button>
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

// A/B-test a suite across prompt/model variants, then promote the winner.
function AbPanel({ suite, onClose }: { suite: EvalSuite; onClose: () => void }) {
  const toast = useToast();
  const [variants, setVariants] = useState<AbVariant[]>([
    { name: "A", system_prompt: "", model: "" },
    { name: "B", system_prompt: "", model: "" },
  ]);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<AbResult[]>([]);
  const [winner, setWinner] = useState("");

  const patch = (i: number, p: Partial<AbVariant>) =>
    setVariants(variants.map((v, j) => (j === i ? { ...v, ...p } : v)));

  const run = async () => {
    setRunning(true); setResults([]);
    const res = await runEvalAB(suite.id, variants.filter((v) => v.name.trim()));
    setRunning(false);
    if (!res.ok) { toast(res.error || "A/B run failed", "error"); return; }
    setResults(res.variants); setWinner(res.winner);
    toast(`winner: ${res.winner}`, "success");
  };
  const promote = async () => {
    const w = results.find((r) => r.name === winner);
    if (!w) return;
    await promoteEval({ system_prompt: w.system_prompt, model: w.model });
    toast(`promoted variant ${winner} to live config`, "success");
  };

  return (
    <div className="pane"><div className="pane-wide">
      <div className="page-head"><h1><GitCompare size={22} /> A/B · {suite.name}</h1>
        <button className="btn" onClick={onClose}>Back</button></div>
      <p className="dim">Run the suite's {suite.cases.length} case(s) under each variant and promote the winner.
        Leave a field blank to use the current default.</p>

      <div className="ab-grid">
        {variants.map((v, i) => (
          <div key={i} className="card">
            <input className="ab-name" value={v.name} onChange={(e) => patch(i, { name: e.target.value })} />
            <label className="lbl-sm" style={{ marginTop: 8 }}>System prompt</label>
            <textarea className="md-edit" rows={5} placeholder="(default prompt)" value={v.system_prompt}
              onChange={(e) => patch(i, { system_prompt: e.target.value })} />
            <label className="lbl-sm" style={{ marginTop: 8 }}>Model</label>
            <input placeholder="(default model)" value={v.model} onChange={(e) => patch(i, { model: e.target.value })} />
            {results.find((r) => r.name === v.name) && (() => {
              const r = results.find((x) => x.name === v.name)!;
              return <div className={`ab-score ${winner === v.name ? "win" : ""}`}>
                {winner === v.name && <Trophy size={14} />} {r.passed}/{r.total} · score {r.score}</div>;
            })()}
          </div>
        ))}
      </div>
      <div className="row" style={{ gap: 8, marginTop: 12 }}>
        <button className="btn" onClick={() => setVariants([...variants, { name: String.fromCharCode(65 + variants.length), system_prompt: "", model: "" }])}>
          <Plus size={14} /> Variant</button>
        <button className="btn primary" disabled={running} onClick={run}><Play size={14} /> {running ? "Running…" : "Run A/B"}</button>
        {winner && <button className="btn" onClick={promote}><Trophy size={14} /> Promote {winner}</button>}
      </div>
    </div></div>
  );
}
