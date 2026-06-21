export interface TaskState {
  id: string;
  title: string;
  role: string;
  status: string;
  assignee?: string | null;
}

const COLUMNS: { key: string; label: string }[] = [
  { key: "pending", label: "Pending" },
  { key: "active", label: "Active" },
  { key: "done", label: "Done" },
  { key: "failed", label: "Failed" },
];

export function TaskBoard({ tasks }: { tasks: Record<string, TaskState> }) {
  const list = Object.values(tasks);
  if (list.length === 0) return null;
  return (
    <div className="kanban">
      {COLUMNS.map((col) => (
        <div key={col.key} className="kanban-col">
          <h4>{col.label}</h4>
          {list
            .filter((t) => t.status === col.key)
            .map((t) => (
              <div key={t.id} className={`kanban-card ${col.key}`}>
                <b>{t.title}</b>
                <span className="dim">{t.role}{t.assignee ? ` · ${t.assignee}` : ""}</span>
              </div>
            ))}
        </div>
      ))}
    </div>
  );
}
