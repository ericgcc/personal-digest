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

The style file in `styles/` remains authoritative for what content exists and how it is organized editorially. The rendering profile explains how that structure maps into HTML. The reference template is a complete, successfully rendered example of that mapping.

If a style has no rendering profile/template mapping, stop safely rather than silently substituting another style's layout.

## Shared visual language

All style templates are built from the same visual language and should feel like one publication family without becoming clones.

`templates/email-theme.html` is the shared visual reference and component library. It contains the primitives from which the style templates were derived: typography hierarchy, columns, backgrounds, borders, spacing, buttons, table patterns, and responsive utilities. It is not itself a required digest layout.

Preserve the common family characteristics demonstrated by the templates:

- Email-safe nested presentation tables with `cellpadding="0"`, `cellspacing="0"`, and no JavaScript.
- Slate-blue page background `#d1deec`.
- Centered white card, maximum width `720px`, rounded corners, subtle shadow, and the blue top accent.
- Inner editorial reading measure of approximately `596px` on desktop.
- Georgia / Times-style serif for editorial headlines and major section titles.
- Arial / Helvetica for body copy, metadata, labels, source metadata, citations, buttons, and statuses.
- The same blue accent, muted secondary text, light rules, cream reading-time capsule, and dark footer family.
- Inline critical styles plus reusable CSS classes because Gmail and other email clients vary in CSS support.

Do not introduce a new color system, font family, card language, or decorative motif merely to differentiate styles. Style identity should come primarily from **composition, hierarchy, density, and rhythm**.

Do not introduce external fonts, scripts, forms, required remote images, complex positioning, CSS grid, or flexbox. Escape untrusted source text and allow only validated `https` links.

## Responsive principle

**Responsive design should preserve the visual language, not the desktop geometry.**

Prefer reflow over shrinking. The email must remain comfortable to read on desktop, tablet, and phone.

Shared rules:

- Desktop may use the full editorial composition shown by the active template.
- Tablet may tighten rails, gaps, and horizontal padding while preserving the intended hierarchy when space permits.
- Mobile should stack or remove width-expensive side rails instead of squeezing the text column.
- Keep body copy near `16px / 25–26px` on mobile unless the active template deliberately specifies otherwise.
- Reduce horizontal padding before reducing readable type size. Mobile content padding should normally remain around `22–24px`.
- Do not preserve a desktop multi-column arrangement when it leaves the main reading column uncomfortably narrow.
- Compact indexes may use two columns on desktop/tablet and one column on mobile.
- Source metadata, dates, and reading-time details may wrap or stack; never force them into tiny type simply to remain on one line.

Each rendering profile defines any additional responsive transformations required by that style.

## Shared shell

### Document metadata and preheader

- Set `<html lang>` to the digest language.
- Set `<title>` to `<digest name> — <formatted digest date>`.
- Replace the hidden preheader with one natural sentence, ideally 90–140 characters, that adds inbox-preview value rather than repeating the subject.
- Preserve `<meta name="x-apple-disable-message-reformatting">` and the compatibility resets from the reference template.

### Masthead

- Keep the small blue uppercase publication label in the upper left; use a concise reusable label such as `Signal Brief` unless the digest profile specifies another.
- Place the digest date opposite it on larger screens and allow the pair to stack on narrow mobile layouts when needed.
- Use the configured digest name as the large serif headline.
- Under it, write one sentence describing the recurring purpose of the digest, not the findings of only this run.

### Reading-time capsule

- Preserve the centered cream capsule and its typography.
- When reliable source reading-time estimates exist, render `<source reading time> → <digest reading time> · Saved ~<difference>`.
- Otherwise render only an honest estimate for the finished email, such as `About 5 min read`.
- Never invent source time or time saved.
- Allow the capsule to wrap gracefully on mobile rather than reducing it to unreadable type.

## Shared link and citation primitives

The active summary style decides whether stable numerical citations are required. When they are required, use the shared clickable citation pill:

```html
<a class="citation" href="https://original-source.example/article">7</a>
```

