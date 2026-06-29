import { useEffect, useState } from "react";
import {
  addFact, deleteFact, deleteSkill, enableLocalVision, exportKnowledge, getFacts, getFullConfig,
  getRoles, getSkills, getStatus, getTools, importKnowledge, patchConfig, putRole,
  putSecrets, restoreBackup, StatusInfo, testVision,
} from "./api";
import { UpdatePanel } from "./UpdatePanel";

const RISK_TIERS = ["low", "medium", "high", "critical"];
const ACTIONS = ["auto", "confirm", "deny"];
const SECRET_KEYS = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"];

export function Settings() {
  const [cfg, setCfg] = useState<Record<string, any> | null>(null);
  const [tools, setTools] = useState<any[]>([]);
  const [roles, setRoles] = useState<Record<string, any>>({});
  const [facts, setFacts] = useState<{ id: number; content: string }[]>([]);
  const [skills, setSkills] = useState<{ name: string; uses: number; description: string }[]>([]);
  const [saved, setSaved] = useState("");

  const reload = async () => {
    setCfg(await getFullConfig());
    setTools((await getTools()).tools);
    setRoles((await getRoles()).roles);
    setFacts((await getFacts()).facts);
    setSkills((await getSkills()).skills);
  };
  useEffect(() => { reload(); }, []);

  const flash = (m: string) => { setSaved(m); setTimeout(() => setSaved(""), 1500); };
  const save = async (updates: Record<string, any>) => { await patchConfig(updates); flash("saved"); };

  if (!cfg) return <div className="settings"><p className="dim">loading…</p></div>;

  const enabledGroups: string[] = cfg.tools_enabled ?? [];
  const policy: Record<string, string> = cfg.safety?.policy ?? {};

  return (
    <div className="settings">
      <div className="warn-banner">⚠ Settings are stored locally in ~/.xplogent. Keep the server bound to 127.0.0.1.</div>
      {saved && <div className="toast">{saved}</div>}

      <HealthCard />
      <McpCard mcp={cfg.mcp ?? {}} onSave={save} />

      <div className="card">
        <h3>Model</h3>
        <label>Active model
          <input defaultValue={cfg.model} onBlur={(e) => save({ model: e.target.value })} />
        </label>
        <label>Reflection model
          <input defaultValue={cfg.reflection_model}
                 onBlur={(e) => save({ reflection_model: e.target.value })} />
        </label>
        <label>Embedding model
          <input defaultValue={cfg.embedding_model}
                 onBlur={(e) => save({ embedding_model: e.target.value })} />
        </label>
        <label>Vision model <span className="dim">(for image chats &amp; analyze_image; blank = use active model)</span>
          <input defaultValue={cfg.vision_model}
                 placeholder="e.g. ollama:llava, openai:gpt-4o, anthropic:claude-sonnet-4-6"
                 onBlur={(e) => save({ vision_model: e.target.value })} />
        </label>
        <VisionControls reload={reload} flash={flash} />
        <p className="dim">Providers: {(cfg.providers ?? []).join(", ")}</p>
      </div>

      <Appearance />
      <BackupCard flash={flash} reload={reload} />
      <ExecutionBackend execution={cfg.execution ?? {}} onSave={save} />

      <ModelsManager models={cfg.models ?? []} onSave={async (m) => { await save({ models: m }); reload(); }} />

      <div className="card">
        <h3>API keys</h3>
        {SECRET_KEYS.map((k) => (
          <label key={k}>{k} {cfg.secrets?.[k] ? "✓ set" : "✗ unset"}
            <input type="password" placeholder={cfg.secrets?.[k] ? "•••••• (set)" : "paste key"}
                   onBlur={async (e) => {
                     if (e.target.value) { await putSecrets({ [k]: e.target.value }); e.target.value = ""; reload(); }
                   }} />
          </label>
        ))}
      </div>

      <div className="card">
        <h3>Safety policy</h3>
        {RISK_TIERS.map((tier) => (
          <label key={tier}>{tier}
            <select defaultValue={policy[tier] ?? "confirm"}
                    onChange={(e) => save({ safety: { policy: { [tier]: e.target.value } } })}>
              {ACTIONS.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </label>
        ))}
      </div>

      <div className="card">
        <h3>Orchestrator</h3>
        <label>Max concurrent agents: <b>{cfg.orchestrator?.max_concurrent_agents ?? 3}</b>
          <input type="range" min={1} max={8}
                 defaultValue={cfg.orchestrator?.max_concurrent_agents ?? 3}
                 onMouseUp={(e: any) => save({ orchestrator: { max_concurrent_agents: Number(e.target.value) } })} />
        </label>
      </div>

      <div className="card">
        <h3>Tools</h3>
        {Array.from(new Set(tools.map((t) => t.group))).map((group) => (
          <label key={group} className="check">
            <input type="checkbox" defaultChecked={enabledGroups.includes(group)}
                   onChange={(e) => {
                     const next = e.target.checked
                       ? [...enabledGroups, group]
                       : enabledGroups.filter((g) => g !== group);
                     save({ tools: { enabled: next } });
                   }} />
            {group}
          </label>
        ))}
      </div>

      <RolesEditor roles={roles} allTools={tools.map((t) => t.name)}
                   onSaved={() => { flash("role saved"); reload(); }} />

      <div className="card">
        <h3>Memory ({facts.length} facts)</h3>
        <div className="row">
          <input id="newfact" placeholder="remember a fact…" />
          <button onClick={async () => {
            const el = document.getElementById("newfact") as HTMLInputElement;
            if (el.value) { await addFact(el.value); el.value = ""; reload(); }
          }}>Add</button>
        </div>
        <ul className="list">
          {facts.map((f) => (
            <li key={f.id}>{f.content}
              <button className="x" onClick={async () => { await deleteFact(f.id); reload(); }}>✕</button>
            </li>
          ))}
        </ul>
      </div>

      <div className="card">
        <h3>Skills ({skills.length})</h3>
        <ul className="list">
          {skills.map((s) => (
            <li key={s.name}><b>{s.name}</b> <span className="dim">×{s.uses}</span>
              <button className="x" onClick={async () => { await deleteSkill(s.name); reload(); }}>✕</button>
            </li>
          ))}
        </ul>
      </div>

      <UpdatePanel />
    </div>
  );
}

function HealthCard() {
  const [st, setSt] = useState<StatusInfo | null>(null);
  const reload = () => getStatus().then(setSt).catch(() => setSt(null));
  useEffect(() => { reload(); const id = setInterval(reload, 10000); return () => clearInterval(id); }, []);
  return (
    <div className="card">
      <h3>Status &amp; health</h3>
      {!st ? <p className="warn">Backend unreachable.</p> : (
        <>
          <div className="row wrap" style={{ gap: 8 }}>
            <span className="badge ok">backend online</span>
            <span className={`badge ${st.ollama.reachable ? "ok" : "bad"}`}>
              Ollama {st.ollama.reachable ? "reachable" : "down"}</span>
            <span className="badge">active model: {st.model}</span>
          </div>
          <h4 style={{ margin: "14px 0 6px", fontSize: 13 }} className="dim">Providers</h4>
          <div className="row wrap" style={{ gap: 8 }}>
            {st.providers.map((p) => {
              const keyMap: Record<string, string> = {
                openai: "OPENAI_API_KEY", anthropic: "ANTHROPIC_API_KEY",
                openrouter: "OPENROUTER_API_KEY", gemini: "GOOGLE_API_KEY",
              };
              const env = keyMap[p];
              const ok = !env || st.secrets[env];
              return <span key={p} className={`badge ${ok ? "ok" : "warn"}`}>{p}{env && !ok ? " · no key" : ""}</span>;
            })}
          </div>
        </>
      )}
    </div>
  );
}

function McpCard({ mcp, onSave }: { mcp: any; onSave: (u: Record<string, any>) => void }) {
  const server = mcp.server ?? {};
  const set = (k: string, v: any) => onSave({ mcp: { server: { [k]: v } } });
  const clientSnippet = JSON.stringify({
    mcpServers: { xplogent: { command: "xplogent-mcp", args: [] } },
  }, null, 2);
  return (
    <div className="card">
      <h3>MCP server</h3>
      <p className="dim">Expose Xplogent's tools/agents to MCP clients (Claude Desktop, Cursor, …).
        Launch it with <code>xplogent mcp</code>.</p>
      <div className="grid2">
        <label className="field-l">Transport
          <select defaultValue={server.transport ?? "stdio"} onChange={(e) => set("transport", e.target.value)}>
            {["stdio", "streamable-http", "sse"].map((t) => <option key={t}>{t}</option>)}
          </select>
        </label>
        <label className="field-l">Role profile
          <input defaultValue={server.agent_role ?? "operator"} onBlur={(e) => set("agent_role", e.target.value)} />
        </label>
      </div>
      <label className="check"><input type="checkbox" defaultChecked={server.auto_approve ?? false}
        onChange={(e) => set("auto_approve", e.target.checked)} /> auto-approve confirm-tier actions</label>
      <label className="check"><input type="checkbox" defaultChecked={server.expose_raw_tools ?? true}
        onChange={(e) => set("expose_raw_tools", e.target.checked)} /> expose raw PC tools</label>
      <h4 style={{ margin: "14px 0 6px", fontSize: 13 }} className="dim">Claude Desktop config</h4>
      <pre className="snippet">{clientSnippet}</pre>
    </div>
  );
}

function Appearance() {
  const [theme, setTheme] = useState(localStorage.getItem("xplogent_theme") || "auto");
  const [accent, setAccent] = useState(localStorage.getItem("xplogent_accent") || "#58a6ff");
  const applyTheme = (t: string) => {
    setTheme(t);
    localStorage.setItem("xplogent_theme", t);
    if (t === "auto") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", t);
  };
  const applyAccent = (c: string) => {
    setAccent(c);
    localStorage.setItem("xplogent_accent", c);
    document.documentElement.style.setProperty("--accent", c);
  };
  return (
    <div className="card">
      <h3>Appearance</h3>
      <label>Theme
        <select value={theme} onChange={(e) => applyTheme(e.target.value)}>
          {["auto", "dark", "light"].map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </label>
      <label className="check">Accent color
        <input type="color" value={accent} onChange={(e) => applyAccent(e.target.value)} />
      </label>
    </div>
  );
}

function BackupCard({ flash, reload }: { flash: (m: string) => void; reload: () => void }) {
  const [msg, setMsg] = useState("");
  const doExport = async () => {
    const data = await exportKnowledge();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "xplogent-knowledge.json";
    a.click();
  };
  const doImport = async (file: File) => {
    const data = JSON.parse(await file.text());
    const res = await importKnowledge(data);
    setMsg(`+${res.facts_added} facts, +${res.skills_added} skills`
           + (res.warnings?.length ? ` · ⚠ ${res.warnings[0]}` : ""));
    reload();
  };
  const doRestore = async (file: File) => {
    const res = await restoreBackup(await file.arrayBuffer());
    flash(res.ok ? "restored — restart to apply" : "restore failed");
  };
  return (
    <div className="card">
      <h3>Backup &amp; knowledge</h3>
      <p className="dim">Full backup downloads the DB + skills + config as a .tar.gz.</p>
      <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
        <a className="primary" href="/backup" style={{ padding: "8px 14px", borderRadius: 6,
           textDecoration: "none", color: "#0d1117", background: "var(--accent)" }}>
          Download backup
        </a>
        <button onClick={doExport}>Export skills + memory</button>
        <label className="filebtn">Import knowledge
          <input type="file" accept="application/json" style={{ display: "none" }}
                 onChange={(e) => e.target.files?.[0] && doImport(e.target.files[0])} />
        </label>
        <label className="filebtn">Restore backup
          <input type="file" accept=".gz,.tar.gz,application/gzip" style={{ display: "none" }}
                 onChange={(e) => e.target.files?.[0] && doRestore(e.target.files[0])} />
        </label>
      </div>
      {msg && <p className="ok">{msg}</p>}
    </div>
  );
}

function ExecutionBackend({ execution, onSave }:
  { execution: Record<string, any>; onSave: (u: Record<string, any>) => void }) {
  const backend = execution.backend ?? "local";
  const docker = execution.docker ?? {};
  const ssh = execution.ssh ?? {};
  return (
    <div className="card">
      <h3>Execution backend</h3>
      <p className="dim">Where <code>shell</code> &amp; <code>python_exec</code> run. The deny-list still applies on every backend.</p>
      <label>Backend
        <select defaultValue={backend} onChange={(e) => onSave({ execution: { backend: e.target.value } })}>
          {["local", "docker", "ssh"].map((b) => <option key={b} value={b}>{b}</option>)}
        </select>
      </label>
      {backend === "docker" && (
        <>
          <label>Image
            <input defaultValue={docker.image ?? "python:3.11-slim"}
                   onBlur={(e) => onSave({ execution: { docker: { image: e.target.value } } })} />
          </label>
          <label>Container <span className="dim">(blank = ephemeral docker run)</span>
            <input defaultValue={docker.container ?? ""}
                   onBlur={(e) => onSave({ execution: { docker: { container: e.target.value } } })} />
          </label>
        </>
      )}
      {backend === "ssh" && (
        <>
          <label>Host
            <input defaultValue={ssh.host ?? ""}
                   onBlur={(e) => onSave({ execution: { ssh: { host: e.target.value } } })} />
          </label>
          <label>User
            <input defaultValue={ssh.user ?? ""}
                   onBlur={(e) => onSave({ execution: { ssh: { user: e.target.value } } })} />
          </label>
          <label>Key path
            <input defaultValue={ssh.key_path ?? ""}
                   onBlur={(e) => onSave({ execution: { ssh: { key_path: e.target.value } } })} />
          </label>
        </>
      )}
    </div>
  );
}

function VisionControls({ reload, flash }: { reload: () => void; flash: (m: string) => void }) {
  const [busy, setBusy] = useState("");
  const [result, setResult] = useState("");

  const enable = async () => {
    setBusy("enable"); setResult("Pulling llava (first time can take a few minutes)…");
    const res = await enableLocalVision("llava");
    setBusy("");
    if (res.ok) { setResult(`Local vision enabled: ${res.vision_model}`); flash("local vision enabled"); reload(); }
    else setResult(res.error || "failed to enable local vision");
  };
  const test = async () => {
    setBusy("test"); setResult("Testing the vision model…");
    const res = await testVision();
    setBusy("");
    setResult(res.ok ? `✓ ${res.model} replied: ${res.reply.slice(0, 200)}` : `✗ ${res.reply}`);
  };

  return (
    <div style={{ marginTop: 6 }}>
      <div className="row" style={{ gap: 8 }}>
        <button onClick={enable} disabled={!!busy}>{busy === "enable" ? "Enabling…" : "Enable local vision (llava)"}</button>
        <button onClick={test} disabled={!!busy}>{busy === "test" ? "Testing…" : "Test vision"}</button>
      </div>
      {result && <p className="dim" style={{ fontSize: 12, marginTop: 6, whiteSpace: "pre-wrap" }}>{result}</p>}
    </div>
  );
}

function ModelsManager({ models, onSave }:
  { models: any[]; onSave: (m: any[]) => void }) {
  const blank = { label: "", model: "", temperature: 0.7, effort: "off", thinking: false };
  const [draft, setDraft] = useState(blank);
  return (
    <div className="card">
      <h3>Models ({models.length})</h3>
      <ul className="list">
        {models.map((m, i) => (
          <li key={i}><b>{m.label}</b> <span className="dim">{m.model} · {m.effort}{m.thinking ? " · think" : ""}</span>
            <button className="x" onClick={() => onSave(models.filter((_, j) => j !== i))}>✕</button>
          </li>
        ))}
      </ul>
      <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
        <input placeholder="label" value={draft.label}
               onChange={(e) => setDraft({ ...draft, label: e.target.value })} />
        <input placeholder="provider:model" value={draft.model}
               onChange={(e) => setDraft({ ...draft, model: e.target.value })} />
        <select value={draft.effort} onChange={(e) => setDraft({ ...draft, effort: e.target.value })}>
          {["off", "low", "medium", "high"].map((x) => <option key={x}>{x}</option>)}
        </select>
        <label className="check"><input type="checkbox" checked={draft.thinking}
               onChange={(e) => setDraft({ ...draft, thinking: e.target.checked })} />think</label>
        <button onClick={() => { if (draft.label && draft.model) { onSave([...models, draft]); setDraft(blank); } }}>Add</button>
      </div>
    </div>
  );
}

function RolesEditor({ roles, allTools, onSaved }:
  { roles: Record<string, any>; allTools: string[]; onSaved: () => void }) {
  const names = Object.keys(roles);
  const [sel, setSel] = useState(names[0] ?? "");
  const role = roles[sel];
  if (!role) return null;
  const allowed: string[] = role.allowed_tools === "*" ? allTools : (role.allowed_tools ?? []);

  return (
    <div className="card">
      <h3>Roles &amp; permissions</h3>
      <select value={sel} onChange={(e) => setSel(e.target.value)}>
        {names.map((n) => <option key={n}>{n}</option>)}
      </select>
      <p className="dim">network: {String(role.network)} · max steps: {role.max_steps}</p>
      <div className="toolgrid">
        {allTools.map((t) => {
          const on = role.allowed_tools === "*" || allowed.includes(t);
          return (
            <label key={t} className="check">
              <input type="checkbox" checked={on}
                     onChange={(e) => {
                       const base = role.allowed_tools === "*" ? allTools : [...allowed];
                       const next = e.target.checked ? [...new Set([...base, t])] : base.filter((x) => x !== t);
                       putRole(sel, { ...role, allowed_tools: next }).then(onSaved);
                     }} />
              {t}
            </label>
          );
        })}
      </div>
    </div>
  );
}
