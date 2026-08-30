# HTML email rendering
This file is the shared rendering contract for every Digest System email. It defines the visual language, email-safety rules, responsive behavior, and the boundary between editorial style, digest instructions, and HTML presentation.

Do not use one summary style's template as a universal fallback. Resolve the active summary style first, then load its rendering profile and matching reference template.

## Rendering profiles
| Summary style       | Rendering profile                       | Reference template                          | Visual personality                     |
| ------------------- | --------------------------------------- | ------------------------------------------- | -------------------------------------- |
| `curated-discovery` | `system/rendering-curated-discovery.md` | `templates/curated-discovery-email-v1.html` | **Magazine edit**                      |
| `synthesis-max`     | `system/rendering-synthesis-max.md`     | `templates/synthesis-max-email-v1.html`     | **Editorial dossier**                  |
| `detailed`          | `system/rendering-detailed.md`          | `templates/detailed-email-v1.html`          | **Annotated reader**                   |
| `concise`           | `system/rendering-concise.md`           | `templates/concise-email-v1.html`           | **Briefing ledger / newspaper briefs** |

The shared `styles/editorial-base.md` establishes the prose quality floor, `system/editorial-process.md` defines the staged production/editing method, and the selected style defines the editorial structure and Writing character. `FINAL POLISH` in the editorial process must be complete before this rendering contract is applied. The rendering profile explains how the approved final structure maps into HTML. The reference template is a **structural visual specimen**: its placeholder components demonstrate hierarchy and email-safe markup, not content volume, item count, paragraph count, or editorial cadence.

If a style has no rendering profile/template mapping, stop safely rather than silently substituting another style's layout.

## Complete-output localization
The configured digest `language` applies to every generated reader-facing HTML string. This includes `<title>`, subject-derived display text, preheader, dates, masthead labels, recurring purpose, section and component headings, generated editorial titles, body copy, statuses, reading-time wording and units, counts, calls to action, callout labels, footer, `alt`, `title`, and `aria-label` attributes. Original source/article titles are the explicit invariant exception below.

* Resolve a valid BCP 47 value for `{{HTML_LANG}}` and use it in `<html lang>`.
* Use natural target-language editorial phrasing, grammar, capitalization, pluralization, date formatting, and time notation. Do not mechanically translate English word order.
* Translate descriptive digest names and generated editorial titles when needed for a fully localized reading experience.
* **Never translate a source/article title.** Every `{{SOURCE_TITLE}}` value must be the exact original title as published, displayed in its original language without paraphrase, normalization, or transliteration. Preserve the original URL and use the same verbatim title in source-led entries and final catalogs.
* Preserve author/publication names, brands, products, code, identifiers, citations, and URLs unless a conventional localized reader-facing name exists.
* Canonical English component/status names are semantic tokens. Their visible labels must be localized without changing their color, structural role, or internal state value.
* Do not emit a bilingual interface or parenthetical English labels unless the active digest explicitly requests bilingual delivery.
* Template comments and placeholder identifiers may remain English because they are not delivered as reader-visible copy. Every visible literal in a canonical style template must be a placeholder or language-invariant symbol; hard-coded English UI text is invalid.

## Shared visual language
All style templates are built from the same visual language and should feel like one publication family without becoming clones.

`templates/email-theme.html` is the shared visual reference and component library. It contains the primitives from which the style templates were derived: typography hierarchy, columns, backgrounds, borders, spacing, buttons, table patterns, and responsive utilities. It is not itself a required digest layout.

Preserve the common family characteristics demonstrated by the templates:

* Email-safe nested presentation tables with `cellpadding="0"`, `cellspacing="0"`, and no JavaScript.
* Slate-blue page background `#d1deec`.
* Centered white card, maximum width `720px`, rounded corners, subtle shadow, and the blue top accent.
* Inner editorial reading measure of approximately `596px` on desktop.
* Georgia / Times-style serif for editorial headlines and major section titles.
* Arial / Helvetica for body copy, metadata, labels, source metadata, citations, buttons, and statuses.
* The same blue accent, muted secondary text, light rules, cream reading-time capsule, and dark footer family.
* Inline critical styles plus reusable CSS classes because Gmail and other email clients vary in CSS support.

