import { useEffect, useState } from "react";
import {
  addFact, deleteFact, deleteSkill, getFacts, getFullConfig, getRoles,
  getSkills, getTools, patchConfig, putRole, putSecrets,
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
        <label>Vision model <span className="dim">(for analyze_image; blank = use active model)</span>
          <input defaultValue={cfg.vision_model}
                 placeholder="e.g. openai:gpt-4o or anthropic:claude-sonnet-4-6"
                 onBlur={(e) => save({ vision_model: e.target.value })} />
        </label>
        <p className="dim">Providers: {(cfg.providers ?? []).join(", ")}</p>
      </div>

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
