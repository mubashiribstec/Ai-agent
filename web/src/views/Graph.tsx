import { useEffect, useMemo, useRef, useState } from "react";
import { Network, RefreshCw } from "lucide-react";
import { GraphEdge, GraphNode, getGraph } from "../api";

interface P { x: number; y: number; }

// A tiny force-directed layout (repulsion + spring + centering) computed in a
// fixed number of iterations — no external graph library.
function layout(nodes: GraphNode[], edges: GraphEdge[], W: number, H: number): Record<string, P> {
  const pos: Record<string, P> = {};
  const n = nodes.length || 1;
  nodes.forEach((nd, i) => {
    const a = (i / n) * Math.PI * 2;
    pos[nd.name] = { x: W / 2 + Math.cos(a) * W * 0.3, y: H / 2 + Math.sin(a) * H * 0.3 };
  });
  const adj = edges.filter((e) => pos[e.subject] && pos[e.object]);
  for (let it = 0; it < 220; it++) {
    const disp: Record<string, P> = {};
    nodes.forEach((nd) => (disp[nd.name] = { x: 0, y: 0 }));
    // Repulsion between all pairs.
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = pos[nodes[i].name], b = pos[nodes[j].name];
        let dx = a.x - b.x, dy = a.y - b.y;
        let d2 = dx * dx + dy * dy || 0.01;
        const f = 9000 / d2;
        const d = Math.sqrt(d2);
        dx /= d; dy /= d;
        disp[nodes[i].name].x += dx * f; disp[nodes[i].name].y += dy * f;
        disp[nodes[j].name].x -= dx * f; disp[nodes[j].name].y -= dy * f;
      }
    }
    // Spring along edges.
    for (const e of adj) {
      const a = pos[e.subject], b = pos[e.object];
      const dx = a.x - b.x, dy = a.y - b.y;
      const d = Math.sqrt(dx * dx + dy * dy) || 0.01;
      const f = (d - 90) * 0.05;
      const ux = dx / d, uy = dy / d;
      disp[e.subject].x -= ux * f; disp[e.subject].y -= uy * f;
      disp[e.object].x += ux * f; disp[e.object].y += uy * f;
    }
    nodes.forEach((nd) => {
      const p = pos[nd.name];
      p.x += Math.max(-12, Math.min(12, disp[nd.name].x));
      p.y += Math.max(-12, Math.min(12, disp[nd.name].y));
      p.x += (W / 2 - p.x) * 0.01; p.y += (H / 2 - p.y) * 0.01; // gentle centering
      p.x = Math.max(20, Math.min(W - 20, p.x));
      p.y = Math.max(20, Math.min(H - 20, p.y));
    });
  }
  return pos;
}

export function Graph() {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [sel, setSel] = useState<string | null>(null);
  const W = 880, H = 560;
  const wrap = useRef<HTMLDivElement>(null);

  const reload = () => getGraph().then((g) => { setNodes(g.nodes); setEdges(g.edges); }).catch(() => {});
  useEffect(() => { reload(); }, []);

  const pos = useMemo(() => layout(nodes, edges, W, H), [nodes, edges]);
  const related = useMemo(() => {
    if (!sel) return new Set<string>();
    const s = new Set<string>([sel]);
    edges.forEach((e) => { if (e.subject === sel) s.add(e.object); if (e.object === sel) s.add(e.subject); });
    return s;
  }, [sel, edges]);

  const r = (nd: GraphNode) => 6 + Math.min(10, nd.mentions);

  return (
    <div className="pane">
      <div className="pane-wide">
        <div className="page-head">
          <h1><Network size={22} /> Knowledge graph</h1>
          <button className="icon-btn" onClick={reload} aria-label="refresh"><RefreshCw size={16} /></button>
        </div>
        <p className="dim">Entities and relations the agent has learned. Click a node to highlight its connections.</p>

        {nodes.length === 0 ? (
          <div className="empty"><Network size={28} /><div>The graph is empty. As the agent reflects on tasks,
            it extracts entities and relationships here.</div></div>
        ) : (
          <div className="card graph-card" ref={wrap}>
            <svg viewBox={`0 0 ${W} ${H}`} className="kg-svg" onClick={() => setSel(null)}>
              {edges.map((e, i) => {
                const a = pos[e.subject], b = pos[e.object];
                if (!a || !b) return null;
                const on = !sel || related.has(e.subject) && related.has(e.object);
                return (
                  <g key={i} className={on ? "" : "dim-edge"}>
                    <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="kg-edge" />
                    {(!sel || on) && (
                      <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2} className="kg-rel">{e.relation}</text>
                    )}
                  </g>
                );
              })}
              {nodes.map((nd) => {
                const p = pos[nd.name]; if (!p) return null;
                const on = !sel || related.has(nd.name);
                return (
                  <g key={nd.name} className={`kg-node ${on ? "" : "dim-node"} ${nd.name === sel ? "sel" : ""}`}
                     onClick={(e) => { e.stopPropagation(); setSel(nd.name === sel ? null : nd.name); }}>
                    <circle cx={p.x} cy={p.y} r={r(nd)} />
                    <text x={p.x} y={p.y - r(nd) - 4} className="kg-label">{nd.name}</text>
                  </g>
                );
              })}
            </svg>
            <div className="dim" style={{ fontSize: 12 }}>{nodes.length} entities · {edges.length} relations</div>
          </div>
        )}
      </div>
    </div>
  );
}
