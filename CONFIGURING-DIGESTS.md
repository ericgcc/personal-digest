# Configuring a Digest

This is a user-facing reference for creating, changing, or renaming digests in the Digest System. It is **not part of the execution workflow** and does not need to be loaded during a normal digest run.

## Mental model

A digest is assembled from separate layers with different responsibilities:

| Layer | Location | Responsibility |
| --- | --- | --- |
| Workflow | `system/workflow.md` | Shared execution, state, safety, routing, precedence, and delivery. |
| Editorial process | `system/editorial-process.md` | Shared autonomous production method: SELECT → ANALYZE → FRAME → DRAFT → structural/clarity/voice-and-naturalness/compression edits → FINAL POLISH. |
| Style contract | `system/style-contract.md` | Interface every canonical style must implement; validates architectural completeness without imposing one output shape. |
| Editorial base | `styles/editorial-base.md` | Shared prose quality floor: clarity, specificity, rhythm, naturalness, honesty, economy, reader interest, and editing standard. |
| Writing references | `system/writing-*.md` | Shared reasoning, source-fidelity, editorial-prose, naturalness, and style-application guidance used by the editorial process; these refine craft without redefining the selected style. |
| Style | `styles/<style>.md` | The editorial implementation: composition, source relationship, depth, structure, provenance, and distinct Writing character. |
| Digest config | `digests/<digest-id>.md` | Which digest this is, what sources it uses, and optional preferences. |
| Adapter | `adapters/<adapter>.md` | How a particular source type must be read. |
| Rendering profile | `system/rendering-<style>.md` | How a style maps into HTML. |
| Template | `templates/<style>-email-v1.html` | Canonical HTML composition for that style. |
| Theme | `templates/email-theme.html` | Shared visual primitives and family resemblance. |
| Registry | `system/registry.yaml` | Connects digest IDs and styles to their files. |
| State database | `state/digest-state.db` | Shared SQLite state for runs, emails, and reviewed items across every digest. |

A file under `digests/` is primarily a **configuration file**. Its Markdown body is optional. It does not need custom instructions to be valid.

Every digest automatically uses the shared editorial process, its writing references, and the shared editorial base through its selected canonical style. Custom instructions do not need to repeat universal writing-quality or naturalness rules and cannot opt out of the process or quality floor.

## Canonical styles

Choose exactly one:

- `concise` — independent, highly compressed per-source summaries.
- `detailed` — independent, deeper structured per-source summaries.
- `synthesis-max` — cross-source editorial synthesis where relationships are the main organizing principle.
- `curated-discovery` — selective, idea-first curation; sources remain independent by default and are combined only when doing so materially improves the selected idea.

Use these names exactly. Do not shorten `curated-discovery` to `curated` or invent aliases.

## 1. Create the digest file

Create `digests/<digest-id>.md`.

Minimal example:

```yaml
---
id: engineering-weekly
name: Engineering Weekly
enabled: true
language: English
style: curated-discovery
sources:
  - gmail_labels:
      - Newsletters/Engineering
    adapters:
      - inline-newsletter
      - link-newsletter
    adapter_selection: auto
---
```

### Language controls the complete reader-facing output

`language` is a whole-output locale, not merely a prose preference. When it is anything other than English, every generated reader-visible string must be written in that language: digest display name when descriptive, subject and preheader, formatted dates, recurring purpose, section headings, generated editorial titles, summaries and synthesis, labels, statuses, reading-time units, calls to action, accessibility text, and footer copy. Original source/article titles are the explicit exception described below.

Canonical IDs, URLs, run keys, state values, source numbers, code, and machine-facing placeholders remain unchanged. Author, publication, company, product, and other proper names remain in their established form unless the target language has a conventional localized form. **Source/article titles must always be preserved and displayed verbatim in their original language.** Never translate, paraphrase, normalize, or transliterate `SOURCE_TITLE`; keep the exact original title for display, links, state, deduplication, and provenance.

A template or style may name semantic components in English for maintainers, but its delivered labels must use natural target-language equivalents. Do not produce a bilingual digest or retain English UI copy merely because it appears in a canonical example.

`adapter_selection: auto` may be omitted when several adapters are listed because it is the default.

The following must match exactly:

- filename: `engineering-weekly.md`
- frontmatter ID: `engineering-weekly`
- registry key: `engineering-weekly`

Set `enabled: false` while building or testing a configuration that should not run.

## 2. Choose source groups and adapters

A source group declares Gmail labels plus the adapters allowed to process messages from those labels. It may also declare structured `acquisition_filters` when an adapter explicitly supports filtering candidates before opening/reading them.

Common adapters:

- `medium` — Medium link collections; requires the authenticated local Chrome reading method defined by the adapter.
- `inline-newsletter` — substantive content is primarily inside the email.
- `link-newsletter` — the email is primarily an index pointing to external articles.

