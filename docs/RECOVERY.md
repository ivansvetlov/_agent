# Как восстановлен этот репозиторий

16.11.2026. До сбоя `_agent` был отдельным git-репозиторием **без remote** — поэтому после
потери `C:\Workspace` от него не осталось ни одной копии. Всё, что ниже, собрано из логов
чатов и уцелевших заметок.

## Что уцелело (полностью или частично)

| файл | источник | состояние |
|---|---|---|
| `AGENTS.md` | лог Grok `01a069b4` | восстановлен дословно, затем переработан под текущую реальность |
| `docs\state-of-workspace.md` | тот же лог | восстановлен (150 строк), переписан под 16.11.2026 |
| `tools\grok-session.py`, `opencode-session.py`, `opencode-cost.py` | лог `01a04a4c` | скопированы как есть |
| `skills-src\resume-grok`, `resume-opencode`, `opencode-cost` | тот же лог | скопированы как есть |
| `commands\opencode\resume-grok\resume-grok.md` | тот же лог | скопировано |
| `scripts\bootstrap.ps1` | тот же лог | был восстановлен; переписан под манифесты агентов |

## Что утрачено безвозвратно

| что | почему |
|---|---|
| `mcp\mcp-servers.json` | не редактировался ни в одной из сохранившихся сессий |
| `scripts\{doctor.ps1, regen-mcp.py, sync-agents.py}` | то же |
| `agents-src\` (4 субагента: code-architect, code-simplifier, code-reviewer, gate-reviewer) | то же |
| `docs\adr\ADR-001…005` | то же |
| `skills-src\` — 9 из 13 скиллов (`layout-qa`, `system-debug`, `ui-copy`, `ui-verify`, `frontend-design`, `agents-md-improver`, `acquire-tools-mcp-skills`, `feedback-loop`, `owner-operator`, `provision-vps-deploy`, `ralph-goal`) | то же |
| `docs\{hermes-playbook, install-guide, planning\TODO, schedules, lowrouter-cost-tracker}` | то же |
| `prompts\`, `libs\`, `configs\` | то же |

Список скиллов и их назначение известны из `state-of-workspace.md` — их можно написать заново,
но это новая работа, а не восстановление.

## Что написано заново

- `skills-src\evidence-first`, `skills-src\handoff` — по смыслу из конституции и практики;
- `skills-src\project-router` — восстановленный вариант указывал на `C:\Workspace` и мёртвые
  проекты, переписан под текущие пути;
- `subagents-src\{code-architect, code-reviewer, gate-reviewer}` — по описанию ролей в
  `state-of-workspace.md` и практике ревью;
- `mcp\mcp-servers.json` — реконструкция состава (playwright, chrome-devtools, context7,
  deepseek-judge), команды запуска не сохранились;
- `scripts\{sync-agents, doctor, mcp-sync, new-project, bootstrap}` — новая схема (манифесты агентов);
- `templates\project\` — скелет проекта;
- `docs\ADR-006-agents.md` — модель «агент добавляется манифестом».

## Проверка

- Все `.ps1` прогнаны (bootstrap, doctor) — см. вывод в первом коммите.
- Все скиллы имеют `SKILL.md`; `doctor.ps1` проверяет привязки.
- JSON-манифесты разбираются `ConvertFrom-Json`.
