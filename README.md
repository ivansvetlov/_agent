# _agent

Инфраструктура агентского пространства: конституция, скиллы, субагенты, MCP, шаблоны, инструменты.
Отдельный репозиторий, чтобы правила и скиллы переживали сбои и не дублировались по проектам.

Восстановлен 16.11.2026 после потери `C:\Workspace` — см. `docs\RECOVERY.md`.

## Быстрый старт

```powershell
# привязать скиллы к агентам, разложить субагентов, проверить состояние
powershell -File scripts\bootstrap.ps1

# диагностика: junction'ы, remote у репозиториев, HANDOFF в проектах
powershell -File scripts\doctor.ps1

# только синхронизация агентов (после правки agents\*.json)
powershell -File scripts\sync-agents.ps1

# новый проект из шаблона
powershell -File scripts\new-project.ps1 -Name my-project -Kind service
```

## Структура

```
AGENTS.md            конституция: правила для всех агентов
agents\              манифесты агентов (куда линковать канон)
skills-src\          канон скиллов: <name>\SKILL.md
subagents-src\       канон субагентов: <name>\agent.md
mcp\                 реестр MCP-серверов
commands\            слэш-команды агентов
tools\               утилиты: чтение сессий Grok/OpenCode, стоимость прогонов
scripts\             bootstrap, doctor, sync-agents, new-project, mcp-sync
templates\project\   скелет нового проекта
docs\                ADR, состояние воркспейса, история восстановления
```

## Добавить агента

Положить `agents\<id>.json` (см. `AGENTS.md` §4) и запустить `scripts\sync-agents.ps1`.
Скиллы и субагенты подтянутся в его каталоги сами.
