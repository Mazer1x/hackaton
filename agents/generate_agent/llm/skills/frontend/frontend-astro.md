---
name: frontend-astro
description: Astro + Tailwind v4 frontend implementation: file structure, custom.css rules, layout order, components. Use when writing or reviewing Astro/Tailwind code so the build succeeds and styles apply correctly.
---

# Skill: frontend (Astro + Tailwind v4)

Use this skill when **implementing** or reviewing frontend code in this project. Stack: Astro, Tailwind v4, plain CSS for custom styles. Goal: build succeeds on first try, styles load in the right order, no broken pages.

## Project structure

- **Site root**: `site/` (or configured project path).
- **Entry**: `src/pages/index.astro` — main page; imports layout and components.
- **Layout**: `src/layouts/BaseLayout.astro` — wraps all pages; must import styles in the correct order.
- **Components**: `src/components/*.astro` — one component per file (Hero.astro, About.astro, etc.), not inline in index.
- **Styles**: `src/styles/global.css` (Tailwind), `src/styles/custom.css` (custom CSS only).

## Style import order (critical)

In the layout (e.g. BaseLayout.astro), import in this order:

1. **global.css** — Tailwind base and utilities. If this is missing, Tailwind classes do nothing.
2. **custom.css** — custom variables, @keyframes, and classes.

Example in frontmatter:

```astro
---
import '../styles/global.css';
import '../styles/custom.css';
---
```

Wrong: only custom.css, or custom before global — layout will look broken.

## custom.css — plain CSS only

- **Do not use `@apply`** in custom.css. Tailwind v4 does not resolve `@apply` in separate CSS files; the build can fail or classes won't work.
- **Use** in custom.css:
  - `:root { ... }` for variables (colors, spacing).
  - `@keyframes name { ... }` for animations.
  - Plain class definitions (e.g. `.floating { animation: float 6s ease-in-out infinite; }`).
- **Use** in .astro files: Tailwind utility classes in the HTML (e.g. `class="bg-slate-900 text-amber-50 px-8 py-4"`).

## Components and pages

- **Import components** in the page or layout: `import Hero from '../components/Hero.astro';`
- **Use in template**: `<Hero />`, `<About />`, etc.
- **One component per file** — do not put multiple section components in a single file or inline in index.astro.
- **BaseLayout** should wrap the whole page; index.astro typically does `<BaseLayout><Hero /><About />...</BaseLayout>`.

## Tailwind usage

- Use real Tailwind v4 utility names: `bg-slate-900`, `text-amber-50`, `rounded-lg`, `hover:bg-amber-600`. Avoid made-up classes like `bg-cream` unless defined in custom.css.
- Prefer Tailwind for layout and spacing; use custom.css for brand-specific animations and variables.

## Checklist before "done"

- [ ] Layout imports global.css first, then custom.css.
- [ ] custom.css has no `@apply`.
- [ ] All sections are separate .astro components; index.astro only imports and composes them.
- [ ] Tailwind classes used in HTML are valid (no unknown classes).
- [ ] One clear CTA and structure that matches the design brief / project_spec.

Use this skill in the execute phase (and when loading context for execution) so generated code fits this stack and builds correctly.
