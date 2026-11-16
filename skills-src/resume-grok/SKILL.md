---
name: resume-grok
description: >
  Use when the user switched from Grok Build, says continue/resume a Grok
  session, names a Grok session by id (01a…) or title, or asks OpenCode to
  pick up after Grok. Triggers: grok session, продолжить сессию grok,
  /resume-grok, dump grok, после grok.
---

# Resume Grok session

Grok chats live in `~\.grok\sessions\<urlencoded-cwd>\<id>\` (`summary.json` + `chat_history.jsonl`). Do **not** use resume-opencode / `opencode.db`. Do **not** re-discover the layout.

## Source

| What | Where |
|---|---|
| Sessions | `~\.grok\sessions\` |
| Meta | `summary.json` (`generated_title`, `last_turn_summary`, `cwd`) |
| Transcript | `chat_history.jsonl` (`type` = user/assistant/…; user asks in `<user_query>`) |
| Tool | `C:\Workspace\_agent\tools\grok-session.py` |
| OpenCode TUI | `/resume-grok` (command in `_agent\commands\opencode\resume-grok`) |

Python: `C:\Workspace\_agent\.venv\Scripts\python.exe`.

## Procedure

1. Resolve the reference (`01a…`, title words, or «последняя» / omit = latest).
2. Dump. Do not write ad-hoc extractors.
3. Read the dump. Then **verify on disk** — `last_turn_summary` can lag.
4. Handoff, then continue only if the user asked to continue.

```powershell
$py = "C:\Workspace\_agent\.venv\Scripts\python.exe"
$tool = "C:\Workspace\_agent\tools\grok-session.py"

& $py $tool list --query "compressor" --limit 20
& $py $tool dump latest --out $env:TEMP\grok-dump.md
& $py $tool dump 01a04a4c-ad41-7b40-9bd5-b2ae28757e34 --out $env:TEMP\grok-dump.md
```

Flags: `--tail N` (default 8), `--full`, `--days N` on `list`.

## What to keep

1. **title / cwd / last_turn_summary**
2. **User queries** (already stripped of system/skill dumps)
3. **Last assistant texts**
4. Files named there — confirm they exist

Ignore: `type=reasoning`, tool_result payloads, `system-reminder` user rows.

## Handoff shape (required)

```
Session: <id> — <title>
Project/cwd: <cwd>
Done: <1-5 bullets of persisted work>
Leftover: <what Grok was mid-implementing>
Disk vs dump: <matches / missing>
Next: <one concrete step>
```

## Common mistakes

| Excuse | Reality |
|---|---|
| Scan `opencode.db` | Wrong product — Grok is JSONL under `~\.grok\sessions` |
| Dump whole jsonl into chat | Use the script; 100k+ lines |
| Trust last_turn_summary alone | Verify the files |
| Ad-hoc `_tmp_grok_*.py` | Extend `grok-session.py` |

## Verification

- [ ] Dump exited 0, file non-empty
- [ ] Handoff names real files on disk
- [ ] Next step matches the **last user** query
