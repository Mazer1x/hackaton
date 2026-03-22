# validate_agent

Графы валидации и правок сайта для LangGraph (см. корневой `langgraph.json`).

## Документация

- **[Редактирование без скриншотов: `validate_edit`](docs/validate_edit.md)** — цепочка `perplexity_reasoning` → `fix_site_react` → `git_commit_push`, переменные окружения, типичные проблемы.
- **[Первые скрины и guideline со страницы: `guideline_from_site`](docs/guideline_from_site.md)** — после init: съёмка (в т.ч. localhost) и синтез `session_export`, если нет ТЗ.

## Графы из этого пакета

| Имя в `langgraph.json` | Модуль |
|------------------------|--------|
| `validate_agent` | `main.py` |
| `validate_edit` | `validate_edit_graph.py` |
| `deploy` | `deploy_graph.py` |
| `screenshot_analysis` | `screenshot_analysis_graph.py` |
| `unified` | `unified_graph.py` |
| `guideline_from_site` | `guideline_from_site_graph.py` |

Примеры входных JSON: каталог `spec/`.
