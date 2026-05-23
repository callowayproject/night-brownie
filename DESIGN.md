---
name: Night Brownie
description: A stealthy, always-on AI co-maintainer for your GitHub repositories.
colors:
  midnight-indigo: "#1A2136"
  twilight-purple: "#362A54"
  biolume-cyan: "#7EE2F5"
  moonlit-silver: "#D4D9EB"
  velvet-black: "#0A0D14"
typography:
  headline:
    fontFamily: "Public Sans, system-ui, -apple-system, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.334
    letterSpacing: "normal"
  body:
    fontFamily: "Public Sans, system-ui, -apple-system, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "normal"
  label:
    fontFamily: "Public Sans, system-ui, -apple-system, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 500
    lineHeight: 1.75
    letterSpacing: "0.02857em"
rounded:
  sm: "4px"
  md: "8px"
  pill: "100px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
components:
  card:
    backgroundColor: "#ffffff"
    rounded: "{rounded.sm}"
    padding: "{spacing.md}"
  card-header:
    backgroundColor: "{colors.midnight-indigo}"
    textColor: "#ffffff"
    padding: "16px 16px 24px"
  tag:
    backgroundColor: "rgba(26, 33, 54, 0.08)"
    textColor: "{colors.midnight-indigo}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  doc-label:
    backgroundColor: "{colors.midnight-indigo}"
    textColor: "#ffffff"
    rounded: "{rounded.pill}"
    padding: "0 5px"
---

# Design System: Night Brownie

## 1. Overview

### Creative North Star: "The Midnight Helper"

This system is built for the quiet efficiency of a helper who works while the world sleeps.
It values stealth, competence, and clarity.
The visual system earns credibility through calm and focus.
A developer who lands here is looking for a tool that solves problems without creating noise.
Night Brownie's design reflects this by being unobtrusive, dense with information,
and oriented toward nighttime productivity.

The reference is a well-organized toolkit or a quiet library: Everything has its place, the lighting is focused,
and the atmosphere is one of productive calm.
Color is used to highlight paths in the dark (biolume cyan), not for decoration.
Typography is precise and functional.
Every component exists to serve the primary goal: making repository maintenance invisible and effortless.

### Key Characteristics

- **Midnight-First**: Optimized for dark environments and focused work.
- **Tonal Depth**: Using subtle shifts in dark tones rather than shadows to define structure.
- **Fixed Points of Light**: Using high-contrast cyan accents sparingly for navigation and primary actions.
- **Dense Utility**: Information-rich components that stay out of the way until needed.

## 2. Colors: The Midnight Palette

The palette is anchored in the deep tones of night, with highlights that cut through the dark like starlight.

### Primary

- **Midnight Indigo** (`oklch(25% 0.08 260)` / `--midnight-indigo`): The structural anchor.
    Used for headers, active navigation, and primary branding.
    A deep, trustworthy indigo that signals depth and stability.
- **Biolume Cyan** (`oklch(80% 0.12 200)` / `--biolume-cyan`): The guiding light.
    Reserved for primary CTAs and critical orientation points.
    Its vibrant, mascot-inspired glow makes it instantly recognizable against the dark backgrounds.

### Secondary

- **Biolume Violet** (`oklch(70% 0.15 300)` / `--biolume-violet`): The character tone.
    Used for secondary interaction accents and brand-identifying decorative elements.
- **Moonlit Silver** (`oklch(80% 0.02 260)` / `--moonlit-silver`): The accent neutral.
    Used for secondary borders, meta-text, and subtle interactive states.
- **Starlight White** (`oklch(96% 0.02 200)` / `--starlight-white`): The sparkle of code.
    Used for tiny accents, particles, and high-contrast text elements that need to feel radiant.
- **Twilight Purple** (`oklch(30% 0.09 295)` / `--twilight-purple`): The companion tone.
    Used for secondary structural elements and decorative accents that need to stay within the nocturnal vibe.

### Neutral

- **Velvet Black** (`oklch(12% 0.01 260)` / `--velvet-black`): The default deep background.
    A rich, dark surface that is easier on the eyes than pure black.
- **Moonlit White** (`oklch(95% 0.01 260)` / `--moonlit-white`): The default text color.
    An off-white tinted toward the brand indigo to reduce harsh contrast.

### Named Rules

**The Biolume Rule.**
Biolume Cyan should appear sparingly—ideally only once or twice on a screen.
Like the mascot's energy, its value comes from its isolation and guidance.

**Tonal Layering.**
Depth is created by moving between Velvet Black, Midnight Indigo, and Twilight Purple.
Avoid box-shadows; use 1px borders in Moonlit Silver or tonal shifts to define boundaries.

## 3. Typography

**Body Font:** Public Sans.
**Label/Mono Font:** System monospace.

Typography is tool-like.
It doesn't perform; it informs.

### Hierarchy

- **Headline** (700 weight, 1.5rem, lh 1.334): Clear anchors.
- **Body** (400 weight, 1rem, lh 1.6): Dense but legible prose.
- **Label** (500 weight, 0.8125rem, lh 1.75): Meta-information and small UI elements.

## 4. Elevation

The system is flat and layered.
Depth is expressed through:

1. **Background Contrast**: Darker surfaces are "further away"; lighter surfaces are "closer".
2. **Borders**: 1px borders in `oklch` with low opacity for subtle definition.

## 5. Components

### Feature Cards

Flat, bordered cards with a tonal header (Midnight Indigo).

### Status Tags

Pill-shaped, using low-opacity Midnight Indigo backgrounds with darker text for readability on light surfaces,
or reversed for dark.

### Action Buttons

Primary actions use Biolume Cyan.
Secondary actions use Moonlit Silver borders.
