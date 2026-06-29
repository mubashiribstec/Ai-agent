import { useEffect, useState } from "react";
import { Globe, KeyboardIcon, MonitorSmartphone, RefreshCw } from "lucide-react";
import { ExtensionStatus, getExtensionStatus } from "../api";

const fmt = (t: number) => (t ? new Date(t * 1000).toLocaleTimeString() : "—");

export function Browser() {
  const [st, setSt] = useState<ExtensionStatus | null>(null);

  const reload = () => getExtensionStatus().then(setSt).catch(() => setSt(null));
  useEffect(() => {
    reload();
    const id = setInterval(reload, 2000); // live view of tabs + input activity
    return () => clearInterval(id);
  }, []);

  const connected = st?.connected;

  return (
    <div className="pane">
      <div className="pane-wide">
        <div className="page-head">
          <h1><MonitorSmartphone size={22} /> Browser</h1>
          <div className="row" style={{ gap: 8 }}>
            <span className={`badge ${connected ? "ok" : "bad"}`}>{connected ? "extension connected" : "not connected"}</span>
            <button className="icon-btn" onClick={reload} aria-label="refresh"><RefreshCw size={16} /></button>
          </div>
        </div>
        <p className="dim">Control and monitor your <b>real</b> Chrome via the Xplogent extension. The agent's
          <code> web_browser</code> tool drives the tabs below.</p>

        {!connected && (
          <div className="card">
            <h3>Connect the extension</h3>
            <ol className="dim" style={{ lineHeight: 1.7, paddingLeft: 18 }}>
              <li>Open <code>chrome://extensions</code> → enable <b>Developer mode</b>.</li>
              <li><b>Load unpacked</b> → select the <code>extension/</code> folder in the repo.</li>
              <li>Click the Xplogent toolbar icon, set the backend URL (and token if enabled), Save.</li>
            </ol>
          </div>
        )}

        <div className="card">
          <h3><Globe size={16} /> Open tabs ({st?.tabs.length ?? 0})</h3>
          <ul className="list">
            {(st?.tabs ?? []).map((t) => (
              <li key={t.id}>
                <span style={{ flex: 1 }}>
                  {t.active && <span className="badge ok" style={{ marginRight: 6 }}>active</span>}
                  <b>{t.title || "(untitled)"}</b><br />
                  <span className="dim mono" style={{ fontSize: 12 }}>{t.url}</span>
                </span>
              </li>
            ))}
            {(st?.tabs?.length ?? 0) === 0 && <p className="dim">no tabs reported</p>}
          </ul>
        </div>

        <div className="card">
          <h3><KeyboardIcon size={16} /> Input-field activity</h3>
          <p className="dim">Where the user is typing (metadata only — values are never captured; passwords flagged redacted).</p>
          <table className="data-table">
            <thead><tr><th>When</th><th>Field</th><th>Type</th><th>Page</th></tr></thead>
            <tbody>
              {[...(st?.inputs ?? [])].reverse().map((a, i) => (
                <tr key={i}>
                  <td className="dim">{fmt(a.ts ?? 0)}</td>
                  <td className="mono">{a.field}{a.redacted && <span className="badge warn" style={{ marginLeft: 6 }}>redacted</span>}</td>
                  <td>{a.type}</td>
                  <td className="dim ellipsis" style={{ maxWidth: 220 }}>{a.page}</td>
                </tr>
              ))}
              {(st?.inputs?.length ?? 0) === 0 && <tr><td colSpan={4} className="dim">no input activity yet</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
