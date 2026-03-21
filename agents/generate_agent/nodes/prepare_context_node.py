# nodes/prepare_context_node.py
"""
Prepare Context Node - runs after load_skills (when model called ready_to_execute).
Collects ToolMessage content from load_skill and read_file into state.loaded_skills_context
only from the last load_skills cycle (messages after the last HumanMessage).
Deduplicates load_skill by content and skips failed read_file results.
"""
from langchain_core.messages import HumanMessage

from agents.generate_agent.state import GenerateAgentState

CONTEXT_SEP = "\n\n---\n\n"

# read_file content prefixes that indicate failure — do not pass to execute
READ_FILE_FAILURE_PREFIXES = (
    "File not found:",
    "Read error:",
    "Directory not found:",
    "This is a directory:",
    "This is a file:",
    "Error reading",
)


def _is_failed_read_file(content: str) -> bool:
    """True if read_file returned an error message."""
    if not content or not isinstance(content, str):
        return True
    s = content.strip()
    return any(s.startswith(prefix) for prefix in READ_FILE_FAILURE_PREFIXES)


def _prepare_context_node(state: GenerateAgentState) -> dict:
    """
    Extract load_skill and read_file tool results from the last load_skills cycle only.
    Cycle = messages after the last HumanMessage (current load_skills task).
    - Deduplicates load_skill by exact content (same skill loaded multiple times → one block).
    - Skips read_file results that are errors (File not found, Read error, etc.).
    Execute will inject this as a dedicated "LOADED CONTEXT" block in its prompt.
    """
    messages = state.get("messages", [])
    # Only consider messages after the last HumanMessage (current load_skills run)
    last_human_idx = -1
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            last_human_idx = i
            break
    slice_start = last_human_idx + 1

    seen_skill_content: set[str] = set()
    parts: list[str] = []

    for msg in messages[slice_start:]:
        name = getattr(msg, "name", None)
        if name not in ("load_skill", "read_file", "read_file_in_site"):
            continue
        content = getattr(msg, "content", None)
        if not isinstance(content, str) or not content.strip():
            continue

        stripped = content.strip()

        if name == "load_skill":
            # Deduplicate: same skill text only once (LLM often calls load_skill multiple times)
            if stripped in seen_skill_content:
                continue
            seen_skill_content.add(stripped)
            parts.append(f"[load_skill]\n{stripped}")

        elif name in ("read_file", "read_file_in_site"):
            if _is_failed_read_file(content):
                continue
            parts.append(f"[read_file]\n{stripped}")

    loaded_skills_context = CONTEXT_SEP.join(parts) if parts else ""
    return {"loaded_skills_context": loaded_skills_context}
