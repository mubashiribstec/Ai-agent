import { Download, X } from "lucide-react";

export function CanvasPanel({ html, title, onClose }:
  { html: string; title: string; onClose: () => void }) {
  const download = () => {
    const blob = new Blob([html], { type: "text/html" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${(title || "canvas").replace(/[^a-z0-9]+/gi, "-")}.html`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };
  return (
    <aside className="canvas-panel">
      <div className="canvas-head">
        <b>{title || "Canvas"}</b>
        <span className="badge" title="rendered by the agent in an isolated sandbox">sandboxed</span>
        <div style={{ flex: 1 }} />
        <button className="icon-btn" aria-label="download" onClick={download}><Download size={15} /></button>
        <button className="icon-btn" aria-label="close" onClick={onClose}><X size={16} /></button>
      </div>
      {/* allow-scripts but NOT allow-same-origin: agent JS runs isolated from the app */}
      <iframe className="canvas-frame" sandbox="allow-scripts" srcDoc={html} title={title || "canvas"} />
    </aside>
  );
}
