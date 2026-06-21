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
