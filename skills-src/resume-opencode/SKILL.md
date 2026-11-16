---
name: resume-opencode
description: >
  Use when the user switched from OpenCode, says continue/resume an OpenCode
  session, names a session by id (ses_…) or title, or asks to dump/read an
  OpenCode chat. Triggers: opencode session, ses_, продолжить сессию opencode,
  содержимое сессии, /resume-opencode, dump opencode.
---

# Resume OpenCode session

OpenCode chats live in SQLite, not JSONL. Do **not** use resume-claude / resume-codex / `~/.zcode`. Do **not** re-discover the schema.

## Source

| What | Where |
|---|---|
| DB | `~\.local\share\opencode\opencode.db` |
| Tables | `session`, `message` (role in `data` JSON), `part` (`type` = text/tool/reasoning/compaction/…), `todo` |
| Tool | `C:\Workspace\_agent\tools\opencode-session.py` |
| Cost dashboard | skill `opencode-cost` (same DB, different job) |

Python: `C:\Workspace\_agent\.venv\Scripts\python.exe` (stdlib only). Open the DB **read-only** (`file:…?mode=ro`). If WAL lock: the script copies db+wal to a temp file.

## Procedure

1. Resolve the reference the user gave (`ses_…`, title words, or «последняя»).
2. Run the dump. Do not write ad-hoc extractors.
3. Read the dump. Then **verify on disk** — compaction drops history; todos are often stale vs the last user turn.
4. Give a handoff, then continue only if the user asked to continue (this turn already did, or they say «продолжай»).

```powershell
$py = "C:\Workspace\_agent\.venv\Scripts\python.exe"
$tool = "C:\Workspace\_agent\tools\opencode-session.py"

# find
& $py $tool list --query "compressor-demo" --limit 20

# dump (stdout is long — write a file, then Read it)
& $py $tool dump ses_fb6af3d35ffeuKYWlsPeGQBXb4 --out $env:TEMP\oc-dump.md
& $py $tool dump "Автосейв разметки"
```

Flags: `--tail N` (last assistant texts, default 8), `--full` (no truncation), `--days N` on `list`.

## What to keep from the dump

Use these sections, in this order, for the handoff:

1. **title / directory / updated** — cwd of the work
2. **User messages** — skip `Continue if you have next steps` pings (script already drops them)
3. **Last assistant texts** — what it was doing when it stopped
4. **File write/edit** — candidates; confirm they still exist and match the last intent
5. **Todos** — hints only. Prefer the last user turn over todo status

Ignore: reasoning parts, step-start/finish, compaction payloads (`auto`/`tail_start_id` — they are not summaries).

## Handoff shape (required)

```
Session: <id> — <title>
Project/cwd: <directory>
Done: <1-5 bullets of persisted work>
Leftover: <what the last assistant was mid-implementing>
Disk vs dump: <matches / missing / stale todos>
Next: <one concrete step>
```

Do not paste the full dump into chat. Do not claim the previous agent finished a step unless the file on disk shows it.

## Common mistakes

| Excuse | Reality |
|---|---|
| `opencode session list` / TUI is enough | Need messages + parts from SQLite |
| Scan `~\.zcode` or Claude JSONL | Wrong product |
| Dump every reasoning/tool payload | 2k+ parts; use the script |
| Trust `todo` status | Last user text wins |
| Continue coding before dump | Handoff first, then implement |
| Ad-hoc `_tmp_oc_*.py` | Extend `opencode-session.py` |

## Verification

- [ ] Dump command exited 0 and file is non-empty
- [ ] Handoff names real files that exist on disk
- [ ] Next step matches the **last user** turn, not an old todo
