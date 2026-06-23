import { useEffect, useState } from "react";
import { Menu } from "lucide-react";
import { NavRail, TABS, Tab } from "./components/NavRail";
import { CommandPalette } from "./components/CommandPalette";
import { Onboarding } from "./components/Onboarding";
import { useIsMobile } from "./hooks/useMediaQuery";
import { getSessions, getStatus } from "./api";
import { Chat } from "./views/Chat";
import { Runs } from "./views/Runs";
import { Council } from "./Council";
import { MissionControl } from "./MissionControl";
import { Schedules } from "./Schedules";
import { Settings } from "./Settings";
import { Guide } from "./Guide";

const initialTheme = (): "dark" | "light" => {
  const t = localStorage.getItem("xplogent_theme");
  if (t === "light" || t === "dark") return t;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
};

export function App() {
  const [tab, setTab] = useState<Tab>("chat");
  const [theme, setTheme] = useState<"dark" | "light">(initialTheme);
  const [online, setOnline] = useState(true);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [onboard, setOnboard] = useState(false);
  const isMobile = useIsMobile();

  // Health polling drives the rail status dot.
  useEffect(() => {
    const poll = () => getStatus().then(() => setOnline(true)).catch(() => setOnline(false));
    poll();
    const id = setInterval(poll, 15000);
    return () => clearInterval(id);
  }, []);

  // First-run onboarding: no API key set and no sessions yet.
  useEffect(() => {
    if (localStorage.getItem("xplogent_onboarded")) return;
    Promise.all([getStatus().catch(() => null), getSessions().catch(() => ({ sessions: [] }))])
      .then(([st, ss]) => {
        const anyKey = st ? Object.values(st.secrets).some(Boolean) : false;
        const usingLocal = st?.model?.startsWith("claude-cli") || st?.model?.startsWith("ollama");
        if (!anyKey && !usingLocal && (ss.sessions?.length ?? 0) === 0) setOnboard(true);
      });
  }, []);

  // Cmd/Ctrl-K command palette.
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPaletteOpen((o) => !o); }
      if (e.key === "Escape") setPaletteOpen(false);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("xplogent_theme", next);
    document.documentElement.setAttribute("data-theme", next);
  };

  const go = (t: Tab) => { setTab(t); setNavOpen(false); };

  return (
    <div className="shell">
      <NavRail tab={tab} onSelect={go} online={online} theme={theme} onTheme={toggleTheme}
               className={navOpen ? "open" : ""} />
      {isMobile && navOpen && <div className="scrim" onClick={() => setNavOpen(false)} />}

      <div className="main">
        {isMobile && (
          <div className="topbar">
            <button className="icon-btn" aria-label="menu" onClick={() => setNavOpen(true)}><Menu size={20} /></button>
            <div className="brand">X</div>
            <b>{TABS.find((t) => t.id === tab)?.label}</b>
          </div>
        )}
        {tab === "chat" && <Chat />}
        {tab === "council" && <Council />}
        {tab === "mission" && <MissionControl />}
        {tab === "runs" && <Runs />}
        {tab === "schedules" && <Schedules />}
        {tab === "settings" && <Settings />}
        {tab === "guide" && <Guide />}
      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)}
        onTab={go} onNewChat={() => { localStorage.removeItem("xplogent_session"); go("chat"); }} />
      {onboard && <Onboarding onDone={() => setOnboard(false)} />}
    </div>
  );
}
