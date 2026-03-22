"""Spec pipeline is wired in agents.generate_agent.main.

init_project → extract_user_design (LLM: guideline + design_preferences → design_tokens при наличии замысла)
→ при необходимости reference (run_screenshots → upload → delete_screenshots → vision)
→ prepare_spec_input (site_target: явный инпут или LLM по user_preferences + business_requirements)
→ page_briefs → spec_finalize → unsplash_search → analyze
"""
