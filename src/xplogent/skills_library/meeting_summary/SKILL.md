---
name: meeting_summary
description: Turn a transcript or notes into a clear summary with action items.
trigger: when given meeting notes, a transcript, or asked to summarize a discussion
tools: [read_file]
---

# Meeting summary

1. Read the source (`read_file` if it's a file, otherwise the pasted text).
2. Produce: a 2-3 sentence **TL;DR**, then **Decisions**, then **Action items**
   (owner + due date when stated), then **Open questions**.
3. Keep names and dates exact. Omit small talk. Use short bullets.
