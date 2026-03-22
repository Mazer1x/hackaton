# Граф `guideline_from_site`

Отдельный LangGraph-пайплайн: **первые скриншоты** уже собранного/запущенного сайта (тот же механизм, что и `run_screenshots`: Playwright, `agents.validate_agent.utils.run_screenshots`) и при отсутствии готового ТЗ — **синтез guideline** (`session_export` с полями `strategy` и `design`) через vision-модель по PNG.

## Когда использовать

- После **`init_project`** (Astro + Tailwind), когда сайт уже открывается локально (например `npm run dev` → `http://localhost:4321`).
- Во входе **нет** полноценного `json_data` / `session_export` с непустыми `strategy` и `design` — иначе шаг синтеза пропускается.

## Поток

1. **`prepare`** — `has_guideline(state)` → в state пишется `_skip_guideline_synthesis`.
2. **`capture_first_screenshots`** — subprocess `run_screenshots` с **разрешённым localhost** (в отличие от `run_screenshots_node` в validate после деплоя).
3. Условие:
   - если уже был guideline → **END** (скрины всё равно сняты);
   - иначе → **`synthesize_guideline`** — vision по локальным `screenshot_paths` → `session_export` + `json_data` + `guideline_source: screenshot_synthesis`.

## Переменные окружения

| Переменная | Назначение |
|------------|------------|
| `GUIDELINE_SITE_URL` | URL для съёмки, если не задан `site_url` в state (по умолчанию в коде `http://localhost:4321`) |
| `GUIDELINE_SITE_LOAD_DELAY_SECONDS` | Пауза перед скрином localhost (по умолчанию 2 с) |
| `VALIDATE_SITE_LOAD_DELAY_SECONDS` | Если задан `deploy_url`, используется задержка перед скрином продакшена |
| `VALIDATE_VISION_MODEL` | Модель для синтеза ТЗ по скринам |

## Вход (минимум)

- **`project_path`** — корень проекта сайта.
- Запущенный dev-сервер **или** задайте **`site_url`** / **`GUIDELINE_SITE_URL`**.

Пример: `agents/validate_agent/spec/langgraph_input_guideline_from_site_example.json`.

## Связка с `generate_agent`

Сейчас граф **не встроен** в `generate_agent/main.py`: там `prepare_spec_input` ожидает `strategy`+`design` в инпуте. Типичный сценарий:

1. Прогнать **`guideline_from_site`** → получить `session_export` / `json_data` в выходе.
2. Передать их в следующий запуск **`generate_agent`** (как `json_data` в Studio).

## Файлы

| Файл | Роль |
|------|------|
| `guideline_from_site_graph.py` | Сборка графа |
| `guideline_from_site_state.py` | `GuidelineFromSiteState` |
| `llm/guideline_helpers.py` | `has_guideline()` |
| `nodes/capture_first_screenshots_node.py` | Скрины (localhost OK) |
| `nodes/synthesize_guideline_from_screenshots_node.py` | Vision → JSON ТЗ |