Do not introduce a new color system, font family, card language, or decorative motif merely to differentiate styles. Style identity should come primarily from **composition, hierarchy, density, and rhythm**.

Do not introduce external fonts, scripts, forms, required remote images, complex positioning, CSS grid, or flexbox. Escape untrusted source text and allow only validated `https` links.

## Responsive principle
**Responsive design should preserve the visual language, not the desktop geometry.**

Prefer reflow over shrinking. The email must remain comfortable to read on desktop, tablet, and phone.

Shared rules:

* Desktop may use the full editorial composition shown by the active template.
* Tablet may tighten rails, gaps, and horizontal padding while preserving the intended hierarchy when space permits.
* Mobile should stack or remove width-expensive side rails instead of squeezing the text column.
* Keep body copy near `16px / 25–26px` on mobile unless the active template deliberately specifies otherwise.
* Reduce horizontal padding before reducing readable type size. Mobile content padding should normally remain around `22–24px`.
* Do not preserve a desktop multi-column arrangement when it leaves the main reading column uncomfortably narrow.
* Compact indexes may use two columns on desktop/tablet and one column on mobile.
* Source metadata, dates, and reading-time details may wrap or stack; never force them into tiny type simply to remain on one line.
* Never create consecutive horizontal rules or visually doubled separators. When adjacent components both provide a boundary, keep only one separator; prefer removing the later component's top border when the previous component already has a bottom border.

Each rendering profile defines any additional responsive transformations required by that style.

## Shared shell
### Document metadata and preheader
* Set `<html lang="{{HTML_LANG}}">` using the resolved BCP 47 tag.
* Set `<title>` to `<localized digest display name> — <localized formatted digest date>`.
* Replace the hidden preheader with one natural target-language sentence, ideally 90–140 characters, that adds inbox-preview value rather than repeating the subject.
* Preserve `<meta name="x-apple-disable-message-reformatting">` and the compatibility resets from the reference template.

### Masthead
* Keep the small blue uppercase publication label in the upper left; generate a concise reusable target-language label through `{{PUBLICATION_LABEL}}` unless the digest profile specifies a localized alternative.
* Place the localized digest date opposite it on larger screens and allow the pair to stack on narrow mobile layouts when needed.
* Use the localized digest display name as the large serif headline. Preserve it unchanged only when it is a deliberate proper name or brand.
* Under it, write one target-language sentence describing the recurring purpose of the digest, not the findings of only this run.

### Reading-time and time-saved capsule
* Preserve the centered cream capsule and its typography.
* The normal semantic form is **`<reviewed-source reading time> → <digest reading time> · ⚡ <localized saved label> ~<difference>`**. Treat this as the default required output, not an optional enhancement. Localize the label, time units, number formatting, and pluralization.
* Compute the reviewed-source time from the substantive material actually read during this run, including reviewed items later omitted from the editorial body. Do not count duplicates skipped without rereading, promotional/admin material discarded without substantive reading, or inaccessible items.
* Prefer a source's explicit reading-time estimate when it is available and trustworthy. Otherwise estimate from the full substantive text actually read using the shared reading-speed assumption defined by the workflow.
* Estimate digest reading time from the finished editorial body, excluding the bibliographic source catalog and boilerplate footer.
* Round for human readability; the displayed saved time is `max(reviewed-source time - digest time, 0)`.
* Do not invent time for content that was not actually read. If the run genuinely lacks enough information to estimate reviewed-source time, use a natural localized equivalent of `About <digest time> read` and treat that as an exceptional degraded state.
* Allow the capsule to wrap gracefully on mobile rather than reducing it to unreadable type.

### Per-source reading time
Whenever any current or future style reports an individual source or article—inside a source-led entry, source catalog, index, or other source-facing component—show that item's original substantive reading time in the configured language when it was actually read substantively. `<N> min` is only the English-format example; localize the unit and formatting when the target language differs.

