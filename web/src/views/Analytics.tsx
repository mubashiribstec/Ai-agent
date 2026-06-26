import { useEffect, useState } from "react";
import { BarChart3, Coins, Cpu, RefreshCw, Zap } from "lucide-react";
import { Analytics as AnalyticsData, UsageBucket, getAnalytics } from "../api";

const fmt = (n: number) => n.toLocaleString();
const usd = (n: number) => `$${n.toFixed(n < 1 ? 4 : 2)}`;

// A dependency-free bar chart: tokens per day, input + output stacked.
function TokenChart({ days }: { days: UsageBucket[] }) {
  if (days.length === 0) return <p className="dim">no usage in this window</p>;
  const W = 720, H = 200, pad = 28;
  const max = Math.max(1, ...days.map((d) => (d.input_tokens + d.output_tokens)));
  const bw = (W - pad * 2) / days.length;
  const y = (v: number) => H - pad - (v / max) * (H - pad * 2);
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label="tokens per day">
      <line x1={pad} y1={H - pad} x2={W - pad} y2={H - pad} className="axis" />
      {days.map((d, i) => {
        const x = pad + i * bw + bw * 0.15;
        const w = bw * 0.7;
        const inH = (d.input_tokens / max) * (H - pad * 2);
        const outH = (d.output_tokens / max) * (H - pad * 2);
        return (
          <g key={i}>
            <rect x={x} y={H - pad - inH} width={w} height={inH} className="bar-in">
              <title>{d.day}: {fmt(d.input_tokens)} in</title>
            </rect>
            <rect x={x} y={H - pad - inH - outH} width={w} height={outH} className="bar-out">
              <title>{d.day}: {fmt(d.output_tokens)} out</title>
            </rect>
          </g>
        );
      })}
      <text x={pad} y={y(max) - 4} className="tick">{fmt(max)}</text>
    </svg>
  );
}

function Stat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="card stat" style={{ padding: 16 }}>
      <div className="row" style={{ gap: 8, color: "var(--accent)" }}>{icon}<span className="dim">{label}</span></div>
      <div style={{ fontSize: 26, fontWeight: 700, marginTop: 6 }}>{value}</div>
    </div>
  );
}

export function Analytics() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [days, setDays] = useState(30);

  const reload = (d = days) => getAnalytics(d).then(setData).catch(() => setData(null));
  useEffect(() => { reload(days); /* eslint-disable-next-line */ }, [days]);

  const t = data?.totals;
  return (
    <div className="pane">
      <div className="pane-wide">
        <div className="page-head">
          <h1><BarChart3 size={22} /> Analytics</h1>
          <div className="row" style={{ gap: 8 }}>
            <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
              <option value={7}>last 7 days</option>
              <option value={30}>last 30 days</option>
              <option value={90}>last 90 days</option>
            </select>
            <button className="icon-btn" onClick={() => reload()} aria-label="refresh"><RefreshCw size={16} /></button>
          </div>
        </div>

        <div className="grid-stats">
          <Stat icon={<Zap size={16} />} label="turns" value={fmt(t?.turns ?? 0)} />
          <Stat icon={<Cpu size={16} />} label="input tokens" value={fmt(t?.input_tokens ?? 0)} />
          <Stat icon={<Cpu size={16} />} label="output tokens" value={fmt(t?.output_tokens ?? 0)} />
          <Stat icon={<Coins size={16} />} label="est. cost" value={usd(t?.cost ?? 0)} />
        </div>

        <div className="card">
          <h3>Tokens per day <span className="dim" style={{ fontWeight: 400 }}>· <span className="swatch in" /> input <span className="swatch out" /> output</span></h3>
          <TokenChart days={data?.by_day ?? []} />
        </div>

        <div className="card">
          <h3>By model</h3>
          <table className="data-table">
            <thead><tr><th>Model</th><th>Turns</th><th>Input</th><th>Output</th><th>Cost</th></tr></thead>
            <tbody>
              {(data?.by_model ?? []).map((m) => (
                <tr key={m.model}>
                  <td className="mono">{m.model}</td>
                  <td>{fmt(m.turns)}</td>
                  <td>{fmt(m.input_tokens)}</td>
                  <td>{fmt(m.output_tokens)}</td>
                  <td>{usd(m.cost)}</td>
                </tr>
              ))}
              {(data?.by_model?.length ?? 0) === 0 && <tr><td colSpan={5} className="dim">no usage recorded yet — chat with the agent to populate this</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
