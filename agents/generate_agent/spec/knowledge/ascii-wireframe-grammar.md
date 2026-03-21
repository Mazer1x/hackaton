# ASCII Wireframe Grammar

Strict format specification for layout wireframes produced by the Layout Dramaturgy skill.
The Code Generator never reads ASCII directly — it reads the parsed `layout_spec.json`.
ASCII is the intermediate reasoning layer that forces spatial thinking.

---

## Symbol Legend

| Symbol | Meaning | Example |
|--------|---------|---------|
| `+--[LABEL]--+` | Section boundary with name | `+--[HERO]--+` |
| `\|          \|` | Section content boundary | Vertical walls of a section |
| `[Button Text]` | Interactive element (button, link) | `[Get a Quote]` |
| `"text"` | Display text (headline, subtitle) | `"Transform Your Business"` |
| `IMG[ratio]` | Image placeholder with aspect ratio | `IMG[16:9]`, `IMG[1:1]`, `IMG[4:5]` |
| `ICON[name]` | Icon placeholder | `ICON[arrow-right]`, `ICON[phone]` |
| `---NNpx---` | Explicit vertical spacing | `---80px---` |
| `<-NNpx` | Horizontal margin/padding annotation | `<-24px` |
| `^NNpx` | Vertical gap annotation (arrow up) | `^16px` |
| `{grid: N-N}` | Grid split ratio | `{grid: 60-40}`, `{grid: equal-3}` |
| `{h: value}` | Height hint | `{h: 100vh}`, `{h: auto}` |
| `(scroll)` | Scroll behavior | `(horizontal-scroll)`, `(sticky)` |
| `[===]` | Horizontal rule / divider | |
| `...` | Repeated elements | `[Card] [Card] [Card]` or `[Card] x3` |

---

## Section Structure

Every section follows this pattern:

```
+--[SECTION_NAME]--+ {grid: TYPE} {h: HEIGHT}
|                                              |
|  content layout here                         |
|                                              |
+----------------------------------------------+
              ---SPACING_px---
```

---

## Grid Types

- `full-width` — single column, edge to edge
- `60-40` — asymmetric split (content left, media right)
- `40-60` — asymmetric split (media left, content right)
- `50-50` — equal split
- `equal-2`, `equal-3`, `equal-4` — equal columns
- `asymmetric` — custom, describe in content
- `auto` — browser default flow

---

## Full Page Example

```
+--[NAV]--+ {grid: auto} {h: 64px} (sticky)
|  LOGO          link  link  link     [CTA Button]  |
+---------------------------------------------------+

+--[HERO]--+ {grid: 60-40} {h: 100vh}
|                                                    |
|  "Transform Your Business"                         |
|   subtitle: value proposition text     IMG[16:9]   |
|                                                    |
|   [Get Started]  [Learn More]                      |
|                                     <-24px         |
+---------------------------------------------------+
                    ---80px---

+--[FEATURES]--+ {grid: equal-3} {h: auto}
|                                                    |
|  ICON[zap]         ICON[shield]      ICON[clock]   |
|  "Feature 1"      "Feature 2"       "Feature 3"   |
|   description       description       description  |
|                                                    |
+---------------------------------------------------+
                    ---120px---

+--[SOCIAL_PROOF]--+ {grid: full-width} {h: auto}
|                                                    |
|  "What Our Clients Say"                            |
|                                                    |
|  [CARD: "quote" — Author]  (horizontal-scroll)    |
|  [CARD: "quote" — Author]                          |
|  [CARD: "quote" — Author]                          |
|                                                    |
+---------------------------------------------------+
                    ---100px---

+--[CTA]--+ {grid: full-width} {h: auto}
|                                                    |
|           "Ready to Start?"                        |
|            subtitle text                           |
|           [Primary CTA Button]                     |
|                                                    |
+---------------------------------------------------+
                    ---60px---

+--[FOOTER]--+ {grid: 40-30-30} {h: auto}
|                                                    |
|  LOGO              Links          Contacts         |
|  legal text        link           ICON[phone]      |
|  RKN data          link           ICON[telegram]   |
|                                                    |
+---------------------------------------------------+
```

---

## Parsing Rules (ASCII -> layout_spec JSON)

1. Each `+--[NAME]--+` block becomes a `sections[]` entry with `id` = lowercase(NAME)
2. `{grid: X}` -> `section.grid = X`
3. `{h: X}` -> `section.height = X`
4. `(sticky)` -> `section.sticky = true`
5. `"text"` elements -> added to `section.elements[]` as headline/subtitle
6. `[Button Text]` -> added as cta element
7. `IMG[ratio]` -> `section.image_ratio = ratio`, added to elements
8. `ICON[name]` -> recorded for component catalog
9. `---NNpx---` -> `section.spacing_after = "NNpx"` on the section above
10. `<-NNpx` -> recorded as margin annotation for component catalog
11. `x3` or repeated elements -> count recorded in elements array
12. `(horizontal-scroll)` -> `section.animation_hint = "horizontal-scroll"`

---

## Quality Rules

- Every wireframe MUST have at least one asymmetric grid (anti-template)
- NAV and FOOTER are required
- At least one section must be marked with bold_move_applied annotation: `★`
- Spacing between sections should vary (not all 80px — use rhythm)
- Hero section should be first content section, always
- CTA section should appear at least once after credibility content
- Use `★` prefix on the section that implements the bold design move: `+--[★ HERO]--+`

---

## Background Layer Notation

Background elements are annotated per-section using the `BG[type]` symbol.
The background-filler agent uses these hints to decide the final background implementation.

### Symbols

| Symbol | Meaning | Example |
|--------|---------|---------|
| `BG[type]` | Background type for this section | `BG[particles]`, `BG[gradient:primary->accent]` |
| `BG[photo:id]` | Photo background from asset manifest | `BG[photo:hero_img]` |
| `BG[overlay:type]` | Overlay on top of background | `BG[overlay:dark_gradient]` |
| `{opacity: N}` | Background opacity | `{opacity: 0.4}` |

### Layer-Separated ASCII (Optional)

When generating multi-layer wireframes, separate layers with the `~~ layer: name ~~` marker:

```
~~ layer: background ~~
+--[HERO]--+ {h: 100vh}
|  BG[3d:particles] {opacity: 0.4}                    |
|  BG[overlay:radial_vignette]                         |
+----------------------------------------------------------+

~~ layer: content ~~
+--[HERO]--+ {grid: 60-40} {h: 100vh}
|  "Transform Your Business"              IMG[16:9]    |
|  subtitle                                            |
|  [Get Started]                                       |
+----------------------------------------------------------+
```

### Background Selection Guidelines

- Hero: most dramatic — 3d or video for dark brands, photo for others
- Feature/reveal: lighter — svg or gradient
- CTA/conversion: minimal — gradient or solid (don't distract)
- Every section MUST have a BG annotation (no empty backgrounds)

---

## Responsive Annotations (Optional)

Add mobile variant as a comment below the section:

```
+--[HERO]--+ {grid: 60-40} {h: 100vh}
|  "Headline"                   IMG[16:9]  |
|  [CTA]                                   |
+------------------------------------------+
// mobile: {grid: full-width} stack: IMG on top, text below
```

---

## Anti-Patterns (DO NOT generate)

- All sections with `{grid: full-width}` (no layout variety)
- Equal spacing between all sections (no rhythm)
- Hero -> 3 equal cards -> testimonials -> CTA -> footer (the "Webflow" layout)
- No bold move section marked with `★`
- All text centered (boring)
- No asymmetric grids at all
