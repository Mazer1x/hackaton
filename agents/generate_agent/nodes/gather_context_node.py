# nodes/gather_context_node.py
"""
Gather Context Node - runs after reasoning, before execute.
Loads skills via tools; results go to state.loaded_skills_context via prepare_context_node.
Does NOT pass full chat history to the LLM (only system + this step's task, or tail of current gather cycle).
"""
import os
from langchain_core.messages import HumanMessage, SystemMessage

from agents.generate_agent.state import GenerateAgentState
from agents.generate_agent.page_plan_context import compute_page_plan_context_updates
from agents.generate_agent.utils import format_reasoning_task, normalize_messages_for_api
from agents.generate_agent.llm.tools import get_gather_context_tools
from agents.generate_agent.llm.chat_factory import get_chat_llm

GATHER_MARKER = "GATHER CONTEXT — Load needed skills via load_skill/list_skills. When done, call ready_to_execute()."

GATHER_SYSTEM = """You are the context-gathering phase. Your ONLY job is to load guidelines for the next code step.

- Use load_skill(skill_name) for design/UI guidelines (e.g. frontend-design, astro-expert). Use list_skills() to see options.
- Do NOT read project files — file reading is disabled in this phase to keep context small.
- When you have enough guidelines for the executor, call ready_to_execute() and stop.
- Do NOT write any code or call write_file. Only gather skills.
"""


def _is_gather_task_message(msg) -> bool:
    """True if this HumanMessage is our gather-context task (so we don't add it twice)."""
    if msg is None or not hasattr(msg, "content"):
        return False
    content = getattr(msg, "content", "") or ""
    if isinstance(content, list):
        content = " ".join(
            b.get("text", b) if isinstance(b, dict) else str(b) for b in content
        )
    return GATHER_MARKER in content and "ready_to_execute" in content


def _gather_context_node(state: GenerateAgentState) -> dict:
    """
    Run LLM with gather tools (load_skill, list_skills, ready_to_execute only — no read_file_in_site).
    Invoke payload: System + (fresh task HumanMessage) OR System + tail since last gather HumanMessage.
    """
    decision = state.get("reasoning_decision", {})
    project_path = state.get("project_path", "/path/to/site")
    state_messages = list(state.get("messages", []))

    if not decision or decision.get("action") == "complete" or decision.get("done"):
        return {"messages": []}

    fp = (decision.get("file_path") or "").strip()
    if decision.get("action") == "create_file" and fp:
        scope_updates = compute_page_plan_context_updates(state, fp)
    else:
        scope_updates = {
            "active_page_id": None,
            "page_plan_context": None,
            "_page_plan_missing_before": None,
        }

    task_desc = format_reasoning_task(decision, project_path)
    ppc = (scope_updates.get("page_plan_context") or "").strip()
    if ppc:
        task_desc = f"{ppc}\n\n{task_desc}"
    gather_human = HumanMessage(
        content=f"""{task_desc}

{GATHER_MARKER}
"""
    )

    last_human = None
    for m in reversed(state_messages):
        if isinstance(m, HumanMessage):
            last_human = m
            break
    should_add_gather_human = not _is_gather_task_message(last_human)

    model = os.getenv("EXECUTE_MODEL") or os.getenv("OPENROUTER_MODEL")
    llm = get_chat_llm(model=model, temperature=0.3, parallel_tool_calls=True)
    tools = get_gather_context_tools()
    llm_with_tools = llm.bind_tools(tools, tool_choice="auto")

    if should_add_gather_human:
        # New gather cycle: do not send full message history — only system + task
        to_send = [SystemMessage(content=GATHER_SYSTEM), gather_human]
    else:
        # Continue same gather cycle: messages since last gather HumanMessage (tool rounds only)
        last_gather_idx = -1
        for i in range(len(state_messages) - 1, -1, -1):
            msg = state_messages[i]
            if isinstance(msg, HumanMessage) and _is_gather_task_message(msg):
                last_gather_idx = i
                break
        if last_gather_idx < 0:
            to_send = [SystemMessage(content=GATHER_SYSTEM), gather_human]
        else:
            tail = state_messages[last_gather_idx:]
            to_send = [SystemMessage(content=GATHER_SYSTEM)] + tail

    response = llm_with_tools.invoke(normalize_messages_for_api(to_send))

    if should_add_gather_human:
        out = {"messages": [gather_human, response]}
    else:
        out = {"messages": [response]}
    out.update(scope_updates)
    return out
