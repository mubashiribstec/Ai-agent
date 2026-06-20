// Thin client for the Nexus backend: REST helpers + a typed WebSocket wrapper.

export interface NexusEvent {
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

export class NexusSocket {
  private ws: WebSocket;

  constructor(onEvent: (ev: NexusEvent) => void, onOpen?: () => void) {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    this.ws = new WebSocket(`${proto}://${location.host}/ws`);
    this.ws.onmessage = (m) => onEvent(JSON.parse(m.data) as NexusEvent);
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
