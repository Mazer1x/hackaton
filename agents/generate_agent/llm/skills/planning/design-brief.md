---
name: design-brief
description: Generate a site design concept from JSON and user description — sections with concept, illustration and animation, UI Kit, and motion principles. Works for any style (minimal, corporate, organic, editorial, etc.).
---

# Skill: design brief (site concept)

Use this skill when you need to generate a **design concept** for a site from a JSON brief (brand, business, goals) and the user's description. The result is a structured brief: not just a list of sections, but a **concept per block** with illustration, animation, UI Kit, and general motion principles. The style can be anything: minimal, corporate, organic, editorial, dark, light, playful, etc. — depending on the brand and request.

## Goal

Produce a document that the build can use to create a site with:
- a single visual concept (one metaphor or direction for the project);
- clear illustration and animation directions for each section;
- a UI Kit (colors, typography, buttons, icons, cards);
- an "Animations" section with motion principles.

## Structure of the design brief

### 1. Title and tagline

- **Concept name** — what the site is and the main idea (e.g. "Concept — massage studio", "Programming school landing").
- **Tagline** — 3–5 style keywords (e.g. minimal, warm colors, soft typography; or strict, grid, monochrome).

### 2. Sections by block

For each major page area define:

- **Concept name** — short idea for the section (metaphor or image) linking content to visuals.
- **Copy / CTA**: headline, subheadline, button (text and action).
- **Illustration**: what is shown visually — shapes, illustration style, metaphors, decoration (or none for minimal).
- **Animation**: how it moves and responds to hover/scroll — subtle or bold, in line with the chosen style.

Typical blocks:

- **HERO** — first screen, main message and CTA.
- **NAVIGATION** — look and behavior (fixed/transparent, hover, scroll).
- **Content sections** (SERVICES, ABOUT, TESTIMONIALS, etc.) — for each: concept, copy, illustration, animation.
- **CTA** — final call to action (button shape, emphasis, light effects if needed).

### 3. UI KIT

One block for the whole site:

- **Colors**: primary background, accents, gradients or textures if needed.
- **Typography**: heading and body fonts, character (strict, soft, contrast).
- **Buttons**: shape, shadows, hover.
- **Icons**: style (line, fill, outline), hover behavior.
- **Cards**: background, borders, shadows, micro-animations on scroll/hover.

### 4. Animations (general principles)

Briefly: motion character (smooth / sharp / almost no animation), parallax if needed, easing, effects (e.g. grain, glow, blur when appropriate). For minimal sites this section can be short.

## Output format

Use dividers and subheadings so the brief is easy to pass into the build:

```
# [Concept name] — [site theme]
## (tagline: style keywords)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## HERO — «[CONCEPT NAME]»
[Copy: headline, subheadline, button]

### Illustration
- bullet points

### Animation
- bullet points

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## NAVIGATION — «[CONCEPT]»
- look and behavior

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## SECTION «[NAME]» — «[CONCEPT]»
- cards/blocks if needed
- Illustration / Animation

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## CTA — «[CONCEPT]»
- button, shape, hover

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# UI KIT
## Colors
## Typography
## Buttons
## Icons
## Cards

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Animations
- general motion principles
```

## Rules

1. **Concept per section** — each zone has a short concept name linking content to visuals and motion.
2. **Illustration and animation** — separate: what is visible statically and how it responds to interaction.
3. **UI Kit** — one system for the whole site; buttons, cards, icons aligned with the chosen style.
4. **Style** — derive from the JSON and user description (minimal, corporate, organic, editorial, etc.); do not force a single template.
5. **Rely on JSON** — sections, copy, CTAs from the JSON brief when possible; design decisions from brand context and user preferences.

Use this skill in the design planning phase; the result is a full design brief in this format (the `design_brief` field or text for the next step).
