# Updating

When the repository changes, you can update Xplogent in one click.

## From the dashboard

Open **Settings → Update**:
1. Click **Check for updates** — Xplogent fetches the remote and shows how many
   commits you're behind, with a changelog.
2. Click **Update & restart** — it pulls, reinstalls, and restarts the backend.
   The page reconnects automatically when it's back.

## From the terminal

```bash
xplogent update      # git pull + reinstall (then restart xplogent up yourself)
```

## Notes

- One-click update works for **git-clone / editable installs**. If you installed
  from a package, the dashboard tells you and you update with your package
  manager instead.
- Updates use a **fast-forward pull**; if you have local commits or conflicts,
  resolve them in git first.
