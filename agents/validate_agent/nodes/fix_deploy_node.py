# nodes/fix_deploy_node.py
"""
React-style fix node: after deploy failure, LLM reasons over deploy_log and uses
FS tools (read/write/list/shell) to fix the project, then we retry deploy.
"""
import os
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from agents.validate_agent.state import ValidateAgentState
from agents.validate_agent.llm.tools import get_fix_tools
from agents.validate_agent.llm import get_chat_llm

FIX_SYSTEM = """You are a deploy-fix agent. The git push succeeded but the remote deploy failed (build or runtime error).
Your job: understand the error from the deploy log, then use the file system tools to fix the project so the next deploy can succeed.

You have these tools (all paths are relative to the project root):
- read_file_in_project(path) — read file, e.g. "astro.config.mjs", "src/pages/index.astro"
- write_file_in_project(path, content) — create or overwrite file
- list_directory_in_project(path) — list dir, use "." for project root
- shell_execute_in_project(command) — run command in project dir, e.g. "npm run build", "npm install"

Steps:
1. Read the deploy log and identify the error (e.g. "Cannot find module 'astr/config'", "repository name must be lowercase", missing file, syntax error).
2. Use read_file_in_project to inspect the relevant files.
3. Apply fixes (write_file_in_project, or fix config/imports).
4. Run "npm run build" (or "npm install && npm run build") via shell_execute_in_project to verify the project builds locally.
5. If build still fails, analyze the new error and fix again. You may do several read/fix/build cycles.

Important:
- For "repository name must be lowercase": fix repo_name in the input (you cannot change that here); or if the error is in the project (e.g. Docker tag), fix the config that generates the tag.
- For "Cannot find module 'astr/config'" or similar: fix the typo (e.g. 'astr' → 'astro') in the file that imports it.
- Use relative paths only, e.g. "astro.config.mjs", "src/layouts/Layout.astro".
"""

MAX_FIX_ITERATIONS = 8


def _run_fix_loop(project_path: str, deploy_log: str, messages: list) -> list:
    tools = get_fix_tools(project_path)
    model = get_chat_llm(
        model=os.getenv("VALIDATE_FIX_MODEL") or os.getenv("OPENROUTER_MODEL") or "anthropic/claude-sonnet-4.5",
        temperature=0.3,
        parallel_tool_calls=False,
    )
    llm_with_tools = model.bind_tools(tools, tool_choice="auto")
    current = list(messages)
    for _ in range(MAX_FIX_ITERATIONS):
        response = llm_with_tools.invoke(current)
        if not isinstance(response, AIMessage):
            current.append(response)
            continue
        current.append(response)
        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            break
        for tc in tool_calls:
            name = tc.get("name")
            args = tc.get("args") or {}
            tool = next((t for t in tools if t.name == name), None)
            if not tool:
                current.append(
                    ToolMessage(
                        content=f"Unknown tool: {name}",
                        tool_call_id=tc.get("id", ""),
                    )
                )
                continue
            try:
                out = tool.invoke(args)
            except Exception as e:
                out = f"Tool error: {e!s}"
            current.append(
                ToolMessage(content=str(out), tool_call_id=tc.get("id", ""))
            )
    return current


def fix_deploy_node(state: ValidateAgentState) -> dict:
    project_path = state.get("project_path") or ""
    deploy_log = state.get("deploy_log") or ""
    fix_attempts = state.get("fix_attempts") or 0

    if not project_path:
        return {"fix_attempts": fix_attempts + 1, "messages": []}

    user_content = f"""Deploy failed. Project path: {project_path}

Deploy log:
---
{deploy_log}
---

Use the tools to read the relevant files, fix the errors (e.g. wrong imports, typos, invalid config), and run `npm run build` to verify. Then we will retry deploy."""

    messages = list(state.get("messages") or [])
    fix_messages = [
        SystemMessage(content=FIX_SYSTEM),
        HumanMessage(content=user_content),
    ]
    new_messages = _run_fix_loop(project_path, deploy_log, fix_messages)
    # Append only the new AI/Tool messages to state (without duplicating system/user)
    appended = new_messages[2:]  # skip system + first user
    return {
        "messages": messages + appended,
        "fix_attempts": fix_attempts + 1,
    }
