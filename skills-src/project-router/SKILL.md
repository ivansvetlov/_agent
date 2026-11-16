---
name: project-router
description: >
  Выбрать правильный проект и рабочий каталог до начала правок. Живые проекты:
  iiko-connector, nasledniki, bloom-crm, qmeka + инфраструктура _agent.
  Триггеры: какой проект, cwd, накладные, iiko, карта, наследники, шов, CRM, КП,
  кумека, qmeka, оркестратор, скиллы, MCP, воркспейс.
---

# Project router

Корень: `C:\Users\MiBookPro\Workspace`. Всё, что не `projects\`, — инфраструктура.

| О чём речь | Каталог | С чего начать |
|---|---|---|
| Накладные, iiko, MAX/TG-бот, OCR, распознавание | `projects\iiko-connector` | `README.md`, `docs\HANDOFF.md`, `.env.example` |
| «НаСЛЕДНИКИ», карта Самарской области, редактор границ, шов | `projects\nasledniki` | `docs\HANDOFF.md`, `docs\MAP-EDITOR.md` |
| CRM, КП, лендинг, flowwow, кабинет флориста | `projects\bloom-crm` | `README.md`, `docs\` |
| Кумека, Qmeka, оркестратор, пайплайны, з.аи, судья | `projects\qmeka` | `docs\HANDOFF.md`, `docs\ORCHESTRATOR_DESIGN.md` |
| Скиллы, субагенты, MCP, ADR, шаблоны проектов, конституция | `_agent` | `AGENTS.md`, `docs\state-of-workspace.md` |
| Разборы, чужие тексты, экспорты, идеи вне кода | `_notes` | имена файлов говорящие |
| Старьё, архивы сессий агентов | `_archive` | только чтение |
| «Разберу потом» | `_inbox` | можно мусорить |

## Правила

1. Перед правкой подтверди, что каталог соответствует теме. Сомневаешься — спроси.
2. `paused`-проект (nasledniki, bloom-crm, qmeka) не правим без явной просьбы: сначала читаем
   `docs\HANDOFF.md`, потом решаем.
3. Замороженные и мёртвые проекты из прошлого (`mandate-crisis`, `agent-lab`, `hermes`,
   `flowwow-crm.ru`) не воссоздаём в `projects\`.
4. Канон скиллов — `_agent\skills-src\`; каталоги `skills\` — junction'ы, править их бессмысленно.

## Частые команды

```powershell
powershell -File _agent\scripts\doctor.ps1         # состояние: junction'ы, remote, HANDOFF
powershell -File _agent\scripts\sync-agents.ps1    # раскатать канон по агентам
git -C projects\<name> status --short --branch     # перед правками
```
