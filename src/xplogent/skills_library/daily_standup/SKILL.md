---
name: daily_standup
description: Prepare a concise daily standup update from recent work.
trigger: when asked for a standup, status update, or "what did I do"
tools: [shell, read_file]
---

# Daily standup

1. Gather signal: recent commits (`git log --since=yesterday --oneline` via `shell`),
   changed files, and any notes (`read_file`).
2. Produce three short sections: **Yesterday** (done), **Today** (plan), **Blockers**.
3. Keep each bullet one line. Lead with outcomes, not activity.
