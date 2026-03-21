---
name: layout-dramaturgy
description: |
  Design the emotional scroll journey: section order, grids, spacing rhythm, focal points.
  Produces ASCII wireframe + structured layout_spec JSON.
  The most critical skill — this is where uniqueness vs template-look is decided.

  Use when: the landing-generator orchestrator calls this skill at Step 4.
---

# Layout Dramaturgy

Designs the page as an emotional journey, not a stack of components.
Produces an ASCII wireframe (spatial reasoning) and a structured layout spec (for codegen).

**This is the most important skill in the pipeline.**
A mediocre visual grammar with a great layout > great visual grammar with a generic layout.

---

## Input

Read ALL upstream artifacts:
- `generator/output/canonical_spec.json`
- `generator/output/brand_profile.json`
- `generator/output/design_tokens.json`
- `generator/output/typography_spec.json`

Also read:
- `@generator/knowledge/ascii-wireframe-grammar.md` (the syntax spec)
- `@generator/knowledge/anti-template-rules.md` (pattern avoidance)
- `@generator/knowledge/conversion-ux.md` (section order by goal)
- `generator/memory/patterns.json` (existing pattern hashes)

---

## Process

### Phase 1: Plan the Emotional Arc

Based on `site_goal`, determine the section sequence using `conversion-ux.md` as a starting point, then mutate.

Map each section to an emotional role:
- **anticipation**: build expectation (hero)
- **reveal**: show what you offer (features, services)
- **credibility**: prove it works (testimonials, cases, team, certificates)
- **climax**: the key moment (main CTA section, or a dramatic visual break)
- **conversion**: facilitate action (CTA, form, contacts)
- **closure**: wrap up (footer with legal)

### Phase 2: Generate 1 Layout Variant

Produce 1 layout variant: the most experimental and dramatic option. No safe alternatives.

1. Choose the boldest structural approach
2. Name it with a short tagline
3. Generate an ASCII wireframe following the grammar

### Phase 3: Anti-Template Check

For the variant:
1. Compute pattern hash (section_sequence + grid_types)
2. Compare to `memory/patterns.json`
3. If Jaccard similarity > 0.7 to any existing pattern: apply mutation
4. Check entropy score (minimum 5/6 from anti-template-rules.md)

### Phase 4: Select and Output

- In **interactive mode**: present the variant with its ASCII wireframe
- In **one-shot mode**: use the variant if it passes anti-template check (entropy >= 5)

### System Prompt

```
You are a layout dramaturge — half creative director, half theatrical director.
You design the emotional journey of a web page scroll.

Given brand profile, design tokens, and content requirements, produce 1 layout variant: the most experimental and dramatic option. No safe alternatives.

MANDATORY: ALL sections from sections_available that are true MUST appear in the layout. Never drop a section. If sections_available.faq=true, there MUST be a FAQ section. If sections_available.achievements=true, there MUST be an achievements section.

At least 2 sections must use asymmetric or 60-40/40-60 grids.
At least 1 section must be full-bleed with height: 100vh or generous padding.

For the variant:
1. name: short memorable name
2. tagline: 1-sentence description of the structural concept
3. ascii_wireframe: full page wireframe following the ASCII grammar specification below

ASCII GRAMMAR RULES:
- +--[SECTION_NAME]--+ for section boundaries
- {grid: TYPE} {h: HEIGHT} for section metadata
- "text" for headlines, [Button Text] for CTAs
- IMG[ratio] for images, ICON[name] for icons
- ---NNpx--- for vertical spacing between sections
- ★ prefix for the bold design move section
- See full grammar specification in the provided context

CRITICAL RULES:
- MANDATORY: ALL sections from sections_available that are true MUST appear in the layout. Never drop a section.
- At least 2 sections must use asymmetric or 60-40/40-60 grids
- At least 1 section must be full-bleed with height: 100vh or generous padding
- At least ONE section must use asymmetric grid (not equal-N, not full-width)
- Spacing between sections MUST vary (rhythm, not uniform)
- The bold design move from design_tokens MUST be implemented in ONE section (mark with ★)
- Section order must NOT match: hero -> features -> testimonials -> CTA -> footer
- Each section has exactly ONE focal point
- NAV must be sticky, FOOTER must contain legal data
- Every section MUST have a background_layer hint (type + hint text)
- Use BG[type] notation in the ASCII wireframe for each section background
- NO section may have an empty/white background — at minimum use a gradient

SECTIONS AVAILABLE (ALL of these MUST appear in the layout — never drop any):
{list from canonical_spec.sections_available where value is true}

SITE GOAL: {site_goal} — use conversion-ux heuristics for optimal section ordering
```

### User Prompt

```
Brand: {brand_profile.chosen_direction as JSON}
Design tokens: {design_tokens as JSON, excluding shadow details}
Typography: headline size = {typography_spec.scale.hero.size}
Available sections: {canonical_spec.sections_available}
Available content: {canonical_spec.content — keys where value is not null}
Site goal: {canonical_spec.site_goal}
Price segment: {canonical_spec.price_segment}
Bold design move: {design_tokens.bold_design_move}
Bold move implementation: {design_tokens.bold_design_move_implementation}

Design 1 layout variant — the most experimental and dramatic option. No safe alternatives.
Include background_layer hint for each section using BG[type] notation.
```

---

## Output

Write to `generator/output/layout_spec.json`.

Must conform to `generator/contracts/layout_spec.schema.json`.

The `ascii_wireframe` field stores the chosen variant's wireframe as a string.
The `layout_variants` field stores the variant for reference.

---

## Quality Checks

Before writing output, verify:
- [ ] At least 1 asymmetric grid section exists
- [ ] Spacing between sections varies (at least 2 different values)
- [ ] One section is marked with bold_move_applied: true
- [ ] Section order doesn't match known template patterns
- [ ] NAV section has sticky: true
- [ ] Primary CTA appears within the first 2 content sections
- [ ] Total section count is reasonable (5-10 sections typical)
- [ ] Every section in layout_spec has a corresponding block in the ASCII wireframe
- [ ] Entropy score >= 5 (from anti-template checklist)
- [ ] ALL sections from sections_available appear in layout (never drop a section)
- [ ] At least 2 sections use asymmetric or 60-40/40-60 grids
- [ ] At least 1 section is full-bleed (100vh or generous padding)

---

## Pattern Memory Update

After successful generation, append to `generator/memory/patterns.json`:
```json
{
  "session_id": "{from canonical_spec}",
  "timestamp": "{current ISO-8601}",
  "pattern_hash": "{computed hash}",
  "section_sequence": ["nav", "hero", ...],
  "grid_types": ["auto", "60-40", ...],
  "brand_name": "{brand.name}"
}
```

---

## Token Budget

Expected: 4-8k tokens (most token-heavy reasoning skill).
