Статус: active

# __NAME__

Кратко: что это и для кого — одно-два предложения.

## Как открыть

```powershell
# статика (Kind=static)
python -m http.server 8080 --directory site

# сервис (Kind=service)
.venv\Scripts\python -m uvicorn app.main:app --reload
```

## Что внутри

| путь | что |
|---|---|
| `docs\HANDOFF.md` | где мы и что дальше — читать первым |
| `docs\ARCHITECTURE.md` | как устроено |
| `docs\DECISIONS.md` | почему так, а не иначе |
| `scripts\` | повторяемые операции, один файл = одна задача |
| `tests\` | тесты |

## Статус проекта

Первая строка этого файла — статус: `active` (развивается), `paused` (заморожен, но открывается),
`archived` (только чтение).
