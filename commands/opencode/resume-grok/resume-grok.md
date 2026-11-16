---
description: Dump a Grok Build session so we can continue that work here
agent: build
---

The owner wants to continue a **Grok Build** session in OpenCode.

1. Read the skill `_agent/skills-src/resume-grok/SKILL.md` (or `~/.agents/skills/resume-grok/SKILL.md`).
2. Dump the session. If they named an id/title, pass it; otherwise `latest`:

```
& C:\Workspace\_agent\.venv\Scripts\python.exe C:\Workspace\_agent\tools\grok-session.py dump latest --out $env:TEMP\grok-dump.md
```

3. Read the dump file. Verify named files on disk. Give the handoff shape from the skill, then continue only if they asked to continue.

Do not invent the transcript. Do not query `opencode.db` for this.