- The visible content is only the stable source number.
- Place it immediately after the supported claim.
- Reuse the same number and URL everywhere the source appears.
- Keep adjacent citation pills separated by a normal space.
- Do not put brackets around the number; the pill supplies the visual boundary.

For per-source styles that do not require numerical inline citations, link the article/item title directly as instructed by that style's rendering profile.

## Shared callout primitive

The light-blue inset component is a reusable **callout**, independent of any digest's editorial vocabulary.

```html
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f7fc;border-radius:8px">
  <tr>
    <td style="padding:15px 18px">
      <div class="callout-label">CALLOUT LABEL</div>
      <p style="margin:4px 0 0;font-size:14px;line-height:22px">Callout content.</p>
    </td>
  </tr>
</table>
```

The renderer supplies the container only. The active digest instructions decide whether a callout is authorized and what its label means.

Callout rules:

- Use callouts **only when explicitly requested or authorized by the active digest instructions and compatible with the selected style**.
- Keep them compact: normally one label and one paragraph of one or two sentences.
- Use them to elevate an application, warning, recommended source, memorable idea, question, or other digest-defined emphasis.
- They may contain bold text, numerical citation pills, or one descriptive link using the shared link treatment.
- Do not use them as decorative restatements of the paragraph immediately above.
- Do not invent vocabulary from another digest. Labels such as `TREND`, `PRACTICAL`, `READ`, `WRITE`, or `DISCOVER` are digest-specific unless the active digest defines them.
- Do not create a separate callout appendix.

The active rendering profile defines where a callout may appear. If a style does not support callouts, do not force one into its layout.

## Source provenance

Source presentation depends on the selected style:

- `curated` and `synthesis-max` use stable numerical citations, section/item-level `SOURCE NOTES`, and a final bibliographic `Sources` catalog.
- `detailed` keeps each source independently identifiable inside its own entry and normally ends without a separate final catalog.
- `concise` uses the source/publication label plus a directly linked article/item title and normally ends without a separate final catalog.

Never add a source catalog merely because another style has one. Follow the selected style file and rendering profile.

## Footer and run marker

- Preserve the shared dark footer treatment.
- Adapt its short line to the digest purpose without adding a new editorial conclusion or sign-off.
- Insert `<!-- run-key: <deterministic run key> -->` before the closing body so Gmail Sent can be checked for duplicate protection and state repair.
- The run key must remain invisible.
- Nothing in the footer may violate the selected style's ending rules.

## Relationship between style, digest, rendering profile, template, and theme

Keep these responsibilities separate:

1. **`styles/<style>.md` — editorial contract**
   Defines what the summary style does: selection model, unit of summary, structure, depth, citation/source rules, and ending behavior.

2. **`digests/<digest>.md` — digest-specific instructions**
   Defines what this particular digest values: topic priorities, selection preferences, tone, recurring purpose, and any optional callout vocabulary.

3. **`system/rendering-<style>.md` — style-to-HTML mapping**
   Defines how the selected style's editorial structure maps to visual components and responsive behavior.

4. **`templates/<style>-email-v1.html` — canonical reference implementation**
   Shows the complete expected composition. Replace example content; do not redesign the template on every run.

5. **`templates/email-theme.html` — shared visual language**
   Supplies reusable visual primitives and the family resemblance shared by every template.

Never let rendering rules create editorial content that the style does not request, and never let digest-specific vocabulary leak into another digest or global template.

## Final rendering checks

Before sending:

1. Confirm the template and rendering profile match the selected summary style.
2. Confirm no example text, dates, article links, source numbers, reading-time values, or placeholder labels remain from the reference template.
3. Confirm the email preserves the shared visual language while retaining the selected style's distinct composition.
4. Confirm desktop, tablet, and mobile layouts remain readable; mobile must not retain width-expensive desktop geometry that squeezes body text.
5. Confirm every source link and citation points to the correct original source.
6. Confirm callouts appear only when authorized and in a location permitted by the active rendering profile.
7. Confirm the selected style's source-provenance and ending rules are followed exactly.
8. Confirm the dark footer and hidden run-key remain intact.
9. Confirm every placeholder or temporary marker is gone except the intentional hidden run-key comment.
