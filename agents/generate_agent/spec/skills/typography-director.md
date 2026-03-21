---
name: typography-director
description: |
  Select font pairing, define type scale, tracking, and Tailwind mapping.
  Queries Google Fonts metadata via context7 MCP.

  Use when: the landing-generator orchestrator calls this skill at Step 3b.
---

# Typography Director

Selects font pairing and defines the complete typographic scale system.
Treats typography as the primary vehicle for brand personality.

---

## Input

Read:
- `generator/output/brand_profile.json` (chosen_direction, tone)
- `generator/output/design_tokens.json` (palette, spacing for context)
- `generator/output/canonical_spec.json` (for `price_segment`, `preferences.typography_density`)

---

## Process

### MCP Usage

Query `context7` MCP for Google Fonts information:
1. `resolve-library-id` with "google-fonts"
2. `query-docs` for "popular font pairings" or specific font families

If context7 doesn't have Google Fonts data, use built-in knowledge of these reliable pairings:

**Grotesk / Modern:**
- Space Grotesk + Inter
- DM Sans + DM Serif Display
- Outfit + Source Serif 4

**Editorial / Luxury:**
- Playfair Display + Lato
- Cormorant Garamond + Montserrat
- Instrument Serif + Inter

**Technical / Clean:**
- JetBrains Mono + Inter
- IBM Plex Sans + IBM Plex Serif
- Fira Code + Fira Sans

**Friendly / Approachable:**
- Nunito + Merriweather
- Rubik + Lora
- Manrope + Crimson Pro

### System Prompt

```
You are a typography director. Typography is the foundation of visual identity.

Given brand profile and design tokens, select a font pairing and define the complete type scale.

Rules:
- Use clamp() for hero and h1-h2 for fluid responsive sizing
- Hero size should be dramatically larger than h1 (this creates hierarchy drama)
- Tracking (letter-spacing): tighter for large text, wider for small/caption
- Line height: tighter for headlines (0.9-1.1), looser for body (1.5-1.7)
- Primary font: for display/headlines — personality-defining
- Secondary font: for body text — optimized for readability
- Include fallback fonts in tailwind_mapping
- font_import_urls: use Google Fonts CSS2 API with display=swap
- If boldness is "high": consider variable fonts for dramatic weight variation
- If typography_density is "minimal": slightly larger body text (1.125rem)
- caption should use primary font with uppercase + wide tracking (micro-text contrast)
```

### User Prompt

```
Creative direction: {brand_profile.chosen_direction as JSON}
Tone: {brand_profile.tone as JSON}
Bold design move: {design_tokens.bold_design_move}
Price segment: {canonical_spec.price_segment}
Typography density: {canonical_spec.preferences.typography_density}

Select font pairing and define type scale.
```

---

## Output

Write to `generator/output/typography_spec.json`.

Must conform to `generator/contracts/typography_spec.schema.json`.

---

## Quality Checks

- [ ] Both fonts are available on Google Fonts (or are system fonts)
- [ ] Primary and secondary fonts have sufficient contrast (not two grotesk sans-serifs)
- [ ] Hero size uses clamp() with vw unit for fluid scaling
- [ ] Body text line_height >= 1.5 (readability)
- [ ] All specified weights are available for the chosen fonts
- [ ] font_import_urls are valid Google Fonts CSS2 URLs

---

## Token Budget

Expected: 1-2k tokens.
