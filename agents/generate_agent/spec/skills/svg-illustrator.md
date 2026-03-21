# SVG Illustrator

Generates thematic inline SVG illustrations that match the brand identity.
Produces 3-6 illustrations per site: hero decorations, section dividers, feature icons, testimonial quote marks, CTA ornaments.

## Input
- `canonical_spec` — business type, activity, audience
- `brand_profile` — chosen_direction, tone, visual_adjectives
- `design_tokens` — palette (primary, secondary, accent), bold_design_move
- `layout_spec` — sections with roles and element references
- `asset_manifest` — existing icons (to avoid duplicates)

## Output
Enriched `asset_manifest.icons[]` with `source: "generated"` entries.

## SVG Requirements

1. **viewBox only** — no fixed width/height (responsive by default)
2. **currentColor** — use `currentColor` for primary strokes/fills so CSS can override
3. **CSS variables** — reference `var(--color-primary)`, `var(--color-accent)` for multi-color SVGs
4. **Lightweight** — each SVG under 2KB, no embedded raster images
5. **Accessible** — include `role="img"` and `aria-label` on the SVG element
6. **No external dependencies** — pure SVG, no JavaScript

## Style Categories

### Decorative
Large background ornaments, partially visible, low opacity.
Used as: hero background element, section accent.
Example: abstract wave, organic blob, geometric pattern.

### Functional
Icons that communicate meaning: feature icons, CTA channel icons, navigation icons.
Used as: feature grid icons, contact method icons.
Consistent stroke width and visual weight across the set.

### Ornamental
Small accent elements: quote marks, section dividers, bullet replacements.
Used as: testimonial quotes, list markers, horizontal rules.

## Prompt

```
You are an SVG illustrator creating thematic inline SVG illustrations for a {business_type} brand.

Brand direction: {chosen_direction.name} — {chosen_direction.concept}
Visual adjectives: {chosen_direction.visual_adjectives}
Tone: {tone.voice}, {tone.formality}
Palette: primary={primary_hex}, secondary={secondary_hex}, accent={accent_hex}

Create {N} SVG illustrations for these roles:
{roles_list}

Rules:
- Output ONLY SVG code per illustration, no wrapper HTML
- Use viewBox, NO fixed width/height
- Use currentColor for primary color, var(--color-accent) for secondary
- Keep each SVG under 50 lines and 2KB
- Match the brand's visual adjectives in your illustration style
- For {business_type}: use thematically relevant shapes (e.g., wheat/bread for bakery, sound waves for nightclub)
- NO text inside SVGs (text is handled by HTML)
- Smooth curves (cubic bezier) over sharp angles for organic brands
- Geometric precision for tech/corporate brands
```

## Example SVGs

### Decorative blob (organic brand)
```svg
<svg viewBox="0 0 200 200" role="img" aria-label="Decorative shape">
  <path fill="currentColor" opacity="0.08"
    d="M45,-62C57,-52 65,-37 68,-21C71,-5 69,12 61,26C53,40 39,52 23,58C7,64 -11,65 -27,59C-43,53 -57,41 -64,26C-71,11 -71,-7 -64,-23C-57,-39 -43,-53 -28,-61C-13,-69 3,-72 18,-69C33,-66 33,-72 45,-62Z"
    transform="translate(100 100)"/>
</svg>
```

### Feature icon (minimal line style)
```svg
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" role="img" aria-label="Quality icon">
  <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
</svg>
```

### Quote mark (ornamental)
```svg
<svg viewBox="0 0 40 32" role="img" aria-label="Quote mark">
  <path fill="var(--color-accent)" opacity="0.2"
    d="M0 32V19.2C0 6.4 8.8 0 17.6 0v6.4C12 6.4 8.8 10.4 8 16h9.6v16H0zm22.4 0V19.2C22.4 6.4 31.2 0 40 0v6.4c-5.6 0-8.8 4-9.6 9.6H40v16H22.4z"/>
</svg>
```
