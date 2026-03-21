"""
Граф validate_edit: правки кода **только по запросу пользователя** (ReAct + инструменты).
Скриншотов, загрузки и vision-анализа нет.

Цепочка: perplexity_reasoning (LLM + perplexity_search) → fix_site_react → git_commit_push → END.
Нужны: непустой project_path и human-сообщение с задачей (например цвет кнопки).
Для поиска Perplexity через OpenRouter: OPENROUTER_API_KEY; опционально PERPLEXITY_MODEL (по умолчанию perplexity/sonar).
"""
from pathlib import Path

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from agents.validate_agent.state import ValidateAgentState
from agents.validate_agent.nodes.fix_site_react_node import fix_site_react_node
from agents.validate_agent.nodes.git_commit_push_node import git_commit_push_node
from agents.validate_agent.nodes.perplexity_reasoning_node import perplexity_reasoning_node

env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)


print(
    "Building validate_edit graph (perplexity_reasoning → fix_site_react → git_commit_push → END, no screenshots)"
)

builder = StateGraph(ValidateAgentState)

builder.add_node("perplexity_reasoning", perplexity_reasoning_node)
builder.add_node("fix_site_react", fix_site_react_node)
builder.add_node("git_commit_push", git_commit_push_node)

builder.set_entry_point("perplexity_reasoning")
builder.add_edge("perplexity_reasoning", "fix_site_react")
builder.add_edge("fix_site_react", "git_commit_push")
builder.add_edge("git_commit_push", END)

graph = builder.compile()

print("validate_edit graph compiled successfully!")
print("   Flow: perplexity_reasoning → fix_site_react → git_commit_push → END")