When both inline and external material may occur:

```yaml
sources:
  - gmail_labels:
      - Newsletters/Technology
    adapters:
      - inline-newsletter
      - link-newsletter
```

For adapters that explicitly support pre-open topic inclusion or exclusion, use structured configuration rather than prose custom instructions. For example, the Medium adapter supports:

```yaml
sources:
  - gmail_labels:
      - Newsletters/Medium
    adapters:
      - medium
    acquisition_filters:
      exclude_topics:
        - photography
```

A domain-specific digest can instead admit only matching candidates:

```yaml
sources:
  - gmail_labels:
      - Newsletters/Medium
    adapters:
      - medium
    acquisition_filters:
      include_topics:
        - photography
```

These filters are evaluated from metadata already visible during candidate discovery. With `exclude_topics`, a high-confidence match can be skipped before Chrome is opened. With `include_topics`, a high-confidence non-match can be skipped. Ambiguous candidates are still read normally. Pre-filtered candidates are not reviewed sources and do not appear in the source catalog or reading-time calculation.

Only use filter keys documented by the adapter. Unsupported acquisition filters are a preflight error. Removing a filter later does not reopen source emails that were already committed as processed.

Source-group order matters. If one Gmail message matches several groups, the first matching group owns it for that run.

## 3. Add custom instructions only when useful

Everything after the frontmatter is optional custom editorial guidance. A heading such as `# Custom instructions` is recommended for readability but is not required by the parser.

Good custom instructions refine the digest **inside the selected style**. They may specify:

- topics or domains to prioritize;
- practical vs. news-oriented preferences;
- editorial inclusion/exclusion rules applied after required source reading;
- selectivity or signal thresholds;
- tone and vocabulary;
- useful tie-breakers when several items compete for space;
- compatible callout labels or emphasis conventions.

For example:

```markdown
# Custom instructions

Prefer material that teaches a reusable technique or explains an engineering trade-off. De-emphasize minor product announcements and generic AI hype. Preserve room for unusually strong material outside the main topics.
```

Custom instructions must not redefine the selected style. In particular, do not use them to:

- weaken the shared editorial-base quality floor or skip/reorder mandatory stages in `system/editorial-process.md`;
- turn `concise` or `detailed` into cross-source synthesis;
- force `curated-discovery` to search for connections or themes merely because they exist;
- remove a required `Sources` catalog from a style that requires one;
- add a replacement top-level structure incompatible with the selected style;
- change adapter reading methods, processed-state rules, reference integrity, or create pre-read exclusions; use supported structured `acquisition_filters` for the latter;
- copy another digest's visual/editorial conventions into this one unless the selected rendering profile explicitly supports the same extension point.

If one custom clause conflicts with the style, the workflow ignores that clause while preserving the rest of the custom instructions.

## 4. Register the digest

Add the digest to `system/registry.yaml`:

```yaml
digests:
  engineering-weekly:
    config: digests/engineering-weekly.md
    catch_up_days: 7
```

`catch_up_days` is the Gmail retrieval lookback window. It is **not the schedule**.

The Digest System defines what happens when a digest is invoked. Daily/weekly/bi-daily execution cadence must be configured in the caller or automation that invokes the system.

## 5. Confirm the selected style is fully wired

Every deliverable style must have all four pieces:

```text
styles/<style>.md
system/rendering-<style>.md
templates/<style>-email-v1.html
system/registry.yaml -> rendering_profiles.<style>
```

The canonical style ID must be identical in all four locations. If any piece is missing, the workflow should stop rather than borrow another style's template.

`templates/email-theme.html` is only the shared visual-language reference. It is not a fallback layout.

## 6. References when the newsletter itself is the source

A source does not need an external website to be eligible.

The system resolves links in this order:

1. canonical original article/item URL;
2. public web version of the same newsletter/content;
3. reliable Gmail deep link to the source message;
4. no hyperlink.

If no reliable link exists, keep the source in the digest and provenance without inventing one. Numerical citation styles use a non-clickable source number; per-source styles use a plain title with email-only provenance.

Never substitute a homepage, sender domain, search result, unsubscribe URL, tracking link, or archive root merely to make a reference clickable.

## 7. Renaming a digest safely

Digest IDs scope processing state. Renaming an ID without migration handling can make old messages look unprocessed.

When renaming, add the old ID to the new digest frontmatter:

```yaml
aliases:
  - old-digest-id
```

The workflow will read old labels and state-database rows as already processed, but every new run, label, and database row will use only the new canonical ID.

Do not rename a digest merely for cosmetic display changes. Change `name:` instead when the processing identity should remain the same.

## 8. Shared SQLite state

All digests use the same `state/digest-state.db`. Do **not** create a database per newsletter or per digest. Rows are scoped by `digest_id`, so the same Gmail message or article may legitimately have independent processing state in two different digests.

