---
name: atelier
description: Design and build web frontends at award level, in the lineage of Apple, Linear, Framer and editorial fashion (Chanel, Vogue). Covers direction, palette, type, spacing, glass navigation, motion, creative detail, near-instant performance and SEO. Use for any site, landing page, web app UI or component.
---

# Atelier

One memorable idea, everything else quiet, and nothing that loads slowly. Read only the reference you need.

| Need | Read |
|---|---|
| direction, palettes, type pairings | `references/direction.md` |
| glass nav, surfaces, depth | `references/glass.md` |
| motion, scroll, creative details, WebGL | `references/motion.md` |
| speed and SEO | `references/speed-seo.md` |
| what every site must ship | the **essentials** skill |

## Process

1. **Direction.** Name the subject, the audience and the single feeling. Pick one reference house from `direction.md` and say what you're taking from it. Write tokens: 4–6 named colors, type roles, a spacing scale, and radii by hierarchy.
2. **Check the plan against the tells below.** If a choice is what you'd produce for any similar brief, replace it and say why.
3. **Build** with the lightest stack that fits: Astro for content sites (zero JS by default), Next.js or Vite + React for apps, Tailwind, and native CSS before libraries. Check current versions with `--help` or `npm view`; don't guess.
4. **Verify.** Screenshot at 390, 1280 and 1920 px (webapp-testing) and fix what you see. Run `python ~/.claude/skills/atelier/scripts/contrast.py <fg> <bg>` for any pair in doubt, then `lighthouse <url> --only-categories=performance,accessibility,seo --quiet --chrome-flags=--headless` and keep 100/100/100 or explain the gap.

## Never

- Badges, pills or chips that decorate rather than inform; green "new"/"live" tags, check-mark lists, star ratings without real reviews.
- Emoji as icons; `→` tacked onto every link; ALL-CAPS eyebrow labels over every heading; one accent-colored word in a headline.
- The SaaS card kit: identical rounded cards, one radius everywhere, soft grey shadow, gradient washes.
- Default looks taken for choices: cream plus terracotta, near-black plus acid green, purple-to-blue gradients, glass on everything.
- Numbered markers (01/02/03) on content that isn't a sequence; fade-up on every section.
- Fake testimonials, logos or stats. Use real content or clearly marked placeholders.

## Always

- Hierarchy from size, weight and space. Body 60–75 characters, spacing on a 4/8 scale, generous section padding (96–160 px desktop).
- One accent at most, and WCAG AA contrast (4.5:1 body, 3:1 large).
- Every state is designed: hover, focus-visible, active, disabled, loading, empty, error.
- Motion answers a person's action or marks one orchestrated moment, and `prefers-reduced-motion` turns it off.
- Copy in plain, active, sentence-case words. Buttons say what happens: "Save changes", not "Submit".
- Restraint: before shipping, remove one thing.

For a formal UI audit, fetch the rules at `https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md` and report findings as `file:line`.
