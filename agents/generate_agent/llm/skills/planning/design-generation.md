---
name: design-generation
description: Generate concrete design decisions from a brief or brand: palette, typography, layout style, motion. Use when producing project_spec.design or translating a design brief into actionable visual choices.
---

# Skill: design generation

Use this skill when you need to **generate design** — i.e. turn a concept, brief, or brand into concrete visual decisions (palette, typography, layout, motion) that the frontend can implement. Applies to planning output (e.g. `project_spec.design`) or any step where "design" is produced from context.

## Inputs

- **Brand / business context**: name, tone, audience, goals, CTA.
- **Design brief** (if any): mood, style keywords, section concepts, UI Kit hints.
- **User description**: e.g. "minimal", "bold", "organic", "corporate", "playful".

## Output: concrete design decisions

Produce a small set of **actionable** decisions that the builder can use without guessing.

### 1. Palette

- **Primary background**: e.g. `slate-900`, `white`, `stone-100`, `zinc-950`.
- **Accent(s)**: 1–2 colors for CTAs, highlights, links (e.g. `amber-500`, `emerald-600`, `rose-500`).
- **Text**: primary and muted (e.g. `slate-100` / `slate-400`, or `stone-900` / `stone-600`).
- Optional: gradient direction, dark/light theme, grain or noise overlay.

Avoid vague "warm colors" — name Tailwind-style tokens or hex if needed (e.g. "warm beige background, soft pink and teal accents").

### 2. Typography

- **Headings**: font name + weight/variant (e.g. Playfair Display, Cormorant, Bebas Neue, Clash Display). Prefer distinctive, not Inter/Roboto.
- **Body**: readable pair (e.g. Inter, Source Sans, or a softer serif if it fits).
- **Character**: strict / soft / contrast / variable — one short phrase so the builder knows the intent.

### 3. Layout and composition

- **Density**: spacious vs dense; single column vs grid/multi-column.
- **Sections**: alignment (centered, asymmetric, full-bleed), max-width if relevant.
- **Components**: cards (bordered vs glass/blur), buttons (pill vs rounded vs organic blob), nav (inline vs minimal).

### 4. Motion and interaction

- **Level**: none / subtle / bold.
- **Hover**: e.g. lift, underline, glow, scale, color shift.
- **Scroll**: e.g. parallax, fade-in, stagger, "breathing" background.
- **Page load**: optional (e.g. short stagger, one key animation).

Keep it short: 2–4 bullets so the frontend knows what to implement without over-specifying.

### 5. Key requirements (checklist)

List 3–6 concrete requirements the frontend must satisfy, e.g.:

- "Custom CSS: at least 3 @keyframes (e.g. float, fade, pulse)."
- "Hero: one strong typographic headline, one CTA button with hover state."
- "No generic AI look: no gray-200 cards, no purple-on-white gradient."
- "Distinctive element: grain overlay OR gradient mesh OR asymmetric layout."

## Rules

1. **Be specific**: "amber-500 and slate-900" beats "warm and dark".
2. **Match context**: derive from brand and user description; don't default to one style.
3. **Implementable**: every choice should be doable in HTML/CSS and Tailwind (or plain CSS).
4. **Consistent**: one coherent direction (e.g. all "soft organic" or all "strict grid"), not a mix of unrelated trends.
5. **Brief-friendly**: if a design_brief exists (sections, UI Kit, animations), align with it and fill in only what's missing.

Use this skill in the planning phase when building `project_spec.design`, or whenever the system needs to "generate design" from a brief and user input.
