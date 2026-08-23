# Concise rendering

Use with `styles/concise.md` and `templates/concise-email-v1.html`.

**Visual personality: briefing ledger / newspaper briefs.** The design should optimize rapid scanning with the least visual machinery of any style. Its personality comes from restraint: source, linked title, compact paragraph, repeat.

## Structure mapping

1. Render the shared masthead and reading-time capsule.
2. Render one compact independent entry for every retained source.
3. Finish immediately after the final entry; do not add thematic sections, editor's notes, a final synthesis, or a source catalog.

## Source entry

On desktop, use the template's narrow source rail beside the reading content:

- source/publication name in compact uppercase/sans-serif treatment;
- article/item title in serif display type, directly linked only when a valid source locator exists;
- one compact paragraph, normally 40–80 words, containing the central value of the source.

Separate entries with light horizontal rules and whitespace rather than cards.

When a valid locator exists, the linked title is the CTA. For email-only sources without a reliable locator, render the title as plain text with subtle email-only provenance; do not fabricate a CTA. Do not add avatars, thumbnails, engagement metrics, `KEY POINTS`, read-original buttons, or other per-entry chrome.

Do not add numerical citation pills unless the style itself is later changed to require them; the linked title supplies provenance for each independent entry.

## Callouts

Concise does not support callouts in its current editorial contract. Do not force the shared callout component into this layout. If a future change to `styles/concise.md` explicitly introduces callouts, update this rendering profile and template together.

## Responsive behavior

- **Desktop:** preserve the compact source rail and full editorial reading column.
- **Tablet:** narrow the source rail and gaps only while the paragraph remains comfortably wide.
- **Mobile:** remove the side-by-side source rail entirely. Stack the source/publication above the linked title and paragraph, using the short blue horizontal accent demonstrated by the template.
- Keep the entry single-column and body text comfortably readable.
- Reflow source metadata rather than shrinking it.

The mobile experience should feel like a clean vertical list of editorial abstracts, not a compressed desktop table.
