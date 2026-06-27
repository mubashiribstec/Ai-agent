import { useEffect, useRef, useState } from "react";
import { Bot, GitBranch, Play, Plus, Save, Trash2, Wrench, Type as TypeIcon } from "lucide-react";
import {
  WfEdge, WfNode, WfResult, Workflow,
  deleteWorkflow, getWorkflows, runWorkflow, saveWorkflow,
} from "../api";
import { useToast } from "../components/Toast";

const uid = () => Math.random().toString(36).slice(2, 8);
const ICON = { input: TypeIcon, agent: Bot, tool: Wrench } as const;

export function Workflows() {
  const toast = useToast();
  const [list, setList] = useState<Workflow[]>([]);
  const [id, setId] = useState<number | undefined>();
  const [name, setName] = useState("My workflow");
  const [nodes, setNodes] = useState<WfNode[]>([]);
  const [edges, setEdges] = useState<WfEdge[]>([]);
  const [sel, setSel] = useState<string | null>(null);
  const [connectFrom, setConnectFrom] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, WfResult>>({});
  const [running, setRunning] = useState(false);
  const drag = useRef<{ id: string; dx: number; dy: number } | null>(null);
  const canvas = useRef<HTMLDivElement>(null);

  const reloadList = () => getWorkflows().then((r) => setList(r.workflows)).catch(() => {});
  useEffect(() => { reloadList(); }, []);

  const load = (w: Workflow) => {
    setId(w.id); setName(w.name);
    setNodes(w.graph.nodes || []); setEdges(w.graph.edges || []);
    setSel(null); setResults({}); setConnectFrom(null);
  };
  const newWf = () => { setId(undefined); setName("My workflow"); setNodes([]); setEdges([]); setResults({}); setSel(null); };

  const addNode = (type: WfNode["type"]) => {
    const n: WfNode = { id: uid(), type, name: type, x: 60 + nodes.length * 30, y: 80 + nodes.length * 24, config: {} };
    setNodes([...nodes, n]); setSel(n.id);
  };

  const onHeaderDown = (e: React.PointerEvent, n: WfNode) => {
    const rect = canvas.current!.getBoundingClientRect();
    drag.current = { id: n.id, dx: e.clientX - rect.left - n.x, dy: e.clientY - rect.top - n.y };
    setSel(n.id);
  };
  useEffect(() => {
    const move = (e: PointerEvent) => {
      if (!drag.current || !canvas.current) return;
      const rect = canvas.current.getBoundingClientRect();
      const x = Math.max(0, e.clientX - rect.left - drag.current.dx);
      const y = Math.max(0, e.clientY - rect.top - drag.current.dy);
      setNodes((ns) => ns.map((n) => (n.id === drag.current!.id ? { ...n, x, y } : n)));
    };
    const up = () => (drag.current = null);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
  }, []);

  const clickNode = (n: WfNode) => {
    if (connectFrom && connectFrom !== n.id) {
      if (!edges.some((e) => e.from === connectFrom && e.to === n.id))
        setEdges([...edges, { from: connectFrom, to: n.id }]);
      setConnectFrom(null);
    } else setSel(n.id);
  };

  const patch = (nid: string, cfg: Record<string, any>) =>
    setNodes(nodes.map((n) => (n.id === nid ? { ...n, config: { ...n.config, ...cfg } } : n)));
  const rename = (nid: string, nm: string) => setNodes(nodes.map((n) => (n.id === nid ? { ...n, name: nm } : n)));
  const removeNode = (nid: string) => {
    setNodes(nodes.filter((n) => n.id !== nid));
    setEdges(edges.filter((e) => e.from !== nid && e.to !== nid));
    setSel(null);
  };

  const save = async () => {
    const res = await saveWorkflow({ id, name, graph: { nodes, edges } });
    if (res.ok) { setId(res.workflow.id); toast("workflow saved", "success"); reloadList(); }
  };
  const run = async () => {
    if (id === undefined) { toast("save the workflow first", "error"); return; }
    setRunning(true); setResults({});
    const res = await runWorkflow(id);
    setRunning(false);
    if (!res.ok) { toast(res.error || "run failed", "error"); return; }
    const map: Record<string, WfResult> = {};
    res.results.forEach((r) => (map[r.node_id] = r));
    setResults(map);
    toast("workflow finished", "success");
  };

  const selNode = nodes.find((n) => n.id === sel);
  const center = (n: WfNode) => ({ x: n.x + 90, y: n.y + 26 });

  return (
    <div className="wf">
      <div className="wf-side">
        <div className="page-head" style={{ padding: "14px 14px 4px" }}>
          <h1 style={{ fontSize: 18 }}><GitBranch size={18} /> Workflows</h1>
          <button className="icon-btn" onClick={newWf} aria-label="new"><Plus size={16} /></button>
        </div>
        <div className="wf-list">
          {list.map((w) => (
            <div key={w.id} className={`wf-item ${w.id === id ? "active" : ""}`} onClick={() => load(w)}>
              <span style={{ flex: 1 }}>{w.name}</span>
              <button className="x" onClick={(e) => { e.stopPropagation(); deleteWorkflow(w.id).then(reloadList); }}><Trash2 size={13} /></button>
            </div>
          ))}
          {list.length === 0 && <p className="dim" style={{ padding: "0 14px" }}>no saved workflows</p>}
        </div>
        <div className="wf-palette">
          <span className="dim">Add node</span>
          <button className="btn" onClick={() => addNode("input")}><TypeIcon size={14} /> Input</button>
          <button className="btn" onClick={() => addNode("agent")}><Bot size={14} /> Agent</button>
          <button className="btn" onClick={() => addNode("tool")}><Wrench size={14} /> Tool</button>
        </div>
      </div>

      <div className="wf-main">
        <div className="wf-bar">
          <input value={name} onChange={(e) => setName(e.target.value)} style={{ maxWidth: 240 }} />
          <div className="spacer" />
          <button className="btn" onClick={save}><Save size={14} /> Save</button>
          <button className="btn primary" disabled={running} onClick={run}><Play size={14} /> {running ? "Running…" : "Run"}</button>
        </div>

        <div className="wf-canvas" ref={canvas} onClick={() => { setSel(null); setConnectFrom(null); }}>
          <svg className="wf-edges">
            {edges.map((e, i) => {
              const a = nodes.find((n) => n.id === e.from), b = nodes.find((n) => n.id === e.to);
              if (!a || !b) return null;
              const p = center(a), q = center(b);
              return <line key={i} x1={p.x} y1={p.y} x2={q.x} y2={q.y} className="wf-edge" markerEnd="url(#arrow)" />;
            })}
            <defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="3" orient="auto">
              <path d="M0,0 L8,3 L0,6 Z" /></marker></defs>
          </svg>

          {nodes.map((n) => {
            const Icon = ICON[n.type]; const r = results[n.id];
            return (
              <div key={n.id} className={`wf-node ${n.type} ${sel === n.id ? "sel" : ""} ${r ? r.status : ""}`}
                   style={{ left: n.x, top: n.y }} onClick={(e) => { e.stopPropagation(); clickNode(n); }}>
                <div className="wf-node-head" onPointerDown={(e) => onHeaderDown(e, n)}>
                  <Icon size={13} /> <b>{n.name}</b>
                </div>
                <div className="wf-node-body dim">{
                  n.type === "input" ? (n.config.value || "value…") :
                  n.type === "agent" ? (n.config.prompt || "prompt…") :
                  (n.config.tool || "tool…")
                }</div>
                <button className="wf-conn" title="connect to…"
                  onClick={(e) => { e.stopPropagation(); setConnectFrom(connectFrom === n.id ? null : n.id); }}>
                  {connectFrom === n.id ? "click target" : "→"}</button>
                {r && <div className="wf-out">{r.output.slice(0, 200)}</div>}
              </div>
            );
          })}
          {nodes.length === 0 && <div className="empty" style={{ height: "100%" }}><GitBranch size={28} />
            <div>Add nodes from the left, drag to arrange, click → then a target to connect.</div></div>}
        </div>
      </div>

      {selNode && (
        <div className="wf-inspect">
          <div className="page-head" style={{ marginBottom: 10 }}><h3 style={{ margin: 0 }}>{selNode.type} node</h3>
            <button className="x" onClick={() => removeNode(selNode.id)}><Trash2 size={14} /></button></div>
          <label className="lbl-sm">Name</label>
          <input value={selNode.name} onChange={(e) => rename(selNode.id, e.target.value)} />
          {selNode.type === "input" && (<>
            <label className="lbl-sm" style={{ marginTop: 10 }}>Value</label>
            <textarea className="md-edit" rows={4} value={selNode.config.value || ""} onChange={(e) => patch(selNode.id, { value: e.target.value })} />
          </>)}
          {selNode.type === "agent" && (<>
            <label className="lbl-sm" style={{ marginTop: 10 }}>Prompt <span className="dim">— use {"{{input}}"} for upstream output</span></label>
            <textarea className="md-edit" rows={5} value={selNode.config.prompt || ""} onChange={(e) => patch(selNode.id, { prompt: e.target.value })} />
            <label className="lbl-sm" style={{ marginTop: 10 }}>Model <span className="dim">(optional)</span></label>
            <input placeholder="provider:model" value={selNode.config.model || ""} onChange={(e) => patch(selNode.id, { model: e.target.value })} />
          </>)}
          {selNode.type === "tool" && (<>
            <label className="lbl-sm" style={{ marginTop: 10 }}>Tool name</label>
            <input placeholder="e.g. web_search" value={selNode.config.tool || ""} onChange={(e) => patch(selNode.id, { tool: e.target.value })} />
            <label className="lbl-sm" style={{ marginTop: 10 }}>Arguments (JSON)</label>
            <textarea className="md-edit" rows={4} placeholder='{"query": "{{input}}"}'
              value={selNode.config.argsText ?? (selNode.config.args ? JSON.stringify(selNode.config.args, null, 2) : "")}
              onChange={(e) => {
                let args: any = undefined; try { args = JSON.parse(e.target.value); } catch { /* keep raw */ }
                patch(selNode.id, { argsText: e.target.value, ...(args !== undefined ? { args } : {}) });
              }} />
          </>)}
          {results[selNode.id] && (<>
            <label className="lbl-sm" style={{ marginTop: 12 }}>Last output</label>
            <pre className="wf-result">{results[selNode.id].output}</pre>
          </>)}
        </div>
      )}
    </div>
  );
}
