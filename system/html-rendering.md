# HTML email rendering

Use `templates/synthesis-max-email-v1.html` as the canonical visual template for every digest unless `system/registry.yaml` explicitly selects another template.

The file is a complete, successfully rendered reference email—not a loose collection of snippets. Preserve its visual system and table hierarchy. Replace its example content with the current digest; do not redesign it on each run.

## Non-negotiable visual system

Preserve these characteristics from the template:

- Email-safe nested presentation tables with `cellpadding="0"`, `cellspacing="0"`, and no JavaScript.
- Slate-blue page background `#d1deec`.
- Centered white card, maximum width `720px`, rounded corners, subtle shadow, and the `5px` blue top accent.
- Inner editorial column, maximum width `596px`, with desktop horizontal padding of `62px` and the existing mobile reduction to `24px`.
- Georgia for the headline, The Big Picture text, section titles, and the Sources title.
- Arial/Helvetica for body copy, metadata, labels, callouts, citations, source rows, and status badges.
- Existing typography, spacing, colors, dividers, mobile media query, and footer treatment unless a later version of the template deliberately changes them.
- Inline critical styles as well as the existing reusable CSS classes, because Gmail and other email clients vary in CSS support.

Do not introduce external fonts, scripts, forms, required remote images, complex positioning, CSS grid, or flexbox. Escape untrusted source text and allow only validated `https` links.

## How to populate each component

Follow the template from top to bottom.

### 1. Document metadata and preheader

- Set the `<html lang>` value to the digest language.
- Set `<title>` to `<digest name> — <formatted digest date>`.
- Replace the hidden `.preheader` text with one natural sentence, ideally 90–140 characters, naming the most useful themes. It must add inbox-preview value rather than repeat the subject.
- Preserve `<meta name="x-apple-disable-message-reformatting">` and all compatibility resets.

### 2. Masthead

- Keep the small blue uppercase publication label in the upper left. Use a concise reusable label such as `Signal Brief` unless the digest profile specifies another.
- Put the digest date in the upper right using the concise visual format shown in the template.
- Use the configured digest name as the large serif headline.
- Under it, write one sentence describing the recurring purpose of this digest, not the findings of only this run.

### 3. Reading-time capsule

- Preserve the centered cream capsule and its typography.
- When the reviewed sources provide reliable reading-time estimates, render: `<source reading time> → <digest reading time> · Saved ~<difference>`.
- Otherwise render only the honest estimate for the finished email, such as `About 5 min read`. Never invent source time or time saved.

### 4. The Big Picture

- Preserve the uppercase label, blue left rule, serif type, width, and spacing.
- Insert the style-defined Big Picture synthesis here. It should be one compact paragraph, not a section heading followed by several paragraphs.
- Render numerical citations with the template’s `.citation` pill and link each number directly to its source.
- Several citation pills may follow the same claim when the sources genuinely support it.

### 5. Numbered thematic sections

Repeat the complete section block from the template for every selected theme:

1. A divider above the section.
2. A serif `h2` with a blue two-digit number (`01`, `02`, …) followed by the editorial title.
3. A muted one-sentence deck immediately below the title.
4. The section’s synthesis in body paragraphs using `.bodycopy`.
5. Zero or one callout when justified.
6. A compact section-level Sources row.

Keep the number and title on the same semantic heading. Section titles describe the synthesized pattern, not an article title. Use the paragraph spacing already demonstrated by the template rather than adding lists or extra subheadings by default.

### 6. Numerical citations

Use this exact visual component for citations:

```html
<a class="citation" href="https://original-source.example/article">7</a>
```

- The visible content is only the stable source number.
- Place it immediately after the supported claim.
- Reuse the same number and URL throughout the email and final catalog.
- Keep adjacent citation pills separated by a normal space.
- Do not put brackets around the number; the pill supplies the visual boundary.

### 7. General callouts

The light-blue inset component is a reusable **callout**, independent of any digest’s editorial vocabulary. The HTML renderer supplies the container; the digest instructions decide whether to use it and what its label means.

Use the existing component structure and visual treatment:

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

The `.callout-label` class is deliberately neutral. It may render `Note`, `Key idea`, `Try this`, `Caution`, `Read`, an emoji-bearing label, or any vocabulary defined by the active digest. Do not infer Medium’s `TREND`, `PRACTICAL`, `READ`, `WRITE`, or `DISCOVER` labels for other digests.

Callout rules:

- Use no more than one callout per thematic section and omit it when it adds no distinct value.
- Keep it compact: normally one label and one paragraph of one or two sentences.
- Use it to elevate an application, warning, recommended source, memorable synthesis, question, or other digest-defined emphasis.
- It may contain bold text, numerical citation pills, or one descriptive link styled with the existing blue underlined link treatment.
- Do not use callouts as decorative summaries of the paragraph immediately above them.
- Use callout IF AND ONLY IF the user request it explicitly in the digest instructions.
- Do not create a separate callout appendix.

### 8. Section-level Sources row

End each thematic section with the compact row shown in the template:

- Uppercase `.source-label` followed by the principal author, publication, or sender names used in that section.
- Place each source’s numeric citation pill immediately after its name.
- Separate entries with a centered dot.
- This row is navigation and provenance, not a bibliography; include only the section’s principal sources.

### 9. Final Sources catalog

- Preserve the serif `Sources` heading and make this the final editorial section.
- Group entries by newsletter, publication, sender, or source email when useful.
- Each entry begins with its linked numeric citation pill, followed by author/publication and the linked article title using `.source-link`.
- List every reviewed item required by the selected summary style, including items not cited in the narrative.
- Render neutral statuses such as `Duplicate`, `Limited content`, `Promotional content`, `Low signal`, or `Not selected` using the gray `.status` badge.
- Do not add explanations for every omitted item.

### 10. Footer and run marker

- Preserve the dark footer. Adapt its short line to the digest purpose without adding a new conclusion or sign-off.
- Insert `<!-- run-key: <deterministic run key> -->` before the closing body so Gmail Sent can be checked for duplicate protection and state repair. The marker must not be visible.
- Do not place editorial content after the Sources catalog; the footer is presentation metadata only.

## Relationship between style, digest, and template

- The selected file in `styles/` controls the briefing’s editorial structure, density, citations, and source-catalog rules.
- The active file in `digests/` controls topic priorities, selection preferences, and any digest-specific callout vocabulary.
- This rendering file and the HTML template control appearance and component construction only.

Never promote vocabulary from one digest into a shared style or into the template. In particular, the optional editorial signals currently defined by `medium-daily.md` are Medium-specific labels rendered through the shared callout component; they are not global Synthesis MAX requirements.

## Final rendering checks

Before sending:

1. Confirm no example text, dates, article links, source numbers, or reading-time values remain from the reference template.
2. Confirm every citation number and URL matches the final Sources catalog.
3. Confirm all reviewed sources required by the selected style appear in the catalog.
4. Confirm there is at most one callout per section and its label is authorized by the active digest instructions.
5. Confirm desktop width, mobile padding, dividers, card corners, footer, and inline styles remain intact.
6. Confirm every placeholder or temporary marker is gone except the intentional hidden run-key comment.
7. Confirm Sources is the last editorial section.
