// folio: book-grade typesetting.
// white page, one serif, lots of air. no rules, no boxes, no fills.

#let ink = rgb("#151515")
#let quiet = rgb("#6f6f6f")

// content -> plain string, for pdf metadata
#let plain(it) = {
  if it == none { "" }
  else if type(it) == str { it }
  else if it.has("text") { it.text }
  else if it.has("children") { it.children.map(plain).join() }
  else if it.has("body") { plain(it.body) }
  else if it == [ ] { " " }
  else { "" }
}

// letterspaced small caps for labels, bylines, table heads
#let caps(body, tracking: 0.12em) = text(tracking: tracking, smallcaps(lower(body)))

#let folio(
  title: none,
  subtitle: none,
  author: none,
  date: none,
  note: none,             // one quiet line under the byline: edition, version, place
  paper: "a4",
  lang: "en",
  size: 12pt,
  contents: true,
  depth: 2,
  chapter-label: "Chapter",
  serif: "EB Garamond",
  mono: "JetBrains Mono",
  body,
) = {
  let authors = if author == none { () }
    else if type(author) == array { author }
    else { (author,) }

  set document(
    title: if title == none { none } else { plain(title) },
    author: authors.map(plain),
  )

  // page and text
  set page(paper: paper, fill: white, margin: (x: 42mm, top: 34mm, bottom: 40mm))
  set text(
    font: serif, size: size, fill: ink, lang: lang,
    number-type: "old-style", hyphenate: true,
  )
  set par(
    justify: true, leading: 0.74em, spacing: 1.3em, linebreaks: "optimized",
    justification-limits: (tracking: (min: -0.012em, max: 0.018em)),
  )
  set strong(delta: 200)

  // headings
  set heading(numbering: "1.1")
  show heading: set text(weight: "regular", hyphenate: false)
  show heading: set par(justify: false, leading: 0.5em)

  show heading.where(level: 1): it => {
    pagebreak(weak: true)
    // the contents title isn't outlined itself; start it higher so long contents fit
    v(if it.outlined { 26mm } else { 10mm })
    if it.numbering != none {
      text(size: 9.5pt, fill: quiet, caps[#chapter-label #counter(heading).display("1")])
      v(6mm, weak: true)
    }
    block(text(size: 26pt, it.body))
    v(15mm, weak: true)
  }

  show heading.where(level: 2): it => block(
    above: 2.7em, below: 1.15em, sticky: true,
    text(size: 15pt, it.body),
  )

  show heading.where(level: 3): it => block(
    above: 2.2em, below: 0.9em, sticky: true,
    text(size: 12pt, style: "italic", it.body),
  )

  show heading.where(level: 4): it => block(
    above: 1.9em, below: 0.8em, sticky: true,
    text(size: 10pt, caps(it.body, tracking: 0.08em)),
  )

  // contents
  set outline(depth: depth)
  set outline.entry(fill: none)

  show outline.entry.where(level: 1): it => {
    v(0.95em, weak: true)
    link(it.element.location(), box(width: 100%, {
      box(width: 2.2em, text(fill: quiet, it.prefix()))
      it.body()
      h(1fr)
      it.page()
    }))
  }

  show outline.entry.where(level: 2): it => {
    v(0.44em, weak: true)
    link(it.element.location(), box(width: 100%, {
      h(2.2em)
      text(size: 0.94em, it.body())
      h(1fr)
      text(size: 0.94em, fill: quiet, it.page())
    }))
  }

  // body elements
  set list(marker: text(fill: quiet)[–], indent: 0.3em, body-indent: 0.75em, spacing: 0.8em)
  set enum(indent: 0.1em, body-indent: 0.6em, spacing: 0.8em)
  // definition lists read like a dictionary: term on its own line, description below
  show terms.item: it => block(above: 1.35em, below: 1.35em, breakable: false, {
    block(below: 0.35em, sticky: true, text(weight: "medium", {
      show raw: set text(size: size * 0.86)
      it.term
    }))
    pad(left: 1.6em, par(justify: false, it.description))
  })

  show link: set text(fill: ink)
  show std.divider: v(2.4em)

  set raw(theme: "folio.tmTheme")
  // absolute sizes, since typst already scales raw text and em would compound.
  // inline code matches the text's x-height; headwords sit a touch larger.
  show raw: set text(font: mono, size: size * 0.76)
  show raw.where(block: true): set text(size: 8.8pt)
  show raw.where(block: true): set par(justify: false, leading: 0.6em)
  // listings that fit on a page (~40 lines) never split
  show raw.where(block: true): it => block(
    width: 100%, inset: (left: 1.6em), above: 1.6em, below: 1.6em,
    breakable: it.lines.len() > 40, it,
  )

  show quote.where(block: true): it => pad(x: 2.2em, block(above: 1.6em, below: 1.6em, {
    set text(style: "italic")
    it.body
    if it.attribution != none {
      v(0.4em)
      align(right, text(style: "normal", size: 0.9em, fill: quiet, it.attribution))
    }
  }))

  set table(stroke: none, inset: (x: 0.55em, y: 0.5em))
  set table.hline(stroke: none)
  set table.vline(stroke: none)
  show table: set par(justify: false)
  show table: set text(size: 0.93em, number-type: "lining", number-width: "tabular")
  show table.cell.where(y: 0): it => text(size: 0.92em, fill: quiet, caps(it, tracking: 0.06em))

  set figure(gap: 1.1em)
  show figure: set block(above: 2em, below: 2em)
  show figure.caption: set text(size: 0.88em, style: "italic", fill: quiet)
  set figure.caption(separator: [. ])

  set footnote.entry(separator: none, clearance: 1.8em, gap: 0.55em)
  show footnote.entry: set text(size: 8.8pt)
  show footnote.entry: set par(justify: false)

  // front page
  if title != none {
    page(margin: (x: 30mm, top: 30mm, bottom: 32mm), {
      set par(justify: false, leading: 0.45em)
      set align(center)
      v(2.3fr)
      text(size: 36pt, hyphenate: false, title)
      if subtitle != none {
        v(9mm)
        text(size: 14.5pt, style: "italic", fill: quiet, subtitle)
      }
      v(3fr)
      if authors.len() > 0 {
        text(size: 10.5pt, caps(authors.join(", "), tracking: 0.16em))
      }
      if date != none {
        v(3.5mm)
        text(size: 10.5pt, fill: quiet, date)
      }
      if note != none {
        v(2mm)
        text(size: 9.5pt, fill: quiet, style: "italic", note)
      }
      v(0.6fr)
    })
  }

  if contents {
    outline()
  }

  // body: arabic page numbers from 1, centred at the foot
  set page(footer: context align(center, text(size: 9pt, fill: quiet, counter(page).display("1"))))
  counter(page).update(1)
  body
}
