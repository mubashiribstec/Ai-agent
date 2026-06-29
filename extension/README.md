# Xplogent Browser Control (Chrome extension)

Gives your Xplogent agent eyes and hands in your **real** Chrome browser: it can
list your open tabs, see the page you're actually looking at, and navigate /
click / type on your behalf — plus stream a live view of your tabs and
input-field activity back to the dashboard's **Browser** view.

This is different from the built-in Playwright `browser` tool (a separate,
automated Chromium). Use the extension when you want the agent to act on the
browser *you* are using.

## Install (developer mode)

1. Start Xplogent: `xplogent up` (backend on `http://localhost:8765`).
2. Open `chrome://extensions`, enable **Developer mode** (top-right).
3. Click **Load unpacked** and select this `extension/` folder.
4. Click the Xplogent toolbar icon → set the **Backend WebSocket**
   (default `ws://localhost:8765/ws/extension`) and, if you enabled an access
   token (`xplogent token`), paste it. Save & reconnect.
5. The dashboard **Browser** view shows "connected" with your live tabs.

## What it can do

The agent's `web_browser` tool routes through the extension:
`list_tabs`, `open_tab`, `activate_tab`, `navigate`, `read`, `click`, `type`,
`close_tab`. Write actions go through Xplogent's normal approval gate.

## Privacy

- Input-field monitoring reports **metadata only** (field name, type, page URL)
  on focus — it never captures what you type, and password fields are flagged
  `redacted`. Toggle it off in the popup.
- The extension only talks to the backend URL you configure (your own machine by
  default). Nothing is sent anywhere else.
