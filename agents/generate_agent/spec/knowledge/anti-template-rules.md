# Anti-Template Rules

Pattern avoidance system to prevent generic-looking output.
Referenced by Layout Dramaturgy and QA Critic skills.

---

## Known Template Patterns to Avoid

### The "Webflow Default"
```
NAV -> HERO (centered) -> 3 equal feature cards -> logo strip -> testimonials -> CTA -> FOOTER
```
This is the most common AI-generated layout. Detection: 3+ equal-column sections, all centered text, uniform spacing.

### The "SaaS Landing"
```
NAV -> HERO (split 50-50) -> features alternating left-right -> pricing table -> FAQ -> FOOTER
```
Detection: alternating split sections, pricing grid, accordion FAQ as second-to-last section.

### The "Agency Portfolio"
```
NAV -> fullscreen video HERO -> project grid (equal) -> about section -> contact form -> FOOTER
```
Detection: fullscreen hero + equal grid immediately after.

### The "Bootstrap Corporate"
```
NAV -> HERO with carousel -> icon+text features in 4 columns -> "Why Choose Us" -> team grid -> FOOTER
```
Detection: carousel in hero, 4-column icon grid, "Why Choose Us" heading.

### The "Minimal SaaS"
```
NAV -> HERO (centered headline + screenshot) -> 3 feature blocks -> integrations logo strip -> pricing -> FOOTER
```
Detection: centered screenshot hero, 3 equal feature sections, logo strip, pricing grid.

### The "Generic Service Business"
```
NAV -> HERO (stock photo bg + centered text) -> "О нас" -> services grid (equal-3 or equal-4) -> reviews -> contacts -> FOOTER
```
Detection: stock photo hero with overlay, "О нас" as second section, equal services grid, reviews before contacts.

---

## Pattern Fingerprinting

To detect similarity, hash these features of a layout:
1. Section sequence (ordered list of section types)
2. Grid types per section
3. Content alignment pattern (left/center/right sequence)
4. Spacing rhythm pattern (relative: small/medium/large)

**Hash algorithm**: `SHA256(section_types.join('-') + grid_types.join('-') + alignments.join('-'))`

Compare against `memory/patterns.json`. If similarity > 0.5 (Jaccard index on section+grid bigrams), trigger mutation.

---

## Mutation Strategies

When a layout is too similar to known patterns, apply one or more mutations:

### 1. Section Fusion
Merge two related sections into one with dual content.
- Features + Social Proof -> features with inline testimonial quotes
- Hero + About -> hero that IS the about section (personal story hero)

### 2. Grid Offset
Replace an equal grid with an asymmetric one.
- `equal-3` features -> one large featured item + 2 smaller ones (2/3 + 1/3 split)
- `equal-4` team -> 1 highlighted member (large) + 3 standard

### 3. Unexpected Negative Space
Insert a "breathing" section — no content, just a visual divider or massive whitespace.
- Full-width color block with single quote
- Parallax image strip between sections

### 4. Scale Inversion
Make one element dramatically larger or smaller than expected.
- Tiny navigation text with oversized hero headline
- Massive section number ("01") as decorative element

### 5. Order Disruption
Move a section to an unexpected position.
- Testimonial before features (trust first, then explain)
- CTA between hero and features (immediate conversion option)

### 6. Full-Bleed Interruption
Insert one full-bleed image or color section to break the container rhythm.

---

## Minimum Layout Entropy Threshold

A layout must score >= 5 on this entropy checklist (each item = 1 point):

- [ ] At least 2 asymmetric grid sections (60-40, 40-60, or asymmetric)
- [ ] At least 3 different spacing values between sections
- [ ] At least 2 sections with non-centered primary content
- [ ] At least 1 bold design move applied (★ section)
- [ ] Section order does NOT match any known template pattern above
- [ ] At least 1 section uses a grid type different from all others
- [ ] At least 1 full-bleed section (100vh or edge-to-edge)
- [ ] Adjacent sections do NOT share the same grid type

If score < 5: the Layout Dramaturgy skill MUST apply mutations until threshold is met.

---

## Memory File Format (`memory/patterns.json`)

```json
{
  "generated": [
    {
      "session_id": "uuid",
      "timestamp": "ISO-8601",
      "pattern_hash": "sha256",
      "section_sequence": ["nav", "hero", "features", "testimonials", "cta", "footer"],
      "grid_types": ["auto", "60-40", "equal-3", "full-width", "full-width", "40-30-30"],
      "brand_name": "Example Corp"
    }
  ]
}
```
