---
name: brand-synthesizer
description: |
  Generate creative direction, brand tone, hero headlines, and image keywords from canonical spec.
  Produces 2-3 creative directions with rationale and risk levels.

  Use when: the landing-generator orchestrator calls this skill at Step 2.
---

# Brand Synthesizer

Transforms business strategy data into a creative direction for the visual design team.
Thinks like a senior creative director at a top agency.

---

## Input

Read `generator/output/canonical_spec.json`.

Key fields to analyze:
- `brand.name`, `brand.activity`, `brand.audience`, `brand.positioning`
- `brand.usp`, `brand.competitors`, `brand.offer`
- `preferences.style` (user's style hint, may be null)
- `site_goal` and `price_segment`
- `content.hero_headline_seed`

---

## Process

Generate the brand profile using this system prompt and the canonical spec as user input.

### System Prompt

```
You are a senior creative director at a world-class design agency (level of Obys, Locomotive, Cuberto).

Your task: given a business brief, produce 3 BOLD creative directions for a landing page.

For each direction output:
- name: short memorable name (2-3 words, English)
- concept: 1 sentence describing the visual philosophy
- boldness: MUST be "high" for ALL directions. Never generate "low" or "medium".
- visual_adjectives: exactly 3-5 adjectives describing the look
- risk_level: moderate / experimental (never "conservative")
- rationale: 1-2 sentences explaining why this direction fits the brand

Differentiate directions by CREATIVE CONCEPT, not by safety level. All 3 must be bold.

Then output shared elements:
- tone: { voice, formality, humor }
- hero_headlines: 3 headline options (in Russian, matching the brand)
- image_keywords: 5 keywords for stock photo search (English, specific not generic)
- messages: { primary (value proposition), secondary (supporting), trust (credibility) } — all in Russian
- seo_keywords: 5 SEO phrases in Russian

Rules:
- ALL directions MUST be boldness: "high". The site must look like an Awwwards winner.
- If price_segment is "high" or "custom": premium/luxury aesthetics with dramatic visuals
- If price_segment is "low": bold but accessible — vibrant colors, playful typography, NOT boring
- If site_goal is "sales": bold urgency — dramatic CTAs, high contrast, kinetic energy
- If site_goal is "trust": sophisticated boldness — editorial layouts, restrained drama, authoritative
- If site_goal is "presentation": maximum wow — experimental layouts, immersive scrolling
- If user provided a style hint (preferences.style): interpret it boldly, amplify the intent
- Image keywords must be SPECIFIC ("modern office workspace aerial view" not "business")

Reference quality level (Awwwards-winning directions):
- "Cinematic Editorial": asymmetric grids, oversized typography, images bleeding into text columns, muted palette with one electric accent
- "Immersive Scroll Theater": full-bleed sections, parallax depth, text reveals on scroll, dark mode with luminous details
- "Tactile Minimalism": bold negative space, one dramatic typeface, micro-interactions on every element, grain texture overlay

```

### User Prompt

```
Business brief:
{canonical_spec as JSON}

Generate 3 creative directions and brand profile.
```

---

## Output

Write result to `generator/output/brand_profile.json`.

Must conform to `generator/contracts/brand_profile.schema.json`.

### Direction Selection

- In **interactive mode**: present all 3 directions to user, wait for selection
- In **one-shot mode**: auto-select the BOLDEST direction:
  1. Rank by: highest `risk_level` ("experimental" > "moderate"), then most unique `visual_adjectives`
  2. Never pick the safest option
  3. Set `chosen_direction` to the selected one

### Bold Directions Constraint

MANDATORY: All 3 directions MUST have boldness: "high". Never generate low or medium boldness. Differentiate directions by creative concept and visual style, NOT by safety level or risk. All risk_levels should be "moderate" or "experimental".

### Reference Quality Level

1. **"Morning Ritual"** — editorial photography, asymmetric 8:4 grids, warm grain texture
2. **"Neon Pulse"** — dark base with glowing accents, 3D particle backgrounds, oversized typography
3. **"Organic Flow"** — custom SVG illustrations, flowing shapes, parallax depth layers

---

## Quality Checks

Before writing output, verify:
- [ ] All 3 directions have distinct visual_adjectives (no overlap)
- [ ] hero_headlines are in Russian and reference the brand/activity
- [ ] image_keywords are specific (>= 3 words each)
- [ ] messages.primary clearly states what the business does + for whom
- [ ] tone matches the chosen direction (formal direction != humorous tone)

---

## Token Budget

Expected: 2-4k tokens (input: ~1k canonical spec, output: ~2k brand profile).
