"""Mark spec pipeline complete and build generation_plan from page_briefs."""
from __future__ import annotations

from typing import Any

from agents.generate_agent.spec.utils.generation_plan import build_generation_plan


async def spec_finalize_node(state: dict[str, Any]) -> dict[str, Any]:
    return {"_spec_done": True, "generation_plan": build_generation_plan(state)}
