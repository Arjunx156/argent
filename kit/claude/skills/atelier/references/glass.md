# Glass and depth

Glass belongs only to things that float over content: the nav, sheets, popovers and toasts. Never use it on cards in the flow.

- Use one blur level per page.
- Use a 1px inner hairline instead of a border.
- Use long, soft shadows tinted by the background.

## Floating pill nav

Icons only, with the label shown on the active item. This works for both light and dark tokens.

```css
.nav {
  position: fixed; top: 16px; left: 50%; translate: -50% 0; z-index: 50;
  display: flex; gap: 4px; padding: 6px; border-radius: 999px;
  background: color-mix(in oklch, var(--bg) 60%, transparent);
  backdrop-filter: blur(18px) saturate(160%);
  -webkit-backdrop-filter: blur(18px) saturate(160%);
  box-shadow: inset 0 0 0 1px color-mix(in oklch, var(--text) 10%, transparent),
              0 12px 32px -16px rgb(0 0 0 / .45);
}
.nav a {
  display: inline-flex; align-items: center; gap: 8px;
  height: 40px; min-width: 40px; padding: 0 12px; border-radius: 999px;
  color: var(--muted); transition: color .2s, background-color .2s;
}
.nav a:hover { color: var(--text); background: color-mix(in oklch, var(--text) 8%, transparent); }
.nav a:focus-visible { outline: 2px solid var(--text); outline-offset: 2px; }
.nav a[aria-current="page"] { background: var(--text); color: var(--bg); view-transition-name: nav-pill; }
.nav a span { display: none; }
.nav a[aria-current="page"] span { display: inline; }
@supports not (backdrop-filter: blur(1px)) { .nav { background: var(--surface); } }
@media (prefers-reduced-transparency: reduce) { .nav { background: var(--surface); backdrop-filter: none; } }
```

Add `@view-transition { navigation: auto; }` and the active pill slides between pages natively, with no JavaScript. Every icon link needs an `aria-label`.

## Radii and elevation

- Radii scale with size: 6 px controls, 12 px cards, 20–28 px sheets, 999 px pills.
- Nested radius = outer radius minus padding.
- Use three elevations at most: flat, raised, floating.
