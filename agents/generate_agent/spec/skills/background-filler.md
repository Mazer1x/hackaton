# Background Filler

Assigns a visually rich, non-empty background to every section of the landing page.
Core principle: a beautiful background is invisible — it supports content without competing with it.

## Input
- `layout_spec` — sections with roles, grids, heights, existing background_layer hints
- `design_tokens` — palette, motion level, bold_design_move
- `typography_spec` — font sizes (for WCAG large-text threshold)
- `brand_profile` — chosen_direction, tone
- `canonical_spec` — preferences (style, animation_level), price_segment, assets

## Output
`background_spec` — per-section background config + dependency flags.

## Background Types

### photo
Full-width image with overlay. Config: `asset_id`, `overlay` (dark_gradient/radial_vignette/color_wash/none), `overlay_opacity`.

### 3d (Three.js)
Particle fields or floating shapes. Config: `variant` (particles/floating_shapes), `density`, `speed`, `palette_keys`, `opacity`.
Requires: `needs_three_js: true`, `needs_react: true`.

### svg (D3/inline)
Animated SVG backgrounds. Config: `variant` (gradient_mesh/wave/noise_field/geometric_grid), `palette_keys`, `opacity`, `animated`, `scale`.
Recommended for most sections — lightweight, beautiful, no heavy JS.

### gradient (CSS only)
Simple CSS gradient. Config: `direction`, `stops` [{color_key, position}], `opacity`.
**RESTRICTION: gradient is ONLY allowed for CTA and footer sections.** All other sections must use photo, 3d, svg, or video.

### video
Background video loop. Config: `asset_id`, `loop`, `muted`, `overlay`, `overlay_opacity`.

## Decision Heuristics

| Brand Style | Hero BG | Content Sections | CTA |
|-------------|---------|-----------------|-----|
| Dark / tech / cyberpunk | 3d (particles) | svg (noise_field) or 3d (floating_shapes) | gradient |
| Premium / luxury / editorial | svg (gradient_mesh) or photo | svg (wave) or photo | gradient |
| Warm / friendly / accessible | svg (geometric_grid) or photo | svg (wave) or gradient_mesh | gradient |
| Minimal / clean | svg (gradient_mesh) | svg (noise_field) or photo | gradient |
| Creative / experimental | 3d (floating_shapes) | svg (any) or photo | gradient |

## Mandatory Rules

1. **No empty backgrounds** — every section must have a non-white, non-trivial background
2. **Variety** — at least 2 different non-gradient types across the page
3. **gradient restriction** — gradient ONLY for CTA and footer; all other sections need richer types
4. **Adjacent contrast** — adjacent sections must NOT have identical background types
5. **Animated backgrounds** — if `motion.level` is "medium" or "max", at least 1 section must have an animated background (3d or animated svg)
6. **Content readability** — verify text-over-background contrast using the check_contrast_ratio tool
7. **prefers-reduced-motion** — all animated backgrounds must respect the media query
8. **z-index layering** — background at z-index: 0, content at z-index: 1 or higher
9. **Bold design move** — if the bold_design_move relates to backgrounds (e.g., "parallax depth layers"), implement it in the appropriate section
10. **Performance** — 3D backgrounds only when `animation_level` is "medium" or "max"

## Post-Validation

If the LLM output has >50% gradient backgrounds, reject and retry with:
"Too many gradient backgrounds. gradient is only allowed for CTA/footer. Use svg, 3d, or photo for other sections."

### System Prompt

```
You are a background strategist ensuring every section has a visually rich background.

Available types: photo, 3d, svg, gradient, video.
CRITICAL: gradient is ONLY for CTA/footer sections. All others need photo, 3d, svg, or video.

Brand: {chosen_direction.name} — {chosen_direction.concept}
Style: {style_hint}
Animation level: {animation_level}
Motion level: {motion_level}
Price segment: {price_segment}
Bold design move: {bold_design_move}
Typography hero size: {hero_font_size}

Sections:
{sections_summary}

Palette: {palette_json}

Rules:
- ≥2 different non-gradient types
- ≥1 animated bg if motion ≥ medium
- Adjacent sections: different bg types
- Use the contrast tool to verify text readability
- gradient ONLY for CTA and footer

Output dependencies: needs_three_js, needs_d3, needs_react booleans.
```
