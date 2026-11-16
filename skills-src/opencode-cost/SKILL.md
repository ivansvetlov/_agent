---
name: opencode-cost
description: >
  Дашборд расходов OpenCode + сессии Grok Build: стоимость и токены OpenCode из
  opencode.db, список Grok-сессий из ~/.grok/sessions. Триггеры: сколько потратили,
  расход токенов, opencode cost, дашборд расходов, cost dashboard, сколько стоит
  моя работа, grok spend, grok sessions cost.
---

# OpenCode + Grok Cost Dashboard — расходы и сессии

Читает два источника (фильтр `--days N` применяется к обоим):

- OpenCode: `~\.local\share\opencode\opencode.db` (таблица `session`: cost + токены,
  окно по `time_created`).
- Grok Build: `~\.grok\sessions\<urlencoded-cwd>\<id>\summary.json` (+ `signals.json`
  для context occupancy / turns). Окно по `updated_at`. У Grok **нет долларовой
  стоимости** в файлах сессии — скрипт пишет `grok: N sessions, cost unknown`,
  не выдумывает `$`.

Ничего не требует, только Python 3 + stdlib.

## Использование

```powershell
# сводка: OpenCode $ + секция Grok (counts/titles/cwd)
& C:\Workspace\_agent\.venv\Scripts\python.exe C:\Workspace\_agent\tools\opencode-cost.py

# последние N дней — фильтр на оба источника
& C:\Workspace\_agent\.venv\Scripts\python.exe C:\Workspace\_agent\tools\opencode-cost.py --days 7

# почасовая гистограмма (активные часы, $ OpenCode)
& C:\Workspace\_agent\.venv\Scripts\python.exe C:\Workspace\_agent\tools\opencode-cost.py --hours

# плоские записи JSON (source=opencode|grok); --days режет оба
& C:\Workspace\_agent\.venv\Scripts\python.exe C:\Workspace\_agent\tools\opencode-cost.py --json

# HTML-снимок + file:// ссылка
& C:\Workspace\_agent\.venv\Scripts\python.exe C:\Workspace\_agent\tools\opencode-cost.py --html
# открыть: C:\Workspace\_agent\tools\opencode-cost.html
```

### Из окна opencode

В TUI opencode набери **`/cost`** (кастомная команда, канон в
`_agent\commands\opencode\cost\cost.md`, junction в `~\.config\opencode\command\cost`).
Команда прогонит скрипт и покажет дашборд прямо в чате.

## Что даёт

- Стоимость в $ (OpenCode уже посчитал по прайсу модели).
- **Лимиты OpenCode Go** (5h $12 / week $30 / month $60) с прогресс-барами — сколько
  осталось от подписки.
- Токены: input/output/reasoning/cache (cache-чтение может быть гигантским — это ок).
- Разбивка по проектам, моделям, топ-сессии по стоимости.
- Почасовой профиль — где реально горит время/деньги (только OpenCode `$`).
- Секция **Grok Build**: число сессий, recent titles, cwd, model, context occupancy
  (текущее окно, не billed). JSON-строки с `"source": "opencode"|"grok"`. `--days`
  режет и OpenCode, и Grok.

> Примечание: сумма в дашборде — это **расчётная стоимость** по API-прайсу (как
> посчитал opencode), НЕ списание с карты. Подписка Go — фикс $5/мес (первый месяц,
> потом $10), лимиты — $12/$30/$60 эквивалента использования.

## Правила для агента

1. По запросу «сколько потратили» — запусти скрипт и покажи OpenCode total +
   per-project **и** Grok-секцию. Не складывай Grok в `$` OpenCode.
2. Заметил аномалию (сессия >$0.5 или проект резко растёт) — подсвети владельцу.
3. Данные локальные, секретов нет (cost/токены/слаг/проект/cwd). Не выводить полный
   JSON в чат без запроса — он длинный.
4. `opencode.db` может быть заблокирован, если opencode открыт — скрипт читает
   read-only; если WAL-локи мешают, скопируй db во временный файл.

## Траблшут

- `no sessions found` → путь БД неверный; проверь `C:\Users\MiBookPro\.local\share\opencode\opencode.db`.
- Grok-секция пустая → нет `summary.json` под `~\.grok\sessions`.
- Дубликаты расходов — нет: одна строка = одна сессия (в отличие от JSONL-логов Claude/Codex).
