# Shared HTML Email Rendering Contract

Render the approved prose with the active style's rendering profile and matching template.
The template supplies structure and visual primitives; it is never a source of editorial
content, section count, or example values.

## Localization

Use the digest's configured language for every generated reader-facing string, including
metadata, dates, labels, statuses, reading-time wording, calls to action, footer text, and
accessibility attributes. Use natural target-language grammar and pluralization.

Original source or article titles are the invariant exception: reproduce them verbatim in
their original language. Preserve proper names, brands, code, identifiers, citations, and
URLs unless a conventional localized reader-facing name exists. Set `<html lang>` to the
resolved BCP 47 value.

## Email-safe shell and responsive behavior

Preserve the template's publication family: its email-safe presentation tables, centered
card, editorial reading measure, typography hierarchy, palette, spacing, and dark footer.
Keep critical styles inline where the template does. Do not introduce external fonts,
scripts, forms, required remote images, CSS grid, flexbox, complex positioning, or active
content. Escape untrusted text and allow only validated `https` links.

Responsive output should reflow before it shrinks. Reduce rails, gaps, and horizontal
padding on narrow screens; stack width-expensive components when the style profile says to;
keep body copy comfortably readable; and let metadata, source notes, and the reading-time
capsule wrap. Never preserve desktop geometry when it leaves an unusably narrow text
column. Collapse adjacent component borders so only one separator appears.

## Authoritative rendering values

Use the supplied rendering values exactly. Do not invent a run key, date, subject, language
tag, reading time, source count, or body-word count.

* Fill the template's hidden `{{RUN_KEY}}` marker with the supplied run key.
* Use `delivery_subject` when supplied. Use `date_iso` only to format the same date naturally
  for the target language.
* The normal reading capsule represents reviewed-source time, digest time, and time saved.
  Localize its units and labels. When the source time is genuinely unavailable, replace the
  whole capsule with the supplied degraded digest-only form; do not display a missing value
  as measured.
* Show a source's recorded substantive reading time wherever the style renders that source.
  Omit it when the source was not substantively read.

## Links and numerical citations

Use the canonical source-note manifest for source identity, numbering, and locators. Do not
reconstruct an identity or URL from prose.

When a valid locator exists, render the stable number as a clickable citation pill:

```html
<a class="citation" href="https://original-source.example/article">7</a>
```

Without a reliable locator, preserve the number as a non-clickable pill:

```html
<span class="citation" aria-label="{{SOURCE_CITATION_ARIA_LABEL}}">7</span>
```

Place pills immediately after supported claims, keep adjacent pills separated, and never
fabricate or approximate a link. A source has one canonical identity; author and publication
are attributes of it, not additional sources.

## Source statuses and catalog rows

Render only the catalog-eligible, substantively reviewed corpus. The active style profile
defines its catalog grouping and visible status vocabulary. Keep selected, recommended, and
reviewed sets disjoint, retain stable source numbers, and keep operational exclusions out of
reader-facing rows. Apply the profile's color semantics and append the recorded per-source
reading time where available.

## Callout primitive

The neutral inset callout is a presentation primitive, not an editorial vocabulary:

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

Render a callout only when the approved prose contains a valid directive and the supplied
registry authorizes its type. Use the registry's label, keep the callout compact, and place
it where the style profile permits. Never invent a callout or import a label from another
digest.

## Template completion and safety

Map approved headings, paragraphs, lists, citations, source notes, catalog rows, and
callouts to the components the style profile names. Preserve their order and wording. Fill
every template placeholder and remove all specimen content. Preserve the hidden run-key
comment and the template's compatibility metadata.

Generated wrapper text may describe the recurring digest purpose but may not add an
editorial conclusion. Do not expose costs, tokens, timings, model names, prompts, file
paths, run directories, internal notes, or validation data. The hidden run key is the sole
permitted operational value.

Before returning the document, verify that:

1. the HTML begins with its doctype and contains no Markdown or unresolved placeholder;
2. every editorial word and source identity matches the approved prose and canonical
   manifest;
3. every link and citation resolves to the correct source or remains unlinked;
4. localization is complete while original source titles remain verbatim;
5. optional callouts are authorized and correctly placed;
6. desktop, tablet, and mobile layouts remain readable;
7. the dark footer and hidden run-key marker remain intact;
8. no scripts, active content, example values, or internal data appear.
