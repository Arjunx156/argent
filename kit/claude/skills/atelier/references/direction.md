# Direction

Take one house's discipline, not its surface.

| House | Take | Leave |
|---|---|---|
| Apple | vast whitespace, one product per screen, type scale with huge headlines, materials and depth | stock "Pro" gradients |
| Linear | dark precision, 1px borders, dense but calm UI, a subtle glow on one element | purple everywhere |
| Framer | big confident type, motion as the hero, clean black and white canvas | template sections |
| Chanel / Vogue | editorial serif display at enormous sizes, black and white, asymmetric grids, photography first | luxury clichés (gold, script fonts) |
| Awwwards winners | one signature interaction that nobody forgets | effects stacked for their own sake |

## Palettes

Each has background, surface, text, muted, line and accent. Accent stays at or under 10% of the area. Neutrals carry the design.

| Feel | bg | surface | text | muted | line | accent |
|---|---|---|---|---|---|---|
| Noir, editorial | #FFFFFF | #F5F5F5 | #0A0A0A | #6B6B6B | #E6E6E6 | none: black is the accent |
| Porcelain, Apple light | #FBFBFD | #FFFFFF | #1D1D1F | #6E6E73 | #E5E5EA | #0071E3 |
| Graphite, Linear dark | #08090A | #0F1011 | #F7F8F8 | #8A8F98 | #1E1F22 | #5E6AD2 |
| Canvas, Framer | #0A0A0A | #141414 | #FFFFFF | #9A9A9A | #222222 | #0099FF |
| Bone and ink | #EFEDE8 | #F7F6F2 | #141414 | #6F6B64 | #DAD6CE | #2F4B7C |
| Midnight, seasonal | #121212 | #1A1A1A | #EDEDED | #8C8C8C | #262626 | one per season: #D9822B autumn, #7FB5D6 winter |

Build custom palettes in OKLCH:
- Tint the neutrals a little toward the accent hue (chroma 0.005–0.01) so they feel related.
- Tune dark mode separately; never invert.
- Check every text pair with `scripts/contrast.py`.

## Type

All of these are free. Pair at most two families.

| Role | Choices |
|---|---|
| Editorial display | Bodoni Moda, Instrument Serif, Fraunces, Playfair Display (large sizes only) |
| Reading serif | EB Garamond, Source Serif 4, Newsreader |
| Interface | Geist, Inter Tight, Inter Display, Satoshi, General Sans |
| Display grotesk | Clash Display, Cabinet Grotesk |
| Mono | Geist Mono, JetBrains Mono |

- Scale by a ratio (1.25 for UI, 1.333–1.5 for editorial).
- Headlines get tighter tracking (−1% to −3%) and a line height of 1.0–1.1.
- Body text gets a line height of 1.5–1.6.
