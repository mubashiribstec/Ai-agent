import {
  Activity, BookOpen, Calendar, LayoutGrid, type LucideIcon,
  MessageSquare, Moon, Settings as Cog, Sun, Users,
} from "lucide-react";

export type Tab = "chat" | "council" | "mission" | "runs" | "schedules" | "settings" | "guide";

export const TABS: { id: Tab; label: string; icon: LucideIcon }[] = [
  { id: "chat", label: "Chat", icon: MessageSquare },
  { id: "council", label: "Council", icon: Users },
  { id: "mission", label: "Mission Control", icon: LayoutGrid },
  { id: "runs", label: "Runs", icon: Activity },
  { id: "schedules", label: "Schedules", icon: Calendar },
  { id: "settings", label: "Settings", icon: Cog },
  { id: "guide", label: "Guide", icon: BookOpen },
];

export function NavRail({ tab, onSelect, online, theme, onTheme, className }: {
  tab: Tab;
  onSelect: (t: Tab) => void;
  online: boolean;
  theme: "dark" | "light";
  onTheme: () => void;
  className?: string;
}) {
  return (
    <nav className={`rail ${className ?? ""}`}>
      <div className="brand" title="Xplogent">X</div>
      {TABS.map(({ id, label, icon: Icon }) => (
        <button key={id} className={`rail-btn ${tab === id ? "active" : ""}`}
                aria-label={label} onClick={() => onSelect(id)}>
          <Icon size={20} />
          <span className="lbl">{label}</span>
        </button>
      ))}
      <div className="spacer" />
      <button className="rail-btn" aria-label="Toggle theme" onClick={onTheme}>
        {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
        <span className="lbl">Theme</span>
      </button>
      <button className="rail-btn" aria-label="Connection status" title={online ? "Connected" : "Offline"}>
        <span className={`health-dot ${online ? "ok" : "bad"}`} />
      </button>
    </nav>
  );
}
