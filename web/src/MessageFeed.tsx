export interface AgentMsg {
  sender: string;
  recipient?: string | null;
  content: string;
}

export function MessageFeed({ messages }: { messages: AgentMsg[] }) {
  return (
    <div className="msg-feed">
      <h4>Agent chatter</h4>
      {messages.length === 0 && <p className="dim">no messages yet</p>}
      {messages.map((m, i) => (
        <div key={i} className="msg">
          <b>{m.sender}</b>
          <span className="arrow"> → {m.recipient ?? "all"}</span>: {m.content}
        </div>
      ))}
    </div>
  );
}