The schema and runtime rules live in `system/state-database.md`. A new digest requires no database migration: once its configuration is registered, new rows are written under its canonical `digest_id`. Digest aliases remain configuration-driven and are used only when reading historical state.

Because the SQLite file is stored in Drive and persisted as one binary file, v1 assumes **one state writer at a time**. Multiple digests are fully supported, but their executions should be serialized rather than scheduled to commit simultaneously. This is a storage-concurrency rule, not a restriction on how many digests can exist.

Do not enable SQLite WAL mode for the persisted state file; the runtime contract intentionally uses a self-contained database file so no `-wal` or `-shm` sidecars need to be synchronized.

## 9. Optional fields

`subject_template` may override the default email subject without changing the editorial style. Keep subject customization separate from editorial structure. Its variables remain intact, but any literal reader-facing words are localized to the configured language at render time.

Example:

```yaml
subject_template: "Engineering Notes — {date}"
```

If no subject template is supplied, the workflow uses `<digest name> — <digest date>`.

## 10. Add a new canonical style

A new style is a new editorial implementation, not just a prompt variant.

Before registering it, read `system/style-contract.md` and create `styles/<style>.md` with a complete `## Style interface`. Every style must explicitly declare its purpose, composition unit, source relationship, selection/depth/organization models, **progression model**, opening/body behavior, provenance, source catalog, ending behavior, Writing character, and optional extension points.

Then add a dedicated `## Writing character` section and style-specific `## Quality control`. The style automatically inherits `styles/editorial-base.md` and uses `system/editorial-process.md`; do not copy the base/process wholesale or create a separate competing production method. Add only what makes this style's voice and editorial behavior distinct.

A style may legitimately declare `Opening behavior: None`, `Source catalog: None`, or `Optional extension points: None`. The interface standardizes the questions, not the answers.

Finally, wire the visual implementation:

1. Create `system/rendering-<style>.md`.
2. Create `templates/<style>-email-v1.html` using `templates/email-theme.html` as the visual language. Every reader-facing literal must be an explicit localization placeholder; do not hard-code English labels into the template.
3. Add `rendering_profiles.<style>` to `system/registry.yaml`.
4. Verify that the rendering profile/template implement the style's actual structure rather than copying another style's composition.
5. Run the style-contract validation before using it in a digest.

A style that lacks any of these pieces is not runnable and should fail preflight before Gmail is touched.

## Preflight checklist

Before enabling a new digest, verify:

- [ ] filename, frontmatter `id`, and registry key are identical;
- [ ] `language` is present, recognizable, and can be mapped to a valid HTML language tag;
- [ ] `style` is one of the canonical style IDs;
- [ ] `system/registry.yaml` resolves `defaults.style_contract`, `defaults.editorial_process`, and `defaults.editorial_base`;
- [ ] the selected style implements every required `## Style interface` dimension, including `Progression model`, plus dedicated `## Writing character` and `## Quality control` sections;
- [ ] the style has a matching style file, rendering profile, registry mapping, and non-empty template;
- [ ] Gmail labels are correct;
- [ ] every adapter exists and matches the source structure;
- [ ] every configured `acquisition_filters` key is explicitly supported by the selected adapter and has intentional values;
- [ ] custom instructions refine rather than replace the style;
- [ ] custom callouts are supported by the rendering profile;
- [ ] `catch_up_days` is intentional;
- [ ] any prior digest ID is listed in `aliases` after a rename;
- [ ] its execution will not overlap another digest state write;
- [ ] reference handling does not require fabricated URLs;
- [ ] the intended execution cadence is configured outside this repository/system configuration;
- [ ] the digest is set to `enabled: true` only when ready.

## Source reporting, statuses, and reading time

Whenever any current or future style reports an individual source or article, show its original reading time as `N min` when that item was substantively read. Use the source-provided estimate when trustworthy; otherwise use the workflow's 225-words-per-minute estimate. This is independent of the aggregate time-saved capsule and does not require adding a source catalog to styles that do not have one. Omit the value for material that was not substantively read.

When a style has a source catalog, status colors are semantic and shared: `Selected` is green; `Worth reading` is yellow; and neutral states such as `Reviewed`, `Duplicate`, `Limited content`, `Email-only`, `Promotional content`, and `Low signal` are gray. These are canonical semantic names, not mandatory English display strings; render their natural equivalents in the configured language. New output never uses the deprecated `Not selected` state or a translation of it; `Reviewed` means a substantive source was reviewed but neither selected nor actively recommended. `Worth reading` is supported by `curated-discovery` and `synthesis-max`; it marks an **unselected** original the editor still actively recommends if the reader has extra time. It is mutually exclusive with `Selected`, is not a section, and is not a synonym for a Discovery.

Canonical HTML templates are structural specimens with placeholders. Their component counts and placeholder lengths are never editorial defaults. The style and editorial process determine how many items and paragraphs are produced.




