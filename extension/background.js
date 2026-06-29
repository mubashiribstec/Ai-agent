// Xplogent extension service worker: bridges the user's real Chrome to the
// Xplogent backend. Connects over WebSocket, streams a live tab snapshot, and
// executes commands (list/open tabs, navigate, read, click, type) on request.

const DEFAULT_URL = "ws://localhost:8765/ws/extension";
let ws = null;
let retry = 0;
let monitoring = true;

function getSettings() {
  return new Promise((res) =>
    chrome.storage.local.get(["serverUrl", "token", "monitoring"], res));
}

function send(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

async function pushTabs() {
  const tabs = await chrome.tabs.query({});
  send({ type: "snapshot", tabs: tabs.map((t) => ({ id: t.id, title: t.title, url: t.url, active: t.active })) });
}

async function connect() {
  // Never open a second socket while one is already connecting/open.
  if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) return;
  const s = await getSettings();
  monitoring = s.monitoring !== false;
  let url = s.serverUrl || DEFAULT_URL;
  if (s.token) url += (url.includes("?") ? "&" : "?") + "token=" + encodeURIComponent(s.token);
  try {
    ws = new WebSocket(url);
  } catch (e) {
    scheduleReconnect();
    return;
  }
  ws.onopen = () => { retry = 0; pushTabs(); };
  ws.onmessage = (m) => handleCommand(JSON.parse(m.data));
  ws.onclose = () => { ws = null; scheduleReconnect(); };
  ws.onerror = () => { try { ws.close(); } catch (_) { /* noop */ } };
}

function scheduleReconnect() {
  const delay = Math.min(1000 * 2 ** retry++, 15000);
  setTimeout(connect, delay);
}

async function activeTab() {
  const [t] = await chrome.tabs.query({ active: true, currentWindow: true });
  return t;
}

async function exec(tabId, func, args) {
  const [r] = await chrome.scripting.executeScript({ target: { tabId }, func, args });
  return r.result;
}

async function handleCommand(msg) {
  if (!msg || msg.type !== "command") return;
  const { id, action, params = {} } = msg;
  try {
    let data;
    if (action === "list_tabs") {
      const tabs = await chrome.tabs.query({});
      data = tabs.map((t) => ({ id: t.id, title: t.title, url: t.url, active: t.active }));
    } else if (action === "open_tab") {
      const t = await chrome.tabs.create({ url: params.url });
      data = { id: t.id, url: params.url };
    } else if (action === "activate_tab") {
      await chrome.tabs.update(params.tab_id, { active: true });
      data = "activated tab " + params.tab_id;
    } else if (action === "navigate") {
      const t = await activeTab();
      await chrome.tabs.update(t.id, { url: params.url });
      data = "navigating to " + params.url;
    } else if (action === "read") {
      const t = await activeTab();
      data = await exec(t.id, () => document.body.innerText.slice(0, 8000));
    } else if (action === "click") {
      const t = await activeTab();
      data = await exec(t.id, (sel) => {
        const e = document.querySelector(sel);
        if (!e) return "no element matches " + sel;
        e.click();
        return "clicked " + sel;
      }, [params.selector]);
    } else if (action === "type") {
      const t = await activeTab();
      data = await exec(t.id, (sel, val) => {
        const e = document.querySelector(sel);
        if (!e) return "no element matches " + sel;
        e.focus();
        e.value = val;
        e.dispatchEvent(new Event("input", { bubbles: true }));
        e.dispatchEvent(new Event("change", { bubbles: true }));
        return "typed into " + sel;
      }, [params.selector, params.text || ""]);
    } else if (action === "close_tab") {
      await chrome.tabs.remove(params.tab_id);
      data = "closed tab " + params.tab_id;
    } else {
      data = "unknown action " + action;
    }
    send({ type: "result", id, ok: true, data });
  } catch (e) {
    send({ type: "result", id, ok: false, data: String(e) });
  }
}

// Live tab monitoring → keep the backend snapshot fresh.
chrome.tabs.onUpdated.addListener(() => pushTabs());
chrome.tabs.onActivated.addListener(() => pushTabs());
chrome.tabs.onRemoved.addListener(() => pushTabs());

// Input-field activity relayed from content scripts (password values redacted).
chrome.runtime.onMessage.addListener((m) => {
  if (m && m.type === "input_activity" && monitoring) send({ type: "snapshot", inputs: [m.data] });
});

// MV3 service workers are killed after ~30s idle, which would silently drop the
// socket. A periodic alarm wakes the worker to reconnect (if dropped) or ping
// (to keep the connection — and the worker — alive).
chrome.alarms.create("xplogent-keepalive", { periodInMinutes: 0.4 }); // ~24s
chrome.alarms.onAlarm.addListener((a) => {
  if (a.name !== "xplogent-keepalive") return;
  if (!ws || ws.readyState === WebSocket.CLOSED) connect();
  else if (ws.readyState === WebSocket.OPEN) send({ type: "ping" });
});

// Reconnect promptly when Chrome starts or the extension is (re)installed.
chrome.runtime.onStartup.addListener(connect);
chrome.runtime.onInstalled.addListener(connect);

connect();
