// Thin client for the Xplogent backend: REST helpers + a typed WebSocket wrapper.

export interface XplogentEvent {
  type: string;
  [key: string]: unknown;
}

export interface ApprovalRequest {
  id: string;
  tool: string;
  risk: string;
  reason: string;
  arguments: Record<string, unknown>;
}

export async function getConfig(): Promise<Record<string, unknown>> {
  const r = await fetch("/config");
  return r.json();
}

export async function getSkills(): Promise<{ skills: { name: string; description: string; uses: number }[] }> {
  const r = await fetch("/skills");
  return r.json();
}

export interface TaskOptions {
  model?: string;
  effort?: string;
  thinking?: boolean;
  temperature?: number;
}

export class XplogentSocket {
  private ws: WebSocket;

  constructor(onEvent: (ev: XplogentEvent) => void, sessionId?: number | null) {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const qs = sessionId ? `?session_id=${sessionId}` : "";
    this.ws = new WebSocket(`${proto}://${location.host}/ws${qs}`);
    this.ws.onmessage = (m) => onEvent(JSON.parse(m.data) as XplogentEvent);
  }

  sendTask(task: string, opts: TaskOptions = {}) {
    this.ws.send(JSON.stringify({ type: "task", task, ...opts }));
  }

  resolveApproval(id: string, allowed: boolean) {
    this.ws.send(JSON.stringify({ type: "approval", id, allowed }));
  }

  close() {
    this.ws.close();
  }
}

// ── Multi-agent orchestration + monitoring ────────────────────────────────────
export interface OrchestrateOptions {
  goal?: string;
  specs?: { name: string; role: string; task: string }[];
  max_concurrent?: number;
  mode?: string;
  auto_approve?: boolean;
}

export async function orchestrate(opts: OrchestrateOptions): Promise<{ run_id: string }> {
  const r = await fetch("/orchestrate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(opts),
  });
  return r.json();
}

export async function controlAgent(agentId: string, action: "pause" | "resume" | "cancel") {
  await fetch(`/agents/${agentId}/${action}`, { method: "POST" });
}

// ── Settings / config ─────────────────────────────────────────────────────────
export async function getFullConfig(): Promise<Record<string, any>> {
  return (await fetch("/config/full")).json();
}

export async function patchConfig(updates: Record<string, any>) {
  await fetch("/config", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ updates }),
  });
}

export async function putSecrets(keys: Record<string, string>) {
  await fetch("/secrets", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keys }),
  });
}

export async function getTools(): Promise<{ tools: any[]; groups: string[] }> {
  return (await fetch("/tools")).json();
}

export async function getRoles(): Promise<{ roles: Record<string, any> }> {
  return (await fetch("/roles")).json();
}

export async function putRole(name: string, role: Record<string, any>) {
  await fetch(`/roles/${name}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(role),
  });
}

export async function getFacts(): Promise<{ facts: { id: number; content: string }[] }> {
  return (await fetch("/memory/facts")).json();
}

export async function addFact(content: string) {
  await fetch("/memory/facts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}

export async function deleteFact(id: number) {
  await fetch(`/memory/facts/${id}`, { method: "DELETE" });
}

export async function deleteSkill(name: string) {
  await fetch(`/skills/${name}`, { method: "DELETE" });
}

// ── Update ────────────────────────────────────────────────────────────────────
export async function checkUpdate(): Promise<Record<string, any>> {
  return (await fetch("/update/check")).json();
}

export async function applyUpdate(): Promise<Record<string, any>> {
  return (await fetch("/update", { method: "POST" })).json();
}

export async function health(): Promise<boolean> {
  try {
    return (await fetch("/health")).ok;
  } catch {
    return false;
  }
}

// ── Models & sessions ─────────────────────────────────────────────────────────
export interface ModelPreset {
  label: string;
  model: string;
  temperature?: number;
  effort?: string;
  thinking?: boolean;
}

export async function getModels(): Promise<{ models: ModelPreset[]; active: string }> {
  return (await fetch("/models")).json();
}

export async function getSessions(): Promise<{ sessions: any[] }> {
  return (await fetch("/sessions")).json();
}

export async function newSession(): Promise<{ id: number }> {
  return (await fetch("/sessions", { method: "POST" })).json();
}

export async function getSessionMessages(id: number): Promise<{ messages: any[] }> {
  return (await fetch(`/sessions/${id}/messages`)).json();
}

export async function deleteSession(id: number) {
  await fetch(`/sessions/${id}`, { method: "DELETE" });
}

// ── Guide ─────────────────────────────────────────────────────────────────────
export async function getGuidePages(): Promise<{ pages: { slug: string; title: string }[] }> {
  return (await fetch("/guide")).json();
}

export async function getGuidePage(slug: string): Promise<{ content: string }> {
  return (await fetch(`/guide/${slug}`)).json();
}

// Live monitor stream for one orchestration run.
export class MonitorSocket {
  private ws: WebSocket;

  constructor(runId: string, onEvent: (ev: XplogentEvent) => void) {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    this.ws = new WebSocket(`${proto}://${location.host}/ws/monitor?run_id=${runId}`);
    this.ws.onmessage = (m) => onEvent(JSON.parse(m.data) as XplogentEvent);
  }

  close() {
    this.ws.close();
  }
}