* Reuse the per-item value recorded during source normalization: prefer a trustworthy source-provided estimate; otherwise estimate from the substantive text actually read at the workflow's shared reading speed.
* Round for human readability and describe the original source, not the digest summary. This per-source value is separate from the aggregate capsule.
* In a source-status badge, append the value with a middle dot: `Selected · 12 min`, `Worth reading · 8 min`, `Reviewed · 4 min`, or `Limited content · 1 min`.
* If the style has no status badge at that location, render `<N> min` as quiet source metadata beside or below the source identity.
* Omit the value for duplicates skipped without rereading, pre-filtered candidates, promotional/administrative material discarded without substantive reading, and inaccessible content. A limited preview or email-only item may show a time only for the substantive material actually read.
* This rule does not require a source catalog or statuses in a style whose editorial contract does not use them.

## Shared link and citation primitives
The active summary style decides whether stable numerical citations are required. Resolve source locators using `system/workflow.md`; clickability is conditional on having a valid locator.

When a valid locator exists, use the shared clickable citation pill:

```html
<a class="citation" href="https://original-source.example/article">7</a>
```

When an email-only source has no reliable locator, preserve the same source number with a non-clickable reference pill:

```html
<span class="citation" aria-label="{{SOURCE_CITATION_ARIA_LABEL}}">7</span>
```

* The visible content is only the stable source number.
* Place it immediately after the supported claim.
* Reuse the same number everywhere the source appears, and reuse the same validated URL everywhere when one exists.
* Keep adjacent citation pills separated by a normal space.
* Do not put brackets around the number; the pill supplies the visual boundary.
* A missing locator never authorizes a fabricated or approximate link.

For per-source styles that do not require numerical inline citations, link the article/item title when a valid locator exists. Otherwise render the title as normal editorial text and preserve email-only provenance without a fake link.

## Shared source-status badges
When a style renders source statuses, use one shared semantic color system. The backticked English names below identify canonical semantics; the visible badge text must be the natural localized equivalent:

* **`Selected`**—pale green badge with dark green text. It means the source materially contributed to the digest body.
* **`Worth reading`**—pale yellow badge with dark amber text. This status is authorized by `curated-discovery` and `synthesis-max`, only for an unselected source whose original the editor actively recommends if the reader has extra time. It is never a section, never a Discovery label, and is mutually exclusive with `Selected`.
* **`Reviewed`**—neutral light-gray badge with muted slate text. It means the source was substantively reviewed but was neither selected nor marked `Worth reading`. This is the canonical reader-facing replacement for `Not selected`.
* **Other operational statuses**—the same neutral treatment (`Duplicate`, `Limited content`, `Email-only`, `Promotional content`, `Low signal`, or another style-authorized neutral state).

New output must never display the deprecated `Not selected` label or a translation of that deprecated state. Historical state may still contain `not_selected`; when such a record must be rendered and it represents a substantive ordinary omission, display the localized equivalent of `Reviewed`. Do not relabel a more specific outcome such as `Duplicate` or `Promotional content`.

Use email-safe inline styles or matching classes from the active template. Status color communicates editorial state only; do not introduce icons or stars. Append per-source reading time according to the preceding shared rule.

## Shared callout primitive
The light-blue inset component is a reusable **callout**, independent of any digest's editorial vocabulary.

```html
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f7fc;border-radius:8px">
  <tr>
    <td style="padding:15px 18px">
      <div class="callout-label">{{CALLOUT_LABEL}}</div>
      <p style="margin:4px 0 0;font-size:14px;line-height:22px">Callout content.</p>
    </td>
  </tr>
</table>
```

The renderer supplies the container only. The active digest instructions decide whether a callout is authorized and what its label means.

Callout rules:

* Use callouts **only when explicitly requested or authorized by the active digest instructions and compatible with the selected style**.
* Keep them compact: normally one label and one paragraph of one or two sentences.
* Use them to elevate an application, warning, recommended source, memorable idea, question, or other digest-defined emphasis.
* They may contain bold text, numerical citation pills, or one descriptive link using the shared link treatment.
* Do not use them as decorative restatements of the paragraph immediately above.
* Do not invent vocabulary from another digest. Labels such as `TREND`, `PRACTICAL`, `READ`, `WRITE`, or `DISCOVER` are digest-specific unless the active digest defines them.
* Do not create a separate callout appendix.

The active rendering profile defines where a callout may appear. If a style does not support callouts, do not force one into its layout.

## Source provenance
Source presentation depends on the selected style:

