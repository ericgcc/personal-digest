# Curated Discovery rendering
Use with `styles/curated-discovery.md` and `templates/curated-discovery-email-v1.html`.

**Visual personality: magazine edit.** The composition should make editorial judgment visible: a small number of selected ideas receive unequal depth, with optional discoveries below. It should feel curated, readable, and idea-first rather than like a list of article cards.

## Localization
All English component names in this profile are semantic maintainer labels. Resolve every visible label, generated editorial title, date, status, reading-time unit, call to action, accessibility string, and footer through the configured digest language. The template's localization placeholders must be filled with natural target-language copy; no hard-coded English UI text may survive in a non-English digest. **Do not localize original source/article titles:** every `SOURCE_TITLE` must be displayed verbatim in its original language. Preserve each component's visual treatment and structural role while localizing only its generated wording.

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

Each full selection may contain, with depth determined independently by editorial need rather than visual symmetry:

* optional `FEATURED IDEA` label;
* two-digit folio;
* descriptive editorial title;
* one-sentence deck;
* as many substantive paragraphs as the finished editorial frame genuinely requires;
* inline citation pills;
* optional authorized callout;
* optional `Worth opening for:` depth cue when the style output includes one;
* `SOURCE NOTES`.

Do not introduce thumbnails, avatars, engagement metrics, or article-card chrome. The digest is the reading product; original sources are optional deeper paths.

## SOURCE NOTES
Use the shared source-note treatment:

* uppercase micro-label `SOURCE NOTES`;
* author/publication names followed by their stable numerical citation pills, clickable only when a valid locator exists;
* centered dots or clean wrapping between entries;
* navigation/provenance only, not a bibliography.

The final `Sources` catalog uses the shared bibliographic row treatment, **grouped by source identity by default**. Give each newsletter/publication/sender one compact heading followed by its source rows. Keep the permanent global citation number in the rail; show the original title and an author only when it adds information beyond the group heading. Do not repeat the group identity on every row. Link only sources with a valid locator; email-only sources without one remain unlinked. Grouping is navigational only and must never renumber sources.

Render source-status badges using the shared semantics from `system/html-rendering.md`: `Selected` in green, `Worth reading` in yellow, and every neutral status—including `Reviewed`—in gray. `Worth reading` appears only inside `Sources` on an unselected source; it never creates a separate section and never labels a Discovery. For every substantively read source, append the original reading time to the badge with a middle dot, for example `Selected · 12 min`, `Worth reading · 8 min`, or `Reviewed · 4 min`. More specific neutral outcomes may also carry time when substantive material was actually read; omit it when no substantive reading occurred.

Separator invariant for full selections:

* Use **at most one horizontal separator between adjacent content blocks**.
* When `Worth opening for:` is rendered with a bottom border, the following `SOURCE NOTES` block must **not** add its own top border.
* When no preceding bordered component supplies that separation, `SOURCE NOTES` may use one subtle top rule.
* Never stack a component's bottom border directly against another component's top border, even if both individual primitives normally support a rule.

## Discoveries
Render `Discoveries` as a compact editorial department, not a collection of cards.

Each discovery contains a short serif title plus one compact, coherent paragraph with its citation pill(s). Separate entries with subtle rules. Omit `SOURCE NOTES` for an individual discovery when the inline citation already makes provenance unambiguous.

## Callouts
The template contains only structural placeholders. Any demonstrated callout is a component specimen, not a requirement; remove it unless the active digest instructions authorize a callout.

When authorized, place at most one callout inside a full selection, after the explanatory prose and before `Worth opening for` / `SOURCE NOTES`. Use the shared neutral callout component from `system/html-rendering.md`.

## Template independence
The HTML template is a structural specimen. Its placeholder selection, discovery, and source rows exist only to demonstrate markup. Do not copy their count or length. Repeat, omit, and size components from the finished editorial output. A featured selection may be substantially longer than neighboring selections; a simple selection may be substantially shorter.

## Responsive behavior
* **Desktop:** preserve the folio rail and vertical rule.
* **Tablet:** retain a narrower folio rail when the body remains comfortably wide.
* **Mobile:** remove the side rail and vertical rule. Stack the folio above the title/content so the prose uses the full available width.
* Stack `TODAY'S EDIT` from its desktop label/copy composition into a full-width note on mobile. The label itself must remain full-width and unbroken; render the short horizontal blue accent as a separate element rather than constraining the label cell to the accent width. Do not preserve the width-expensive vertical divider.
* Keep Discoveries single-column at all widths.
* Keep body copy comfortably readable; reflow before shrinking.

The mobile version should preserve the editorial hierarchy without preserving desktop geometry.
