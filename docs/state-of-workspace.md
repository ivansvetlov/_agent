# State of workspace — что изменилось

Обновлено: 2026-11-16.

> Для агентов после перерыва. Дельта и текущая правда. Читать вместе с `_agent\AGENTS.md`.

## 2026-11-16. Восстановление после сбоя

**Что случилось.** 15.11.2026 погиб рабочий корень `C:\Workspace`. Уцелели части в
`Workspace backup` (36,8 ГБ) и логи чатов агентов. GitHub: `bloom-crm`, `nasledniki`,
`iiko-connector` — уцелели полностью.

**Что восстановлено:**

| что | откуда | состояние |
|---|---|---|
| `bloom-crm`, `nasledniki`, `iiko-connector` | GitHub | склонированы в `projects\` |
| Код Qmeka (бывш. orchestrator) | логи Grok `01a069b4` | `projects\qmeka`, статус paused, 28 файлов |
| `_agent` | логи Grok `01a04a4c`, `01a069b4` | этот репозиторий: конституция, 7 скиллов, 3 субагента, MCP-реестр, скрипты, шаблоны |
| Наследники: шов 21–24.08 | логи Grok `01a026c3` | 25 файлов в `_recovery\`, ещё не в git |
| Заметки и замыслы | диски + логи | `_notes\`: ORG-PROPOSAL, QMEKA-VISION, NASLEDNIKI-POSTMORTEM |

**Что настроено заново:** git (user, UTF-8, quotepath), `gh` (авторизован, credential helper),
PowerShell 7 + профиль UTF-8, обёртка `pwsh-utf8` для OpenCode.

**Что перенесено:** личные данные (34,19 ГБ) — из воркспейса в `C:\Users\MiBookPro\Documents\no ai`.

**Что удалено/уйдёт:** `Workspace backup` (осталось ~2,6 ГБ) — после архивации сессий агентов.

## Текущая структура

```
Workspace\
├── AGENTS.md, README.md
├── projects\{iiko-connector, nasledniki, bloom-crm, qmeka}
├── _agent\        этот репозиторий
├── _notes\
├── _recovery\     временно: восстановленное из логов, до переноса в проекты
├── _archive\
├── _backup\       манифест 10 598 файлов, скрипты
└── Workspace backup\   остатки, под удаление
```

## Агенты и как они подключены

| агент | как получает канон | состояние |
|---|---|---|
| OpenCode | junction'ы скиллов в `~/.agents/skills`, копии субагентов в `~/.config/opencode/agents` | живой, манифест `agents\opencode.json` |
| DeepSeek Harness | плагинами профиля `~/.dsh/profiles/desktop`, каталога скиллов нет | живой, манифест `agents\dsh.json`, автолинковка не поддерживается |

Подробности модели — `docs\ADR-006-agents.md`.

## Открытые вопросы

1. `nasledniki`: восстановленные файлы (25, включая `map_editor.js` 196 КБ) не перенесены в репозиторий.
   Ждут решения: ветка `recovery/handoff-seam`.
2. `qmeka`: код неполон (6 модулей + `roles\`), статус paused. План — `projects\qmeka\docs\HANDOFF.md`.
3. `_agent`: скиллы `resume-grok`, `resume-opencode`, `opencode-cost` восстановлены из логов;
   остальные 9 кастомных скиллов и субагент `code-simplifier` утрачены — писать заново по мере надобности.
4. MCP-реестр — реконструкция: команды запуска серверов не сохранились, ключ context7 перевыпустить.
5. `Workspace backup` не удалён: сначала архивировать сессии Grok/Cline в `_archive`, потом чистить.

## Правила, которые появились после сбоя

- **Всё в git — с remote.** `_agent` был локальным репозиторием без remote и исчез целиком.
- **`docs\HANDOFF.md` в каждом проекте.** Его отсутствие — причина, по которой восстановление
  шло день, а не пять минут.
- **Восстановление из логов — штатный процесс.** Скрипты и метод: `_backup\` воркспейса,
  описание в `projects\qmeka\docs\RECOVERY.md`.
