# Curated Discovery rendering

Use with `styles/curated-discovery.md` and `templates/curated-discovery-email-v1.html`.

**Visual personality: magazine edit.** The composition should make editorial judgment visible: a small number of selected ideas receive unequal depth, with optional discoveries below. It should feel curated, readable, and idea-first rather than like a list of article cards.

## Structure mapping

1. Render the shared masthead and reading-time capsule.
2. Render the opening orientation as `TODAY'S EDIT`: a restrained editorial note, not a unifying thesis.
3. Render the strongest selected items as numbered editorial selections.
4. If one item is clearly stronger or richer, allow the template's `FEATURED IDEA` treatment. Do not manufacture a featured item merely to satisfy the layout.
5. Render optional `Discoveries` only when the style output contains them.
6. End full selections with the shared `SOURCE NOTES` treatment.
7. End the editorial body with the complete bibliographic `Sources` catalog required by the style.

## Main selection layout

On desktop, use the template's editorial folio rail: the two-digit number sits in the margin beside the title, deck, and prose. The rail is a visual hierarchy device, not a separate content column.

Each full selection may contain:

- optional `FEATURED IDEA` label;
- two-digit folio;
- descriptive editorial title;
- one-sentence deck;
- one to three substantive paragraphs as warranted by the style;
- inline citation pills;
- optional authorized callout;
- optional `Worth opening for:` depth cue when the style output includes one;
- `SOURCE NOTES`.

Do not introduce thumbnails, avatars, engagement metrics, or article-card chrome. The digest is the reading product; original sources are optional deeper paths.

## SOURCE NOTES

Use the shared source-note treatment:

- uppercase micro-label `SOURCE NOTES`;
- author/publication names followed by their stable numerical citation pills, clickable only when a valid locator exists;
- centered dots or clean wrapping between entries;
- navigation/provenance only, not a bibliography.

The final `Sources` catalog uses the shared bibliographic row treatment: citation rail, author/publication, original title, and any neutral status required by the style. Link only sources with a valid locator; email-only sources without one remain unlinked.

## Discoveries

Render `Discoveries` as a compact editorial department, not a collection of cards.

Each discovery contains a short serif title plus one information-dense paragraph with its citation pill(s). Separate entries with subtle rules. Omit `SOURCE NOTES` for an individual discovery when the inline citation already makes provenance unambiguous.

## Callouts

The template contains an example callout so the renderer knows the component exists. Remove it unless the active digest instructions authorize a callout.

When authorized, place at most one callout inside a full selection, after the explanatory prose and before `Worth opening for` / `SOURCE NOTES`. Use the shared neutral callout component from `system/html-rendering.md`.

## Responsive behavior

- **Desktop:** preserve the folio rail and vertical rule.
- **Tablet:** retain a narrower folio rail when the body remains comfortably wide.
- **Mobile:** remove the side rail and vertical rule. Stack the folio above the title/content so the prose uses the full available width.
- Stack `TODAY'S EDIT` from its desktop label/copy composition into a full-width note on mobile; use a short horizontal blue accent rather than preserving the width-expensive vertical divider.
- Keep Discoveries single-column at all widths.
- Keep body copy comfortably readable; reflow before shrinking.

The mobile version should preserve the editorial hierarchy without preserving desktop geometry.
