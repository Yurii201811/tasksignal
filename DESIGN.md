# TaskSignal Design System

TaskSignal uses a restrained product UI system.

Tokens:

- Background: cool tinted near-white.
- Surface: tinted white panels.
- Text: deep ink.
- Muted text: cool slate.
- Accent: restrained teal for primary actions and selected states.
- Warning/accent secondary: amber for scoring and attention states.
- Borders: cool slate hairlines.

Typography:

- System sans stack.
- Fixed product scale.
- Dense labels and readable prose.

Layout:

- Left navigation on desktop.
- Single-column mobile flow.
- Data tables for ranked opportunities.
- Cards only for bounded summaries, repeated evidence items, and focused panels.
- No nested cards.

Interaction:

- Primary actions use teal.
- Secondary actions use bordered neutral buttons.
- Loading states must be visible for async processing.
- Focus states must remain visible.

## Exports

Generated from the locked TaskSignal system on 2026-07-10. The root
`tokens.css` file is the repository export entry point; runtime definitions live
in `apps/web/src/app/tokens.css` so local, Vercel, and Docker builds share one
canonical implementation.

### CSS custom properties

```css
:root {
  --color-paper: oklch(97% 0.007 255);
  --color-paper-2: oklch(99% 0.004 255);
  --color-paper-3: oklch(95.8% 0.01 255);
  --color-ink: oklch(25% 0.037 258);
  --color-ink-2: oklch(34% 0.032 258);
  --color-muted: oklch(45% 0.035 255);
  --color-neutral: oklch(38% 0.032 255);
  --color-rule: oklch(88.5% 0.017 255);
  --color-rule-2: oklch(66% 0.025 255);
  --color-accent: oklch(50.5% 0.091 183);
  --color-accent-hover: oklch(44.5% 0.083 183);
  --color-accent-soft: oklch(94.5% 0.025 183);
  --color-accent-ink: oklch(98.8% 0.004 255);
  --color-focus: oklch(40% 0.14 250);
  --color-attention: oklch(55% 0.145 55);
  --font-body:
    ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI",
    sans-serif;
  --font-display: var(--font-body);
  --font-outlier:
    ui-monospace, "SFMono-Regular", Menlo, Monaco, Consolas, monospace;
  --text-xs: 0.75rem;
  --text-sm: 0.875rem;
  --text-base: 1rem;
  --text-md: 1.125rem;
  --text-lg: 1.25rem;
  --text-xl: 1.5rem;
  --text-2xl: 1.875rem;
  --text-display: 2.25rem;
  --space-3xs: 0.25rem;
  --space-2xs: 0.5rem;
  --space-xs: 0.75rem;
  --space-sm: 1rem;
  --space-md: 1.5rem;
  --space-lg: 2rem;
  --space-xl: 2.5rem;
  --space-2xl: 4rem;
  --space-3xl: 6rem;
  --rule-hair: 1px;
  --rule-fine: 2px;
  --radius-card: 0.5rem;
  --radius-input: 0.5rem;
  --radius-pill: 999px;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in: cubic-bezier(0.7, 0, 0.84, 0);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --dur-micro: 120ms;
  --dur-short: 200ms;
  --dur-long: 300ms;
}
```

### Tailwind v4 `@theme`

```css
@theme {
  --color-paper: oklch(97% 0.007 255);
  --color-paper-2: oklch(99% 0.004 255);
  --color-paper-3: oklch(95.8% 0.01 255);
  --color-ink: oklch(25% 0.037 258);
  --color-ink-2: oklch(34% 0.032 258);
  --color-muted: oklch(45% 0.035 255);
  --color-neutral: oklch(38% 0.032 255);
  --color-rule: oklch(88.5% 0.017 255);
  --color-rule-2: oklch(66% 0.025 255);
  --color-accent: oklch(50.5% 0.091 183);
  --color-focus: oklch(40% 0.14 250);
  --font-display: ui-sans-serif, system-ui, sans-serif;
  --font-body: ui-sans-serif, system-ui, sans-serif;
  --font-outlier: ui-monospace, "SFMono-Regular", Menlo, monospace;
  --spacing-3xs: 0.25rem;
  --spacing-2xs: 0.5rem;
  --spacing-xs: 0.75rem;
  --spacing-sm: 1rem;
  --spacing-md: 1.5rem;
  --spacing-lg: 2rem;
  --spacing-xl: 2.5rem;
  --spacing-2xl: 4rem;
  --text-xs: 0.75rem;
  --text-sm: 0.875rem;
  --text-base: 1rem;
  --text-md: 1.125rem;
  --text-lg: 1.25rem;
  --text-xl: 1.5rem;
  --text-2xl: 1.875rem;
  --radius-card: 0.5rem;
  --radius-input: 0.5rem;
  --radius-pill: 999px;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in: cubic-bezier(0.7, 0, 0.84, 0);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
}
```

