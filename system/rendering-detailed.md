# Detailed rendering
Use with `styles/detailed.md` and `templates/detailed-email-v1.html`.

**Visual personality: annotated reader.** The digest should feel like a structured reading notebook: each source remains independently identifiable, with a coherent summary followed by the most useful supporting notes.

## Localization
All English component names in this profile are semantic maintainer labels. Resolve every visible label, generated editorial title, date, status, reading-time unit, call to action, accessibility string, and footer through the configured digest language. The template's localization placeholders must be filled with natural target-language copy; no hard-coded English UI text may survive in a non-English digest. **Do not localize original source/article titles:** every `SOURCE_TITLE` must be displayed verbatim in its original language. Preserve each component's visual treatment and structural role while localizing only its generated wording.

## Structure mapping
1. Render the shared masthead and reading-time capsule.
2. When topical grouping genuinely improves navigation, render `IN THIS DIGEST` as a compact index.
3. Render each broad topic as a section header.
4. Within the section, render every retained source as its own independent reading entry.
5. Finish after the final source summary; do not add a final source catalog.

## IN THIS DIGEST index
Use only when the output contains useful topical grouping. Do not invent sections for the sake of the component.

Each index row contains:

* two-digit section number;
* section name;
* retained source count.

The index must scale to many sections:

* use a compact two-column arrangement on desktop/tablet when space permits;
* use one compact column on mobile;
* if the section count is unusually high, first verify that grouping is not unnecessarily granular. Visual compaction is the fallback, not an excuse for over-grouping.

## Topic section headers
Use a restrained numbered section opener that clearly acts as navigation rather than synthesis. Include the topic name and optional source count. Do not imply that sources inside the section agree with one another.

## Source entry
Each retained source should contain:

* source/publication name as a small uppercase or sans-serif label;
* required original-source reading time as quiet `N min` metadata for every substantively read article/item;
* article/item title in serif display type, directly linked only when a valid source locator exists;
* coherent explanatory paragraph(s) preserving the source's central idea and context;
* `SOURCE NOTES` when the style output contains concise supporting points;
* optional authorized callout;
* optional secondary `OPEN ORIGINAL SOURCE` link/button as shown in the template, only when a valid locator exists.

The per-source time describes the original material, not the detailed summary. When a source locator exists, the linked title remains the primary source link and the secondary button is only an affordance. For email-only sources without a reliable locator, render the title as plain text, omit the button, and preserve provenance without inventing a URL.

## SOURCE NOTES
Render the style's two-to-five key details as an annotated-note list rather than conventional heavy bullets:

* small numbered rail (`01`, `02`, …);
* thin rule / understated note structure;
* substantive text to the right;
* enough vertical spacing to scan clearly without turning each point into a card.

If the style output uses prose instead of bullets because the source depends on a sequential argument, omit the note list entirely. Do not mechanically generate notes merely because the template demonstrates them.

## Callouts
The template may demonstrate the neutral callout primitive. Remove it unless the active digest instructions authorize it.

When authorized, use at most one callout in a source entry, after the summary or notes and before the final source link/button. Use the shared component from `system/html-rendering.md`.

## Template independence
The HTML template is a structural specimen. Placeholder topic/source/note components demonstrate markup only. Do not infer a fixed number of topics, sources, notes, or paragraphs from the template; render only the structure justified by the finished editorial output.

## Responsive behavior
* **Desktop:** source metadata may sit opposite the per-source read estimate; the index may use two columns.
* **Tablet:** reduce padding while keeping the same reading structure.
* **Mobile:** stack source metadata and reading time; stack section heading/count; render the index as one column.
* Keep `SOURCE NOTES` with only a very narrow numerical rail; never retain a wide side column that squeezes prose.
* Preserve body readability near `16px / 25–26px`.

Detailed should remain comfortably readable even when the digest contains many source entries or many topic sections.
