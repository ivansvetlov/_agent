# MCP

Единый реестр серверов: `mcp-servers.json`. Правка только здесь; конфиги агентов — производные.

```powershell
powershell -File ..\scripts\mcp-sync.ps1            # показать diff по каждому агенту
powershell -File ..\scripts\mcp-sync.ps1 -Apply     # записать, с .bak рядом
```

## Форматы

| `mcp_format` | Куда пишется |
|---|---|
| `opencode` | `~/.config/opencode/opencode.json`, ключ `mcp` |
| `cordis` | `~/.dsh/profiles/<profile>/cordis.yml` — не реализовано, см. `agents\dsh.json` |

## Про реконструкцию

Реестр восстановлен по `docs\state-of-workspace.md` (упоминались playwright, chrome-devtools,
context7, deepseek-judge). Точные команды запуска и переменные утрачены — сверять при первом
запуске. Ключи: context7 перевыпустить, deepseek — из `.env`, в git не класть.
