# nodes/should_fix_deploy.py
"""Route after deploy_git: переход на анализ скринов только если в логе нет ошибки деплоя; иначе — повторить fix_deploy."""

from agents.validate_agent.state import ValidateAgentState

MAX_FIX_ATTEMPTS = 5


def _deploy_failed(state: ValidateAgentState) -> bool:
    """True, если в deploy_log есть признак ошибки деплоя (remote/post-receive или типичные маркеры)."""
    log = (state.get("deploy_log") or "") + (state.get("deploy_url") or "")
    if not log.strip():
        return True  # пустой лог = деплой не запустился или упал без вывода
    markers = [
        "Ошибка деплоя",
        "ERROR: Деплой завершился с ошибкой",
        "Деплой завершился с ошибкой",
        "ERROR:",
        "Deployment error",
        "invalid tag",
        "repository name must be lowercase",
        "Cannot find module",
        "failed with error",
        "Build failed",
        "npm ERR!",
    ]
    log_lower = log.lower()
    return any(m in log for m in markers) or "error" in log_lower


def should_fix_after_deploy(state: ValidateAgentState) -> str:
    """run_screenshots только если ошибки деплоя нет; иначе fix_deploy (до MAX_FIX_ATTEMPTS раз)."""
    if not _deploy_failed(state):
        return "run_screenshots"
    fix_attempts = state.get("fix_attempts") or 0
    if fix_attempts >= MAX_FIX_ATTEMPTS:
        return "run_screenshots"
    return "fix_deploy"
