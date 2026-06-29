// Reports input-field *activity* (focus) to the agent — metadata only. Field
// values are never sent (and password fields are flagged redacted), so the agent
// knows the user is filling a form without capturing what they type.

function describe(el) {
  const isPassword = el.type === "password";
  return {
    field: el.name || el.id || el.getAttribute("aria-label") || el.placeholder ||
           el.tagName.toLowerCase(),
    type: el.type || el.tagName.toLowerCase(),
    page: document.title,
    url: location.href,
    redacted: isPassword,
  };
}

document.addEventListener("focusin", (e) => {
  const el = e.target;
  if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA")) {
    try {
      chrome.runtime.sendMessage({ type: "input_activity", data: describe(el) });
    } catch (_) {
      /* extension reloading; ignore */
    }
  }
}, true);
