// Build shareable / downloadable representations of a chat transcript.

export interface ExportMsg { role: "user" | "assistant" | string; text: string; }

export function toMarkdown(title: string, msgs: ExportMsg[]): string {
  const head = `# ${title}\n\n_Exported from Xplogent · ${new Date().toLocaleString()}_\n\n`;
  const body = msgs.map((m) => {
    const who = m.role === "user" ? "🧑 You" : "🤖 Xplogent";
    return `**${who}:**\n\n${m.text}\n`;
  }).join("\n---\n\n");
  return head + body;
}

const escapeHtml = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

export function toHTML(title: string, msgs: ExportMsg[]): string {
  const rows = msgs.map((m) => {
    const mine = m.role === "user";
    return `<div class="m ${mine ? "u" : "a"}"><div class="who">${mine ? "You" : "Xplogent"}</div>`
      + `<div class="b">${escapeHtml(m.text)}</div></div>`;
  }).join("\n");
  return `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${escapeHtml(title)}</title>
<style>
  body{font-family:ui-sans-serif,system-ui,sans-serif;background:#0b0e14;color:#e6edf3;
    margin:0;padding:32px;line-height:1.55}
  .wrap{max-width:760px;margin:0 auto}
  h1{font-size:22px} .meta{color:#8b97a7;font-size:13px;margin-bottom:24px}
  .m{margin:14px 0;display:flex;gap:12px}
  .who{font-size:12px;color:#8b97a7;width:74px;flex-shrink:0;padding-top:10px}
  .b{background:#141a23;border:1px solid #232c39;border-radius:12px;padding:11px 15px;
    white-space:pre-wrap;word-break:break-word;flex:1}
  .m.u .b{background:#4c8dff22;border-color:#4c8dff44}
</style></head><body><div class="wrap">
<h1>${escapeHtml(title)}</h1>
<div class="meta">Shared from Xplogent · ${new Date().toLocaleString()}</div>
${rows}
</div></body></html>`;
}

export function download(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

const slug = (s: string) =>
  (s || "chat").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40) || "chat";

export function downloadMarkdown(title: string, msgs: ExportMsg[]) {
  download(`${slug(title)}.md`, toMarkdown(title, msgs), "text/markdown");
}
export function downloadJSON(title: string, msgs: ExportMsg[]) {
  download(`${slug(title)}.json`, JSON.stringify({ title, messages: msgs }, null, 2), "application/json");
}
export function shareHTML(title: string, msgs: ExportMsg[]) {
  download(`${slug(title)}.html`, toHTML(title, msgs), "text/html");
}
