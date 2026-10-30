---
skill_id: motion.ui_cards
name: UI Cards (glass cards with real content, progress steps, connectors, illustrations)
domain: motion
version: 1.0.0
summary: Polished explainer card layouts from VIDEO_ENGINE/remotion/src/ui (GlassPanel, IconChip, Illustration, ProgressRow, FlowLines, Headline); every card carries the plan's items, never grey placeholder lines.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent. The parts are our own SVG/DOM code; the icons beside them come from @phosphor-icons/react (MIT) and lucide-react (ISC), already approved.
risk_level: low
capabilities:
  - card
  - bento
  - process-steps
  - connectors
  - illustration
dependencies:
  - remotion
  - "@phosphor-icons/react"
compatible_agents:
  - motion_planning
  - motion_animation
compatible_project_modes:
  - motion_only
---

# UI Cards

The reference look: a big headline (accent word coloured) and a one-line subtitle, two or three glass cards with glowing borders (cyan and amber), connector lines with glowing nodes between them, a centre card that lists steps with progress bars and check badges, a round action badge below. Everything is readable on a phone.

## The parts (`import { ... } from "../ui"`)
- `GlassPanel accent width height padding enterAt` - the card. `accent` is a `#RRGGBB` string; the border, glow and inner shade come from it.
- `IconChip accent size enterAt` - gradient chip for a white Phosphor icon: `<IconChip accent="#F59E2E"><FileText size={56} weight="duotone" color="#fff" /></IconChip>`.
- `Illustration name="document-search" | "profile-card" | "growth-chart" size enterAt` - two-colour hero pictures (not line icons).
- `ProgressRow label progress accent enterAt` - label, filling bar, check badge when `progress` is 1. The fill is decorative; it prints no number (a number appears only when the plan's item has a `value`).
- `CheckBadge`, `FlowLines width height lines color enterAt` (lines are `[x1, y1, x2, y2]` px; draw them between the card edges), `Headline text accent accentWords size enterAt`.

- `StarField from to count seed` - the backdrop (gradient, drifting stars, dark horizon); first child of the scene's `AbsoluteFill`.
- `RingBadge accent ring size enterAt` - glowing orb with a turning orbit ring, an icon inside; sits on top of the centre card.
- `RatingStars rating size color enterAt`, `MiniBars values accent width height enterAt` (a card's footer chart), `ThumbsBadge accent size enterAt` (round approval badge under the cards).

## Content rule
Every card, panel, node or step draws the words of its plan item: title (`label`) 36px or more, one-line `caption` 24px or more, `value` only when the plan has one, a picture from `icon_hint` (an Illustration when one fits, else a duotone icon in an IconChip). A card without words, or a bar without a label, is a defect: the Final QC review sees it on the contact sheet and the scene is written again.

## Layout
1920x1080: headline at the top (about 50px from the edge), cards in the middle band, 100px side margins, 100 to 130px gaps for connectors; three cards of 420 / 620 / 420px fit one row. In 9:16 stack the cards in a column and use fewer, larger texts. Stagger `enterAt` by 6 to 10 frames per card so the eye follows the explanation, and keep every card visible to the last frame.
