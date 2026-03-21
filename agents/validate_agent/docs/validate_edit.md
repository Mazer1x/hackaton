# Граф `validate_edit`: правки сайта по запросу

Пайплайн для **редактирования кода проекта** (Astro/Tailwind и т.д.) по тексту пользователя **без** скриншотов, деплоя и vision-анализа. Зарегистрирован в корневом `langgraph.json` как граф **`validate_edit`**.

## Сравнение с `validate_agent`

| | `validate_edit` | `validate_agent` (`main.py`) |
|---|-----------------|------------------------------|
| Назначение | Только правки в репозитории по задаче | Полный цикл: деплой → скрины → анализ → при необходимости правки → цикл |
| Точка входа | `perplexity_reasoning` | `deploy` |
| Скриншоты | Нет | Да |

В LangGraph Studio нужно **явно выбрать граф `validate_edit`**, иначе в трейсе будут другие ноды (например сразу `fix_site_react` без `perplexity_reasoning`).

## Цепочка нод

```
perplexity_reasoning → fix_site_react → git_commit_push → END
```

1. **`perplexity_reasoning`** — отдельный шаг рассуждения: краткое резюме для правки; опционально вызов **`perplexity_search`** (модели Perplexity через **OpenRouter**), только когда без актуальных данных из сети нельзя уверенно планировать правку.
2. **`fix_site_react`** — ReAct-агент с инструментами чтения/записи файлов в `project_path` (см. `llm/tools/fs_tools.py`).
3. **`git_commit_push`** — `git add .`, `git commit`, `git push` в каталоге проекта.

## Переменные окружения

Общие для агента (см. корневой `.env`):

| Переменная | Назначение |
|------------|------------|
| `OPENROUTER_API_KEY` | Доступ к OpenRouter (reasoning-модель в `perplexity_reasoning`, модель правок в `fix_site_react`) |
| `OPENROUTER_BASE_URL` | Обычно `https://openrouter.ai/api/v1` |
| `PERPLEXITY_MODEL` | Модель поиска для тулзы (по умолчанию `perplexity/sonar`) |
| `VALIDATE_EDIT_REASONING_MODEL` | Модель для ноды `perplexity_reasoning`; иначе `REASONING_MODEL`, иначе `OPENROUTER_MODEL` |
| `VALIDATE_FIX_SITE_MODEL` / `VALIDATE_FIX_MODEL` | Модель для `fix_site_react`; иначе `OPENROUTER_MODEL` |

Если `OPENROUTER_API_KEY` не задан, **`perplexity_reasoning`** пропускает веб-исследование (`edit_research_notes` пустой), но граф продолжает работу.

## Состояние (state)

Релевантные поля `ValidateAgentState`:

- **`project_path`** — абсолютный путь к корню сайта (где лежит репозиторий с `src/` и т.д.). Обязателен.
- **`messages`** — история чата; для текста задачи используется последнее human-сообщение (см. `last_human_text` в `should_fix_or_edit_site.py`).
- **`validation_result`** — опционально; если есть `errors` / `warnings`, `fix_site_react` ориентируется на них.
- **`json_data`** — опционально; может подставиться в контекст, если нет явного human-текста.
- **`edit_research_notes`** — заполняется **`perplexity_reasoning`**, передаётся в промпт **`fix_site_react`** как блок «Контекст из веб-поиска».

## Инструмент `perplexity_search`

Реализация: `llm/tools/perplexity_tool.py`. Запросы идут на OpenRouter Chat Completions с моделью вида `perplexity/sonar`, а не на прямой API Perplexity.

## Нода `fix_site_react`

- Инструменты: `read_file_in_project`, `write_file_in_project`, `list_directory_in_project`, `shell_execute_in_project` (ограниченный allowlist команд).
- Цикл ReAct не завершается «пустым» ответом модели, пока в истории не появится успешный результат записи: ответ инструмента с префиксом **`File written:`** (см. `fix_site_react_node.py`). Иначе выдаётся напоминание вызвать `write_file_in_project` с полным содержимым файла.
- Это снижает ситуации, когда модель утверждает, что файл изменён, но на диск ничего не записано.

## Нода `git_commit_push`

- Сообщение коммита фиксированное: `fix: user-requested site edits`.
- Если **`git commit`** сообщает `nothing to commit, working tree clean`, нового коммита не создано — тогда **`git push`** даст `Everything up-to-date`: на диске не было изменений относительно последнего коммита (в том числе если правки агента не были сохранены через `write_file_in_project`).

## Пример входа для Studio

Файл: `agents/validate_agent/spec/langgraph_input_validate_edit_example.json` — задайте **`project_path`** на каталог с клоном сайта и human-сообщение с задачей.

## Устранение неполадок

- **В трейсе нет `perplexity_reasoning`** — выбран граф `validate_agent`, а не `validate_edit`.
- **`Everything up-to-date` / `nothing to commit`** — после прогона проверьте `git status` в `project_path`; убедитесь, что в трейсе `fix_site_react` были вызовы с `File written:`.
- **Правки в «другом» каталоге** — `project_path` в инпуте должен совпадать с тем репозиторием, который вы открываете в IDE.

## Связанные файлы

| Файл | Роль |
|------|------|
| `validate_edit_graph.py` | Сборка графа |
| `nodes/perplexity_reasoning_node.py` | Reasoning + тулза поиска |
| `nodes/fix_site_react_node.py` | Правки кода |
| `nodes/git_commit_push_node.py` | Git |
| `llm/tools/perplexity_tool.py` | OpenRouter + Perplexity-модель |
| `llm/tools/fs_tools.py` | Файловые тулы |
| `state.py` | `ValidateAgentState` |
