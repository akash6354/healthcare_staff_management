# UI direction

Skills that govern every screen: **frontend-design** (visual direction, type, layout, copy) and **dataviz**
(status colours, charts, scorecards; colours validated with its `validate_palette.js`). This file is their output for OGLOS.

## 1. Subject, audience, job

- **Subject:** the physical hospital (buildings, floors, wards, washrooms, beds) and the non-clinical work that keeps it running.
- **Audiences:** the MD/Owner (buyer, glances at the overview, decision 2) · operations managers and supervisors (live control, desktop) ·
  housekeeping and maintenance workers (low-end Android, bright corridors, Kannada/Hindi/English) · vendors · the public (one QR scan).
- **Primary job:** show at a glance *where* in the building work is late or unproven, and *who owns it*.

**Feel:** a calm, exact control room, closer to airline ops or a rail signal box than a SaaS marketing page. Information first.

## 2. The one bold idea: the building elevation

The hero screen draws the hospital **as a building cross-section**. Floors are stacked horizontal bands, top floor at the top
(as an architect's elevation reads), and each area is a tile on its floor. Every other screen stays quiet and disciplined so this one carries the identity.
It suits the subject (the work *is* spatial), no generic dashboard looks like it, and it scales from the desktop to the wall TV.

## 3. Colour (extracted from `/media`, decision 7)

Measured from `oglos-logo-light.png` / `oglos-logo-dark.png` (2400×556):

| Name | Hex | Source | Role |
|---|---|---|---|
| **Ward Green** | `#0F3D2E` | wordmark | primary: top bar, primary buttons, headings ink accent, selected nav |
| **Tile Green** | `#1C513E` | logo tile, top-left | hover/pressed of primary, TV board bands |
| **Deep Tile** | `#0C2E23` | logo tile, bottom-right | wall-TV surface (dark theme), login side panel |
| **Gilt** | `#D4AF56` | "G" mid-gradient | gold accent **on dark only** (TV, login panel); never body text, never large fills |
| **Brass** | `#8A6A1F` | darkened from `#A78230` (G dark end) for AA | gold accent on light: focus ring, the active-tab underline, small highlights (5.05:1 on white) |
| **Pale Gilt** | `#F2D98F` | dark wordmark | wordmark/text on Ward Green (8.7:1) |
| **Cream Dot** | `#F6EBC8` | logo dot | used once, as the selected-tile ring on dark |

Neutrals are **green-tinted greys derived from Ward Green**, deliberately *not* the cream or near-white default:

| Token | Hex | Use | Contrast |
|---|---|---|---|
| `--bg` | `#F4F5F1` | page plane | — |
| `--surface` | `#FFFFFF` | panels, tables | — |
| `--surface-sunk` | `#ECEEE9` | table header, wells | — |
| `--border` | `#D9DDD6` | hairlines | — |
| `--border-strong` | `#7A827D` | inputs, focus-adjacent | 3.95:1 (non-text) |
| `--ink` | `#1A2420` | body text | 14.6:1 on bg |
| `--ink-2` | `#5A635E` | secondary/muted text | 5.7:1 on bg |

### Status palette (one palette, everywhere, always with icon + label)

Validated with dataviz `validate_palette.js --pairs all`. Light vs white: all pass, worst colour-blind pair 7.3 ΔE (WARN band).
Dark vs `#0C2E23`: all pass, worst 6.7 ΔE (WARN band). The WARN band is legal **only with secondary encoding**, and OGLOS
always pairs each status with an icon and a label, so the rule is met by design. Status colours are reserved: never used for chart series.

| Status (area board / SLA) | Fill (light) | Fill (dark/TV) | Text ink (AA on white) | Icon (Lucide) | Shape cue |
|---|---|---|---|---|---|
| Clean & verified · SLA met | `#3AA86A` | `#38AA6B` | `#1D6B40` | `circle-check` | solid |
| In progress · on time | `#2A6FBF` | `#4E8DD8` | `#1F5A9E` | `loader` (static, not spinning) | solid |
| Awaiting inspection | `#9B4F96` | `#B46DB3` | `#7D3A78` | `clipboard-check` | solid |
| Due · at risk | `#C98A00` | `#C08812` | `#7A5300` | `clock-alert` | solid |
| Needs attention · overdue / escalated | `#B3261E` | `#D03F37` | `#9E1F18` | `triangle-alert` (+ level badge "L2") | solid + thick border |
| Not due / idle | `--surface` + `--border-strong` outline | outline | `--ink-2` | `circle` | outline only |
| Out of service | `--surface-sunk` + 45° hatch | hatch | `--ink-2` | `ban` | hatched |

Text on a status fill: white, except `#1A2420` on amber.

## 4. Typography

| Role | Face | Why |
|---|---|---|
| UI (Latin) | **Anek Latin** (Ek Type, OFL, variable wght 100–800, wdth 75–125) | Designed in India as **one family across Latin, Kannada and Devanagari**, so all three languages share one voice and rhythm instead of mixing unrelated fonts. Not Inter/Roboto/Arial. |
| UI (Kannada) | **Anek Kannada** | same family |
| UI (Hindi) | **Anek Devanagari** | same family |
| IDs, timestamps, SLA countdowns | **IBM Plex Mono** (OFL) | required by the spec for IDs/timers only, never for labels |

- Self-hosted woff2 subsets (no Google Fonts call from production pages, so no third-party request from hospital networks).
- `font-variant-numeric: tabular-nums` on tables, timers and counts. **Phase 1 check:** confirm Anek ships `tnum`; if it doesn't, numeric columns use Plex Mono and the fallback UI face becomes IBM Plex Sans (+ Noto Sans Kannada/Devanagari).
- Width axis: `wdth 100` for body, `wdth 112` for the OGLOS hero headings, `wdth 90` for dense table cells on desktop.

**Type scale** (ratio ~1.2, desktop base 14px dense / PWA base 17px):
| Token | Desktop | PWA | Use |
|---|---|---|---|
| `--fs-xs` | 12 | 14 | table meta, legends |
| `--fs-sm` | 13 | 15 | secondary text |
| `--fs-base` | 14 | 17 | body |
| `--fs-md` | 16 | 19 | section titles |
| `--fs-lg` | 20 | 22 | page titles |
| `--fs-xl` | 28 | 28 | MD overview headline |
| `--fs-tv` | 32 / 48 | — | wall-TV tiles / headline |

Line-height 1.45 for body, 1.2 for headings. Indic scripts get +0.1 line-height (taller matras). Sentence case everywhere; no all-caps labels.

## 5. Shape, space, elevation

- 4px spacing grid. Desktop density: 32px table rows, 36px controls. PWA: **56px** primary targets, 48px minimum.
- Radius follows hierarchy: board tiles 3px (tight, technical), controls 6px, panels 8px, sheets/dialogs 12px. Not one radius for everything.
- No drop shadows on panels; 1px `--border` hairlines. Shadow only on floating layers (menus, dialogs, toasts).
- Motion: one meaningful motion only, a tile **briefly outlines** (200 ms) when its status changes live. Everything else is instant. `prefers-reduced-motion` removes it.
- Icons: **Lucide** (ISC licence), 1.75px stroke. No emoji as icons.

## 6. Layout and key screens

### 6.1 Desktop shell (web-admin)
Left rail 232px (collapsible to 64px icons): logo mark + "OGLOS"; nav groups *Live*, *Work*, *Setup*, *Reports*. Top bar: page title,
hospital name, global search (task #, area code), notifications, user menu. Content is left-aligned, max 1440px. Page title: `<Page> · OGLOS`.

### 6.2 Login
```
┌──────────────────────────────┬──────────────────────────────────┐
│ Deep Tile panel (#0C2E23)    │  Sign in to Sunrise Multispeciality│
│  [logo]                      │  Work email  [______________]      │
│  OGLOS                       │  [ Send sign-in code ]  (primary)  │
│  Hospital Operations &       │  ── or ──                           │
│  Accountability Platform     │  Use password (admins & vendors)    │
│                              │  Language: English · ಕನ್ನಡ · हिन्दी     │
│  thin Gilt rule, one line of │                                    │
│  real copy, no stock photos  │  Privacy notice · Help             │
└──────────────────────────────┴──────────────────────────────────┘
```
Mobile: the panel becomes a 120px header band.

### 6.3 Area status board (hero)
```
 Live board   Building: Main block ▾   Filter: All areas ▾   [12 need attention] [5 awaiting inspection]
┌────────────────────────────────────────────────────────────────────┬──────────────────────┐
│ 4  │ ■ICU-1 ■ICU-2 ■ICU-WC ▲NS-4  □Corr-4  ▨Store                   │ Needs attention      │
│ 3  │ ■W3-A  ■W3-B  ◆W3-WC1 ●W3-WC2 ■Corr-3                          │ ▲ W2-WC1  overdue    │
│ 2  │ ●OT-1  ●OT-2  ■OT-Prep ▲W2-WC1 ◆Corr-2                         │   38:12 · Ravi K · L2│
│ 1  │ ■OPD-A ■OPD-B ▲OPD-WC ■Lab   ■Pharm-front                      │ ▲ OPD-WC  overdue    │
│ G  │ ■Lobby ■Casualty ◆ER-WC ■Canteen ■Lift-lobby                   │ ◆ ER-WC   at risk    │
│ B1 │ ■Kitchen ▨Laundry ■BMW store                                   │ … (sorted by severity│
└────┴───────────────────────────────────────────────────────────────┴──────────────────────┘
 Legend: ■ Clean & verified  ● In progress  ◆ Due / at risk  ▲ Needs attention  □ Not due  ▨ Out of service  ✓ Awaiting inspection
```
- The floor label column uses Plex Mono, left-aligned. Tiles have a fixed width per floor band, wrap within the band, and show the area code plus a countdown (mono) when a timer is running.
- Clicking a tile opens a right-side **drawer** with the current task, its owner, evidence thumbnails and the audit timeline (the board never navigates away).
- High-risk areas get a small Brass corner notch, which is the one use of gold on this screen.
- Desktop 1440: the board takes about 75% of the width. Mobile 390: floors become an accordion list, and the attention queue comes first.

### 6.4 MD overview (the buyer's screen, decision 2)
Not a grid of identical stat cards. It reads top-down like a briefing:
```
Today at Sunrise · Thu 20 Nov
94% of tasks on time   (412 of 438)      ▁▂▃▅▆▇▆▇  last 14 days, target 90% ──
3 escalations open · 2 vendor jobs past SLA · 1 area out of service
───────────────────────────────────────────────────────────────────────────
On-time rate by department          (horizontal bars, sorted, target line)
Areas that failed inspection most (7 days)      Vendor SLA this month (table)
Worst 5 open items (owner, age, level)          Inspection pass rate trend (line)
```
- The headline is a sentence with numbers in context ("of 438", "target 90%"), never a bare big number.
- Charts follow dataviz: one axis, thin marks, direct labels on at most 4 series, a hover tooltip, a table view toggle. Chart series use a categorical palette derived from the brand (Ward Green, a teal, a slate blue, Brass), validated in Phase 1 and kept separate from status colours.

### 6.5 Worker task screen (PWA, 390px)
```
┌───────────────────────────────┐
│ ‹  W2-WC1 · Washroom, Ward 2  │  ← area, large (fs-lg)
│ Floor 2 · High risk ▲          │
│ Due in 18:40  (mono, amber)    │
├───────────────────────────────┤
│ ☐ Floor mopped                 │  56px rows, whole row tappable
│ ☐ Toilets disinfected          │
│ ☐ Soap & tissue refilled       │
│ ☐ Bin emptied                  │
│ [📷 Take photo]  0 of 1         │  (Lucide camera icon, not emoji)
├───────────────────────────────┤
│ ███ Scan QR to finish ███       │  one primary action, thumb zone
└───────────────────────────────┘
 Offline: "Saved on this phone. Will send when online." banner, Brass left edge
```
- One primary action per screen, at the bottom: *Accept* → *Scan QR to start* → *Scan QR to finish* → *Submit*.
- High-contrast mode by default (ink on white, 17px), readable in bright corridors. Every string goes through i18n, with icons beside labels for low literacy.

### 6.6 Task detail and audit timeline
A vertical timeline. Each event shows its state chip (status icon + label), actor (role + name or "Staff #1234"), server time in mono IST, and evidence thumbnails inline. A "Chain verified ✓" footnote shows when the hash check passes.

### 6.7 Wall-TV operations board (dark, decision 8)
1920×1080, Deep Tile surface, the building elevation at `--fs-tv`, an escalations column on the right, and a clock in Plex Mono.
It auto-cycles buildings every 30 s. No interaction, first names only, no phone numbers.

### 6.8 Public QR page
Hospital name + area ("Washroom, Ward 2, Floor 2"), then "What's wrong?" with a 2-column grid of large icon tiles (Dirty washroom, No water,
AC not working, Light not working, Bin full, Other). Then an optional photo, an optional phone number behind a consent checkbox with a link to the short notice, and the *Send report* button.
The confirmation shows a reference number. GIGW-friendly: plain language, works without JS for the core form if feasible, 18px base.

## 7. Copy rules
- Plain verbs, sentence case, active voice. A button names its result: "Send sign-in code", "Mark verified", "Reject and reassign".
- The same word through the whole flow ("Verify" → toast "Verified").
- Errors say what happened and how to fix it: "That QR code belongs to Ward 3. Scan the code in W2-WC1."
- Never "NABH compliant". Write "supports NABH documentation".
- No arrows appended to buttons, no tracked-out eyebrow labels, no decorative numbering.

## 8. Self-review against generic defaults (frontend-design process)

| Default I'd drift to | What we chose instead, and why |
|---|---|
| Warm cream page + terracotta accent | Green-tinted greys taken from the logo; gold limited to hairline accents |
| Grid of identical rounded stat cards | The building elevation (spatial) + a briefing-style MD headline sentence |
| Inter / system sans | Anek, one Indian type family covering all three scripts |
| Mono for every small label | Mono only for IDs, times and countdowns (the spec requires it) |
| One radius and a soft shadow on everything | Radius by hierarchy, hairlines, shadow only on floating layers |
| Fade-in on every section | One live-change outline pulse, nothing else |
| Default shadcn look | shadcn primitives re-themed through `packages/ui/tokens.css`; custom board, timeline and chip components |

## 9. Screenshot critique loop (every screen)
Playwright at 1440×900 and 390×844 → check against §2–§8: status always icon+label? gold only as accent? targets ≥48px on PWA?
Kannada/Hindi strings fit without clipping? → fix → re-shoot. Save shots under `docs/screens/<phase>/`.
