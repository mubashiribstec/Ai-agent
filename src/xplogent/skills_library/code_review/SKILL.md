---
name: code_review
description: Review a code change or file for bugs, clarity, and risk.
trigger: when asked to review code, a diff, or a pull request
tools: [read_file, shell, web_search]
---

# Code review

1. Identify the scope: read the changed files (`read_file`) or run `git diff` via `shell`.
2. Check correctness first: logic errors, edge cases, error handling, off-by-ones,
   resource leaks, and concurrency issues.
3. Then clarity & maintainability: naming, duplication, dead code, missing tests.
4. Then risk: security (injection, secrets, unsafe deserialization), performance hot spots.
5. Report findings grouped by severity (must-fix / should-fix / nit), each with a file:line
   reference and a concrete suggested change. Be specific and brief.
