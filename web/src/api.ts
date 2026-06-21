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

export class XplogentSocket {
  private ws: WebSocket;

  constructor(onEvent: (ev: XplogentEvent) => void, onOpen?: () => void) {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    this.ws = new WebSocket(`${proto}://${location.host}/ws`);
    this.ws.onmessage = (m) => onEvent(JSON.parse(m.data) as XplogentEvent);
    if (onOpen) this.ws.onopen = onOpen;
  }

  sendTask(task: string) {
    this.ws.send(JSON.stringify({ type: "task", task }));
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
