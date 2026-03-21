---
name: visual-grammar
description: |
  Generate design tokens: color palette, spacing scale, grid system, border radius,
  shadows, motion vocabulary, and one bold design move.

  Use when: the landing-generator orchestrator calls this skill at Step 3a.
---

# Visual Grammar Engine

Translates the chosen creative direction into a concrete visual system.
Produces design tokens that all downstream skills consume.

---

## Input

Read:
- `generator/output/brand_profile.json` (specifically `chosen_direction` and `tone`)
- `generator/output/canonical_spec.json` (for `preferences.animation_level` and `preferences.style`)

---

## Process

### MCP Usage

Before generating, query `context7` MCP for current Tailwind CSS token conventions:
- `resolve-library-id` with "tailwindcss"
- `query-docs` for "theme configuration colors spacing" to get token naming patterns

Also reference `@generator/knowledge/design-heuristics.md` for color theory and spacing rules.

### System Prompt

```
You are a visual systems designer at a world-class agency.

Given a creative direction and brand context, produce a complete visual grammar.

Rules:
- palette: follow 60-30-10 ratio (background 60%, secondary 30%, accent 10%)
- All hex colors must pass WCAG AA contrast when text color is used on background
- Do NOT use pure black (#000000) or pure white (#ffffff) — use near-black/near-white
- spacing: must feel rhythmic, not mechanical
- motion.level: take from user preference (animation_level)
- bold_design_move: must be implementable in CSS/HTML (not "use 3D graphics")
  Good examples:
  - "Oversized hero headline at 15vw with tight -0.05em tracking"
  - "Full-bleed accent color section interrupting the neutral palette"
  - "Offset grid where images bleed outside their container by 10%"
  Bad examples:
  - "Use WebGL shader background" (too complex for codegen)
  - "Make it feel premium" (not actionable)
- bold_design_move_implementation: write the actual CSS concept
  Example: "hero h1 { font-size: 15vw; letter-spacing: -0.05em; line-height: 0.85; }"

### Dramatic Token Rules (WOW quality)
- motion.level MUST be "medium" or "max" unless the user explicitly chose animation_level: "none". Never default to "subtle".
- bold_design_move_implementation MUST contain: the CSS property, the exact value, and which section it applies to. No vague descriptions like "add visual interest".
- Anti-corporate palette: NEVER use generic corporate blue (#3B82F6), Bootstrap gray (#6B7280), or default SaaS green (#10B981) as primary colors. Create distinctive, brand-specific colors.

### Bold Design Move Examples
1. "Editorial 8:4 grid" — `.hero { display: grid; grid-template-columns: 8fr 4fr; } .hero-image { width: 115%; }` — hero section
2. "Diagonal clip-path sections" — `.section-angled { clip-path: polygon(0 0, 100% 4%, 100% 100%, 0 96%); }` — 2nd content section
3. "Mix-blend-mode headline" — `.hero-headline { mix-blend-mode: difference; color: white; font-size: clamp(4rem,12vw,10rem); }` — hero section
4. "Oversized section numbers" — `.section-number { font-size: clamp(10rem,20vw,25rem); opacity: 0.05; position: absolute; }` — all numbered sections
5. "Glassmorphism cards" — `.card { backdrop-filter: blur(12px); background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.12); }` — features section

```

### User Prompt

```
Creative direction: {brand_profile.chosen_direction as JSON}
Brand tone: {brand_profile.tone as JSON}
User style hint: {canonical_spec.preferences.style or "none"}
Animation preference: {canonical_spec.preferences.animation_level}
Price segment: {canonical_spec.price_segment}

Generate the visual grammar.
```

---

## Output

Write to `generator/output/design_tokens.json`.

Must conform to `generator/contracts/design_tokens.schema.json`.

---

## Quality Checks

Before writing output, verify:
- [ ] Primary text on background passes WCAG AA (4.5:1 contrast)
- [ ] Accent on background passes WCAG AA for large text (3:1)
- [ ] motion.level matches canonical_spec.preferences.animation_level
- [ ] bold_design_move is concrete and implementable (not vague)
- [ ] bold_design_move_implementation contains actual CSS or layout instructions
- [ ] Spacing values are in rem (not px) for responsiveness

Use `html-css` MCP -> `get_docs` for "contrast ratio" if unsure about WCAG calculations.

---

## Token Budget

Expected: 1.5-3k tokens.
