# Conversion UX Heuristics

Reference knowledge for Brand Synthesizer, Layout Dramaturgy, and QA Critic.
Focused on Russian-language landing pages for service businesses.

---

## CTA Placement

### Above the Fold (Critical)
- Primary CTA must be visible without scrolling on desktop (within first 100vh)
- Hero CTA: large, high-contrast, with action verb ("Получить расчёт", "Записаться", "Заказать")
- Secondary CTA can be subtle (text link, ghost button)

### After Social Proof
- Place CTA immediately after testimonials or case studies
- User just read trust signals -> highest conversion moment
- Repeat the same CTA (not a different one)

### Sticky on Mobile
- On mobile viewport: sticky bottom CTA bar (56px height)
- Appears after user scrolls past hero CTA
- Phone/WhatsApp icon + short label

### End of Page
- Always a CTA section before footer
- "Остались вопросы?" or "Готовы начать?" pattern
- Phone number + messenger links as alternative to form

---

## CTA Design Rules

### Button Copy (Russian Market)
- Use action verbs: "Получить", "Записаться", "Заказать", "Узнать", "Рассчитать"
- Add urgency sparingly: "Получить расчёт бесплатно"
- Avoid generic: "Отправить", "Подробнее", "Далее"
- Keep under 4 words

### Button Styling
- Primary CTA: accent color background, white text, largest button on page
- Minimum touch target: 48x48px (mobile), 44x44px (desktop)
- Padding: horizontal >= 2x vertical (pill shape preferred)
- Hover: darken 10% or slight scale(1.02)

---

## Contact Channel Priority by Goal

| Site Goal | Primary Channel | Secondary Channel |
|-----------|----------------|-------------------|
| Продажи (sales) | Phone / WhatsApp | Telegram |
| Заявки (leads) | Form | Phone |
| Доверие (trust) | Phone | Form |
| Презентация (presentation) | Form / Telegram | Phone |

### Russian Market Specifics
- WhatsApp > Telegram for 35+ audience
- Telegram > WhatsApp for tech/young audience
- Phone is still #1 trust signal for services
- Forms: max 3 fields (name, phone, optional message)
- Show phone number in header (not just in CTA)

---

## Trust Signals

### Placement Rules
- Reviews: place near CTA (within 1 scroll of CTA button)
- Certificates/awards: near pricing or offer section
- Team photos: build rapport, place after features
- Case studies: strongest trust signal, place before final CTA
- "Работаем с YEAR года" — great for header or hero subtitle

### Social Proof Formatting
- Real names + photos > anonymous quotes
- Specific results > vague praise ("Увеличили продажи на 40%" > "Отличная работа")
- Video testimonials > text (but text is fine for MVP)
- Show count: "Более 500 клиентов" (but only if true)

---

## Form Design

### Fields
- Minimum: Name + Phone (2 fields)
- Standard: Name + Phone + Message (3 fields)
- Maximum: Never more than 5 fields on a landing page
- Pre-fill country code (+7 for Russia)

### UX
- Large input fields (48px height minimum)
- Clear labels (above field, not placeholder-only)
- Success state: "Спасибо! Мы свяжемся с вами в течение 15 минут"
- Error state: inline, red border, clear message

### Lead Capture Form Patterns

**Inline Form (preferred for site_goal: "leads")**:
- Placed directly in the CTA section, always visible
- 2-3 fields max: name + phone + optional message
- Large submit button (full-width on mobile)
- For `site_goal: "leads"` a visible form is MANDATORY, not just a button

**Modal Form**:
- Triggered by CTA button click
- Use when the page is visually dense and a form would break flow
- Keep under 3 fields, auto-focus first field on open
- Close on backdrop click + Escape key

**Multi-Step Form**:
- Split into 2-3 steps for complex services (e.g., "Тип услуги" → "Контакты")
- Progress indicator at top
- Only use when >3 data points are genuinely needed

### Multi-Channel CTA Layout
When multiple contact channels are available (phone, WhatsApp, Telegram, form):
- Display as a grid (2x2 on mobile, 1x4 on desktop)
- Each channel as a card: icon + label + hover state
- WhatsApp: green hover (#25D366)
- Telegram: blue hover (#229ED9)
- Phone: brand primary color hover
- Form: opens inline or modal

---

## Page Structure for Conversion

### Optimal Section Order (by goal)
**Sales ("Продажи")**:
Hero (offer + CTA) -> Features/Benefits -> Social Proof -> Cases -> CTA -> FAQ -> Footer

**Leads ("Заявки")**:
Hero (problem + CTA) -> Solution/Features -> Social Proof -> Form Section -> FAQ -> Footer

**Trust ("Доверие")**:
Hero (brand story) -> Team -> Cases -> Achievements -> Reviews -> Contacts -> Footer

**Presentation ("Презентация")**:
Hero (visual wow) -> About -> Services/Features -> Cases -> Team -> Contacts -> Footer

---

## Microcopy Patterns (Russian)

### Hero Subtitles
- Problem-agitate: "Устали от [проблема]? Мы решаем это за [срок]"
- Direct offer: "[Услуга] для [аудитория] в [гео]"
- Result-focused: "Увеличьте [метрика] с помощью [решение]"

### Section Headings
- Avoid generic: "Наши услуги", "О нас", "Почему мы"
- Better: specific, benefit-driven: "Как мы увеличиваем продажи", "Команда, которой доверяют 500+ клиентов"

### Footer Legal (RKN)
- Required for Russian sites: ИНН, ОГРН (for ИП/ООО)
- Format: "ИП Иванов И.И. ИНН 123456789012 ОГРНИП 123456789012345"
- Place at very bottom in small/muted text
