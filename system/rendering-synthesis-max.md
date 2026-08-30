# Synthesis MAX rendering

Use with `styles/synthesis-max.md` and `templates/synthesis-max-email-v1.html`.

**Visual personality: editorial dossier.** The composition should read as one analytical briefing: an opening thesis followed by a sequence of synthesized threads. It should feel cumulative and deliberate rather than like independent article cards.

## Localization

All English component names in this profile are semantic maintainer labels. Resolve every visible label, generated editorial title, date, status, reading-time unit, call to action, accessibility string, and footer through the configured digest language. The template's localization placeholders must be filled with natural target-language copy; no hard-coded English UI text may survive in a non-English digest. **Do not localize original source/article titles:** every `SOURCE_TITLE` must be displayed verbatim in its original language. Preserve each component's visual treatment and structural role while localizing only its generated wording.

## Structure mapping

1. Render the shared masthead and reading-time capsule.
2. Render `THE BIG PICTURE` as the opening thesis.
3. Render each synthesized theme as a numbered `THREAD`.
4. End each thread with `SOURCE NOTES`.
5. End the editorial body with the complete bibliographic `Sources` catalog required by the style.

## The Big Picture

Treat `THE BIG PICTURE` as an opening editorial statement, not a blockquote or card.

- Use the uppercase micro-label.
- Use the short blue horizontal rule from the template.
- Use prominent serif text with generous whitespace.
- Keep the synthesis compact and citation-supported.
- Do not restore the old width-expensive blue left rule.

## Threads

Open every theme with the small running head:

`01 / THREAD`

Then render:

- serif editorial title;
- muted one-sentence deck;
- synthesis paragraphs;
- inline numerical citation pills immediately after supported claims;
- zero or one authorized callout;
- `SOURCE NOTES`.

The number is part of the running head rather than a large side rail. Use whitespace, typography, and horizontal rules to create rhythm instead of cards.

## SOURCE NOTES

At the end of each thread:

- use uppercase `SOURCE NOTES`;
- list only the principal author/publication/sender names materially used in that thread;
- place the stable numerical citation pill immediately after each name; make it clickable only when that source has a valid locator;
- let entries wrap naturally on narrow screens.

The final `Sources` catalog uses the shared bibliographic row pattern, **grouped by source identity by default**. Render each newsletter/publication/sender group with one compact source-group heading, followed by its rows. Each row keeps the permanent global citation number in the narrow numerical rail plus the original title and, when useful, an author distinct from the group identity. Do not repeat the group identity on every row. Link the citation/title only when a valid locator exists; otherwise render email-only provenance without a fabricated destination. Render `Selected` in the shared green status treatment, `Worth reading` in yellow, and every neutral status—including `Reviewed`—in gray. `Worth reading` appears only on an unselected source that the editor still actively recommends; it is mutually exclusive with `Selected` and does not create a narrative thread. For every substantively read source, append the original reading time to the badge with a middle dot, for example `Selected · 12 min`, `Worth reading · 8 min`, or `Reviewed · 4 min`. More specific neutral outcomes may also carry time when substantive material was actually read; omit it when no substantive reading occurred. Grouping must never renumber sources.

## Callouts

Remove the template's example callout unless the active digest instructions authorize one.

When authorized, use at most one callout inside a thread, after the synthesis prose and before `SOURCE NOTES`. Use the shared neutral callout primitive from `system/html-rendering.md`.

## Template independence

The HTML template is a structural specimen. Its placeholder Big Picture, thread, and source rows demonstrate markup only. Never infer thread count, paragraph count, or section length from the template; render exactly the editorial structure produced by the style.

## Responsive behavior

This layout should remain primarily linear across sizes.

- **Desktop:** full editorial measure and spacing.
- **Tablet:** reduce horizontal padding and large vertical gaps modestly.
- **Mobile:** keep the same thesis → thread → thread sequence, with smaller headline scale but body text near `16px / 25–26px`.
- Allow masthead metadata and long source-note rows to stack/wrap.
- Keep the Big Picture full-width inside the editorial column.
- Keep the bibliographic citation rail narrow enough to remain useful on mobile.

Avoid side rails that would require a structural collapse on phone; Synthesis should feel like a continuous dossier at every width.



