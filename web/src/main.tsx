import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./styles.css";

// Apply the saved theme + accent before first paint.
const theme = localStorage.getItem("xplogent_theme") || "auto";
if (theme !== "auto") document.documentElement.setAttribute("data-theme", theme);
const accent = localStorage.getItem("xplogent_accent");
if (accent) document.documentElement.style.setProperty("--accent", accent);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
