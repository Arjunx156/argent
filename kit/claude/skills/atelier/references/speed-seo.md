# Speed and SEO

The target is instant: LCP under 1.2 s, INP under 100 ms, CLS under 0.05, and Lighthouse at 100 for performance, accessibility and SEO.

## Speed

- **Ship less.** Marketing pages get under 70 KB of gzipped JavaScript. Use static or server rendering, and hydrate only islands that need it.
- **Fonts.** Self-host WOFF2, subset with `pyftsubset font.ttf --flavor=woff2 --unicodes="U+0000-00FF,U+2000-206F"`, and preload the one used above the fold. Use `font-display: swap` with metric-matched fallbacks (`size-adjust`) so nothing shifts.
- **Images.** Use AVIF, then WebP (sharp), with `width` and `height` on every image. The LCP image gets `fetchpriority="high"`; everything else gets `loading="lazy"` and `decoding="async"`.
- **SVG.** Run every icon and illustration through `svgo`. Prefer inline sprites over icon fonts.
- **CSS.** Inline the critical CSS and defer the rest. Use `content-visibility: auto` on long sections below the fold.
- **Navigation.** Use Speculation Rules to prerender likely next pages, and keep cache headers long on hashed assets.
- **Never** use layout-shifting ads or embeds, render-blocking third-party scripts, or carousels as the hero.

Measure with `lighthouse <url> --only-categories=performance,accessibility,seo --quiet --chrome-flags=--headless`.

## SEO

- One `<h1>`, real heading order, semantic landmarks (`header`, `nav`, `main`, `footer`).
- A unique `<title>` of 50–60 characters, a meta description of 140–160, and a canonical URL.
- Open Graph and Twitter cards, with a 1200×630 image per page.
- JSON-LD for the page type: Organization, Product, Article, BreadcrumbList or FAQ.
- `sitemap.xml`, `robots.txt`, clean lowercase URLs, and `hreflang` when there's more than one language.
- Alt text that describes; empty `alt=""` for decoration.