### DTCG `tokens.json`

```json
{
  "$schema": "https://design-tokens.github.io/community-group/format/",
  "color": {
    "paper": { "$value": "oklch(97% 0.007 255)", "$type": "color" },
    "paper-2": { "$value": "oklch(99% 0.004 255)", "$type": "color" },
    "paper-3": { "$value": "oklch(95.8% 0.01 255)", "$type": "color" },
    "ink": { "$value": "oklch(25% 0.037 258)", "$type": "color" },
    "ink-2": { "$value": "oklch(34% 0.032 258)", "$type": "color" },
    "muted": { "$value": "oklch(45% 0.035 255)", "$type": "color" },
    "neutral": { "$value": "oklch(38% 0.032 255)", "$type": "color" },
    "rule": { "$value": "oklch(88.5% 0.017 255)", "$type": "color" },
    "rule-2": { "$value": "oklch(66% 0.025 255)", "$type": "color" },
    "accent": { "$value": "oklch(50.5% 0.091 183)", "$type": "color" },
    "accent-ink": { "$value": "oklch(98.8% 0.004 255)", "$type": "color" },
    "focus": { "$value": "oklch(40% 0.14 250)", "$type": "color" }
  },
  "font": {
    "display": {
      "$value": "ui-sans-serif, system-ui, sans-serif",
      "$type": "fontFamily"
    },
    "body": {
      "$value": "ui-sans-serif, system-ui, sans-serif",
      "$type": "fontFamily"
    },
    "outlier": {
      "$value": "ui-monospace, SFMono-Regular, Menlo, monospace",
      "$type": "fontFamily"
    }
  },
  "size": {
    "text-xs": { "$value": "0.75rem", "$type": "dimension" },
    "text-sm": { "$value": "0.875rem", "$type": "dimension" },
    "text-base": { "$value": "1rem", "$type": "dimension" },
    "text-md": { "$value": "1.125rem", "$type": "dimension" },
    "text-lg": { "$value": "1.25rem", "$type": "dimension" },
    "text-xl": { "$value": "1.5rem", "$type": "dimension" },
    "text-2xl": { "$value": "1.875rem", "$type": "dimension" }
  },
  "space": {
    "3xs": { "$value": "0.25rem", "$type": "dimension" },
    "2xs": { "$value": "0.5rem", "$type": "dimension" },
    "xs": { "$value": "0.75rem", "$type": "dimension" },
    "sm": { "$value": "1rem", "$type": "dimension" },
    "md": { "$value": "1.5rem", "$type": "dimension" },
    "lg": { "$value": "2rem", "$type": "dimension" },
    "xl": { "$value": "2.5rem", "$type": "dimension" },
    "2xl": { "$value": "4rem", "$type": "dimension" }
  },
  "duration": {
    "micro": { "$value": "120ms", "$type": "duration" },
    "short": { "$value": "200ms", "$type": "duration" },
    "long": { "$value": "300ms", "$type": "duration" }
  }
}
```

### shadcn/ui variables

```css
:root {
  --background: 97% 0.007 255;
  --foreground: 25% 0.037 258;
  --card: 99% 0.004 255;
  --card-foreground: 25% 0.037 258;
  --popover: 99% 0.004 255;
  --popover-foreground: 25% 0.037 258;
  --primary: 50.5% 0.091 183;
  --primary-foreground: 98.8% 0.004 255;
  --secondary: 95.8% 0.01 255;
  --secondary-foreground: 34% 0.032 258;
  --muted: 95.8% 0.01 255;
  --muted-foreground: 45% 0.035 255;
  --accent: 50.5% 0.091 183;
  --accent-foreground: 98.8% 0.004 255;
  --destructive: 49% 0.18 29;
  --destructive-foreground: 98.8% 0.004 255;
  --border: 88.5% 0.017 255;
  --input: 66% 0.025 255;
  --ring: 40% 0.14 250;
  --radius: 0.5rem;
}
```