* `curated-discovery` and `synthesis-max` use stable numerical citations, section/item-level `SOURCE NOTES`, and a final bibliographic `Sources` catalog. Citations and catalog titles are clickable only when a valid source locator exists.
* `detailed` keeps each source independently identifiable inside its own entry and normally ends without a separate final catalog.
* `concise` uses the source/publication label plus the article/item title, linked when possible, and normally ends without a separate final catalog.

Never add a source catalog merely because another style has one. Follow the selected style file and rendering profile.

## Footer and run marker
* Preserve the shared dark footer treatment.
* Adapt its short line to the digest purpose without adding a new editorial conclusion or sign-off.
* Insert `<!-- run-key: <deterministic run key> -->` before the closing body so Gmail Sent can be checked for duplicate protection and state repair.
* The run key must remain invisible.
* Nothing in the footer may violate the selected style's ending rules.

## Relationship between style, digest, rendering profile, template, and theme
Keep these responsibilities separate:

1. **`system/editorial-process.md`—shared editorial production method**
   Defines the autonomous `SELECT → FRAME → DRAFT → structural/clarity/voice/compression edits → FINAL POLISH` sequence. It governs how prose becomes publication-ready before HTML exists.

2. **`styles/editorial-base.md`—shared editorial quality floor**
   Defines how excellent digest prose behaves across every style: clarity, coherence, orientation, specificity, rhythm, naturalness, intellectual honesty, economy, and reader interest. It does not impose one voice or layout.

3. **`styles/<style>.md`—editorial implementation**
   Implements `system/style-contract.md`: selection model, composition unit, source relationship, structure, depth, provenance, ending behavior, and a distinct Writing character layered on top of the editorial base.

4. **`digests/<digest>.md`—digest configuration plus optional custom instructions**
   YAML frontmatter defines the digest configuration. Any Markdown body is optional and may refine topic priorities, selection preferences, tone, recurring purpose, and compatible callout vocabulary without replacing the selected style.

5. **`system/rendering-<style>.md`—style-to-HTML mapping**
   Defines how the selected style's editorial structure maps to visual components and responsive behavior.

6. **`templates/<style>-email-v1.html`—canonical structural reference implementation**
   Shows the expected **visual composition and component markup using explicit placeholders**. Every reader-facing label must be a localization placeholder; hard-coded English display text is invalid. Placeholder instances are not a quota: never infer how many selections, threads, topics, discoveries, source rows, paragraphs, or words to produce from the template. Repeat or omit components only according to the selected style's editorial output. Do not redesign the template on every run.

7. **`templates/email-theme.html`—shared visual language**
   Supplies reusable visual primitives and the family resemblance shared by every template.

Never let rendering rules create editorial content that the style does not request, and never let digest-specific vocabulary leak into another digest or global template.

## Final rendering checks
Before sending:

1. Confirm the editorial body has completed every stage through `FINAL POLISH` in `system/editorial-process.md` and satisfies `styles/editorial-base.md` plus the selected style's Writing character.
2. Confirm the template and rendering profile match the selected summary style.
3. Confirm no example text, dates, article links, source numbers, reading-time values, or placeholder labels remain from the reference template.
4. Confirm the email preserves the shared visual language while retaining the selected style's distinct composition.
5. Confirm desktop, tablet, and mobile layouts remain readable; mobile must not retain width-expensive desktop geometry that squeezes body text.
6. Confirm every available source link/clickable citation points to the correct locator, and that email-only sources without a locator remain unlinked rather than receiving fabricated destinations.
7. Confirm callouts appear only when authorized and in a location permitted by the active rendering profile.
8. Confirm the selected style's source-provenance and ending rules are followed exactly.
9. Confirm the dark footer and hidden run-key remain intact.
10. Confirm no two horizontal rules/borders appear consecutively between adjacent content blocks; collapse any doubled separator to one subtle rule.
11. Confirm the reading-time capsule uses the full source → digest → saved form whenever the run contains enough measured or estimable source text; do not silently downgrade to digest-only reading time.
12. Confirm every placeholder or temporary marker is gone except the intentional hidden run-key comment.
13. Confirm every generated reader-facing string and accessibility attribute uses the configured language, the `<html lang>` value is valid, every source/article title is displayed verbatim in its original language, and no hard-coded English template text leaked into a non-English digest.
