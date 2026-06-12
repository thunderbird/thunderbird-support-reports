# Design Guide — Thunderbird Support Reports

Design system: **Bolt** (bolt.thunderbird.net) — Thunderbird's design system.
These reports are web surfaces. Apply web conventions throughout.

---

## Principles

- **Consistent familiarity** — simplicity, ease of use, logical structure
- **Inclusive freedom** — accessible, adaptable, customizable
- **Privacy companion** — privacy-first, transparent, respectful of user data and attention
- **Humanize user collaboration** — clear feedback, supportive tone, jargon-free
- **Craft** — clean, minimal, elegant; perceivable quality across platforms

---

## Color

### Semantic tokens (use these, not raw hex)

| Token | Hex | Use |
|---|---|---|
| `info` | `#004F9B` | Buttons, chips, icons |
| `infoContainer` | `#F0F8FF` | Banners, cards, backgrounds |
| `onInfo` | `#FFFFFF` | Text/icon in filled info components |
| `onInfoContainer` | `#004F9B` | Text/icons inside info containers |
| `success` | `#194E2C` | Icons, highlights, action emphasis |
| `successContainer` | `#F4F9F4` | Background of success banners, badges, cards |
| `onSuccess` | `#FFFFFF` | Text/icon in filled success components |
| `onSuccessContainer` | `#194E2C` | Text/icons inside success containers |
| `warning` | `#713F12` | Icons, highlights, action emphasis |
| `warningContainer` | `#FEFAE8` | Background of warning banners, badges, cards |
| `onWarning` | `#FFFFFF` | Text/icon in filled warning components |
| `onWarningContainer` | `#713F12` | Text/icons inside warning containers |
| `error` | `#7F1D1D` | Icons, highlights, dangerous actions |
| `errorContainer` | `#FEF2F2` | Background of error banners, badges, cards |
| `onError` | `#FFFFFF` | Text/icon in filled error components |
| `onErrorContainer` | `#7F1D1D` | Text/icons inside error containers |

Bolt also defines Surface, Primary, Secondary, Success, Warning, Critical, and Text+Icon palettes in Light, Dark, High Contrast, TFAndroid Light/Dark, and Global modes. See bolt.thunderbird.net/color for full swatches.

---

## Typography

**Web/design mockups:** Inter (open source, sans-serif). Download: https://rsms.me/inter/

Desktop production uses system fonts (Segoe UI on Windows, SF Pro on macOS, Noto Sans / Cantarell / Ubuntu on Linux). For desktop, **13px = 1rem**.

| Role | Weight | Size | Line height |
|---|---|---|---|
| Title large | 400 | 22px | 100% |
| Title medium | 400 | 20px | 100% |
| Title small | 500 | 15px | 100% |
| Title extra-small | 700 | 13px | 100% |
| Body medium | 500 | 13px | 17px |
| Body small | 400 | 13px | 100% |
| Body extra-small | 400 | 11px | 100% |
| Label medium | 600 | 13px | 150% |
| Label small | 700 | 10px | 100% |

---

## Icons

**Web:** [Phosphor Icons](https://phosphoricons.com/) — use the package/library, not one-off SVG assets. Multiple weights, consistent visual style, broad coverage.

---

## Spacing

Base unit: **4px**. Web base scale: 4px, 8px, 12px.

| Token | rem | px |
|---|---|---|
| space-4 | 0.25rem | 4px |
| space-8 | 0.5rem | 8px |
| space-12 | 0.75rem | 12px |
| space-24 | 1rem | 24px |
| space-36 | 1.5rem | 36px |
| space-48 | 3rem | 48px |
| space-64 | 4rem | 64px |
| space-96 | 6rem | 96px |
| space-128 | 8rem | 128px |
| space-192 | 12rem | 192px |
| space-256 | 16rem | 256px |
| space-max | 24rem | 384px |

---

## Layout

### Breakpoints

Design primarily for **extra-small** and **large**:

| Name | Min width |
|---|---|
| Extra-small | 375px |
| Small | 640px |
| Medium | 768px |
| Large | 1280px |
| Extra-large | 1440px |

### Grid

| Breakpoint | Columns | Margins | Gutters |
|---|---|---|---|
| Large (≥ 1280px) | 12 | 32px | 16px |
| Extra-small (375px, < 599px) | 4 | 16px | 16px |

---

## Density

Density affects row/component spacing and vertical padding — not font size, icon size, or structure.

| Density | Line height | Card padding | Row spacing | Input padding |
|---|---|---|---|---|
| Compact | ~1.35× font size | 12px | 9px | 6px top+bottom |
| Default | ~1.5× font size | 16px | 9px | — |
| Relaxed | ~1.65× font size | 24px | — | — |

Use **Compact** for dense data UIs. **Default** for most cases. **Relaxed** for touch-friendly or readability-focused surfaces.
