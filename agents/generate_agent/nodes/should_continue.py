# nodes/should_continue.py
from agents.generate_agent.state import GenerateAgentState


def _should_continue_gather(state: GenerateAgentState) -> str:
    """
    Routing after gather_context node.
    If the model made tool_calls → gather_tools_execute. Else → prepare_context (then execute).
    """
    messages = state.get("messages") or []
    if not messages:
        return "prepare_context"
    last = messages[-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "gather_tools_execute"
    return "prepare_context"


def _should_continue_after_gather_tools(state: GenerateAgentState) -> str:
    """
    Routing after gather_tools_execute.
    If ready_to_execute was called → prepare_context (fill loaded_skills_context, then execute). Else → gather_context (model can call more tools).
    """
    messages = state.get("messages", [])
    for m in reversed(messages):
        if hasattr(m, "tool_calls") and m.tool_calls:
            names = [tc.get("name") for tc in m.tool_calls]
            if "ready_to_execute" in names:
                return "prepare_context"
            return "gather_context"
    return "gather_context"


def _should_continue_reasoning(state: GenerateAgentState) -> str:
    """
    Routing after reasoning node. If complete → end. Else → check_step_file → analyze | gather_context.
    """
    decision = state.get("reasoning_decision", {})
    if not decision or not isinstance(decision, dict):
        print("WARNING: No decision from reasoning!")
        return "check_step_file"

    action = decision.get("action", "")
    if action == "complete":
        print("Reasoning decided project complete → verify_index_imports")
        return "verify_index_imports"

    iteration = state.get("iteration_count", 0)
    if iteration >= 100:
        print(f"WARNING: Iteration limit reached ({iteration}). Finishing.")
        return "verify_index_imports"

    print(f"→ check_step_file: {action}")
    return "check_step_file"


def _should_continue_after_check_step_file(state: GenerateAgentState) -> str:
    """
    Routing after check_step_file. If target file already existed → analyze.
    Else → gather_context (page_plan_context is applied inside gather from reasoning file_path).
    """
    if state.get("_step_file_existed"):
        return "analyze"
    return "gather_context"


def _should_continue_execute(state: GenerateAgentState) -> str:
    """
    Routing after execute node. Execute has only write_file_in_site; no move_on tool.
    If write_file_in_site was called → analyze (step done). Else → execute (retry/nudge).
    """
    messages = state.get("messages") or []
    if not messages:
        return "execute"
    for m in reversed(messages):
        if hasattr(m, "tool_calls") and m.tool_calls:
            names = [
                (tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None))
                for tc in m.tool_calls
            ]
            if "write_file_in_site" in names:
                return "analyze"
            return "execute"
    return "execute"


def _should_continue_after_tools_execute(state: GenerateAgentState) -> str:
    """
    Routing after tools_execute node.
    If the last tool call was move_on → analyze. Else → execute (to continue or call move_on).
    """
    messages = state.get("messages", [])
    for m in reversed(messages):
        if hasattr(m, "tool_calls") and m.tool_calls:
            names = [tc.get("name") for tc in m.tool_calls]
            if "move_on" in names:
                return "analyze"
            return "execute"
    return "execute"


def _should_continue_action(state: GenerateAgentState) -> str:
    """
    Routing after action node.
    Decides: go to tools or back to reasoning.
    """
    last = state["messages"][-1]
    
    # If action node called tools - go to tools node
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    
    # If action said project complete
    if hasattr(last, "content") and last.content:
        content = last.content.lower()
        if any(phrase in content for phrase in [
            "project complete",
            "all done",
            "completed"
        ]):
            return "end"
    
    # By default return to reasoning for new cycle
    return "reasoning"


def _should_continue_after_tools(state: GenerateAgentState) -> str:
    """
    Routing after tools node (legacy action flow).
    If load_skill/list_skills → back to action. Else → back to action (analyze will see new files).
    """
    messages = state["messages"]
    for msg in reversed(messages):
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            tool_names = [tc.get("name") for tc in msg.tool_calls]
            if any(name in ["load_skill", "list_skills"] for name in tool_names):
                print(f"Tools {tool_names} called → returning to action to continue")
                return "action"
            break
    return "action"
