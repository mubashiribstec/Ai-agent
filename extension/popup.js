const $ = (id) => document.getElementById(id);

chrome.storage.local.get(["serverUrl", "token", "monitoring"], (s) => {
  $("url").value = s.serverUrl || "ws://localhost:8765/ws/extension";
  $("token").value = s.token || "";
  $("mon").checked = s.monitoring !== false;
});

$("save").onclick = () => {
  chrome.storage.local.set({
    serverUrl: $("url").value.trim(),
    token: $("token").value.trim(),
    monitoring: $("mon").checked,
  }, () => {
    $("status").textContent = "Saved. Reconnecting…";
    chrome.runtime.reload(); // restart the service worker with new settings
  });
};
