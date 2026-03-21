# Animation Director

Defines a complete animation choreography for the page: scroll-triggered entrances, hover micro-interactions, parallax layers, staggered children, and reduced-motion fallbacks.

## Input
- `layout_spec` — sections with roles, animation_hints, bold_move_applied
- `components_catalog` — component structure per section (elements, buttons, cards)
- `design_tokens` — motion.level (none/subtle/medium/max), duration_fast/normal/slow, easing
- `background_spec` — which sections have animated backgrounds (3D, SVG)

## Output
`animation_spec` — per-section animation directives with CSS/JS implementation.

## Animation Types

### 1. Scroll Entrance
Element appears when scrolled into viewport (IntersectionObserver).

| Type | CSS | When to use |
|------|-----|-------------|
| fade-up | `opacity:0; transform:translateY(30px)` → `opacity:1; transform:none` | Default for most content |
| fade-in | `opacity:0` → `opacity:1` | Subtle, for images and backgrounds |
| slide-left | `transform:translateX(-40px); opacity:0` → `none` | Asymmetric layouts, left-side content |
| slide-right | `transform:translateX(40px); opacity:0` → `none` | Right-side content in split layouts |
| scale-up | `transform:scale(0.9); opacity:0` → `none` | Cards, featured elements |
| clip-reveal | `clip-path:inset(0 100% 0 0)` → `clip-path:inset(0)` | Headlines, dramatic reveals |

### 2. Children Stagger
Children of a container enter one by one.

```css
[data-stagger] > * {
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 0.5s ease, transform 0.5s ease;
}
[data-stagger].visible > *:nth-child(1) { transition-delay: 0s; }
[data-stagger].visible > *:nth-child(2) { transition-delay: 0.1s; }
[data-stagger].visible > *:nth-child(3) { transition-delay: 0.2s; }
/* ... */
[data-stagger].visible > * { opacity: 1; transform: none; }
```

### 3. Hover Micro-Interactions

| Element | Transform | Transition |
|---------|-----------|------------|
| Button (primary) | `scale(1.03)` | `0.2s ease` |
| Button (secondary) | `translateY(-2px)` | `0.2s ease` |
| Card | `translateY(-4px); box-shadow: 0 20px 60px rgba(0,0,0,0.1)` | `0.3s ease` |
| Link | underline width `0%` → `100%` via `background-size` | `0.3s ease` |
| Image | `scale(1.05)` (inside `overflow:hidden` container) | `0.4s ease` |
| Nav link | `color: var(--color-accent)` | `0.2s ease` |

### 4. Parallax
Background or decorative elements scroll at different speed.

```css
.parallax-element {
  will-change: transform;
  /* JS sets translateY based on scroll position */
}
```
Speed values: `0.1` (barely moves) to `0.5` (half scroll speed).
Only apply to decorative elements, never to readable text.

### 5. Scroll Progress
CSS property changes based on scroll position within a section.

```css
.progress-bar {
  transform: scaleX(var(--scroll-progress, 0));
  transform-origin: left;
}
```

## Motion Level Mapping

| Token Level | Entrances | Stagger | Hover | Parallax | Notes |
|-------------|-----------|---------|-------|----------|-------|
| none | No | No | Static states only | No | `prefers-reduced-motion: reduce` |
| subtle | fade-in only | No | Yes (subtle) | No | Minimal distraction |
| medium | fade-up, slide | Yes (0.1s delay) | Yes | Decorative only | Good balance |
| max | All types incl. clip-reveal | Yes (0.15s delay) | Yes (dramatic) | Yes | Full choreography |

## Reduced Motion Strategy

Always wrap animations in a `prefers-reduced-motion` check:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

For JS-driven animations, check: `window.matchMedia('(prefers-reduced-motion: reduce)').matches`

## Scroll Observer Setup (goes in Layout.astro or global script)

```js
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.15, rootMargin: '0px 0px -50px 0px' });

document.querySelectorAll('[data-scroll]').forEach(el => observer.observe(el));
```

## Prompt

```
You are an animation director creating scroll choreography for a landing page.
Motion level: {motion_level}
Bold design move: {bold_design_move}

Rules:
- Respect the motion level: if "subtle", only use fade-in
- The hero section should have the most dramatic entrance
- CTA sections: keep animations minimal (don't distract from conversion)
- Stagger delay: 0.1s for medium, 0.15s for max
- Total animation time for a section should not exceed 1.2s
- Always include prefers-reduced-motion fallback
```
