# Motion and creative detail

Motion explains change or creates one remembered moment. Animate only `transform`, `opacity` and `filter`.

| Token | Value |
|---|---|
| durations | 120 ms (hover), 200 ms (UI), 320 ms (panels), 500–800 ms (hero) |
| ease out | `cubic-bezier(.2, .8, .2, 1)` |
| ease in-out | `cubic-bezier(.65, 0, .35, 1)` |
| spring (Motion) | `{ type: "spring", bounce: 0.15, duration: 0.4 }` |

## The ladder

Climb only as high as the brief needs:

1. CSS transitions and `@keyframes`.
2. Scroll-driven animations: `animation-timeline: view()` and `animation-range`, with no JavaScript.
3. The View Transitions API for page and state changes (`@view-transition`, `view-transition-name`).
4. Motion (motion.dev) for React gestures, layout and shared-element moves.
5. GSAP, now free including ScrollTrigger and SplitText, for orchestrated timelines.
6. Lenis smooth scroll, only when the experience is the product.
7. three.js, OGL or raw WebGL shaders for hero art, and Rive for interactive vector animation.

Lazy-load anything heavier than step 3, and keep it out of the critical path.

## Creative details

Seasonal pixel art, ambient creatures and hand-made flourishes give a site soul when they stay out of the way. Corner branches, cobwebs, a pumpkin or a spider descending on a thread are all fair game.

- Place them as absolutely positioned SVG or PNG at the edges, with `aria-hidden="true"` and `pointer-events: none`.
- Give pixel art `image-rendering: pixelated` and scale it by whole-number factors.
- Use slow ambient loops (6–20 s, ease-in-out), and pause them when off screen.
- Keep all decoration under 30 KB and never on the LCP path. Swap themes by date at build time, not runtime.
- `@media (prefers-reduced-motion: reduce)` stops all of it.
