# Phase 5 — Canonical provenance and optional callouts

Completion report. Phase 5 is a functional publication-contract phase: it makes
the source-note identity canonical and gives callouts an approved semantic
representation that survives the whole pipeline. It works for both Synthesis MAX
and Curated Discovery, because both the manifest and the callout registry are
built from data the run already carries — the frame's units, the reviewed corpus
and the digest's own `## Optional highlights` section.

## 1. Changed and added files

### Added

| File | Responsibility |
| --- | --- |
| `digest_system/config/callouts.py` | The central, **domain-neutral** callout registry: capabilities, limits and the shape of a callout definition. It parses a digest's own `## Optional highlights` section into definitions with stable slugs. It does **not** enumerate a vocabulary. |
| `digest_system/editorial/callouts.py` | The approved semantic representation of a callout (`type`, `text`, `source_numbers`, `unit_id`), its Markdown directive form, parsing, authorization/provenance validation and limit enforcement. |
| `digest_system/editorial/provenance.py` | The canonical source-note manifest: one identity per source, per retained unit. Splits the ambiguous `author_or_publication` field, and detects duplicate rendered identities (the D6 symptom). |
| `tests/python/regression/test_phase5_checklist.py` | The Phase 5 acceptance checklist (32 tests). |
| `docs/history/phase5-provenance-callouts-report.md` | This report. |

### Changed

| File | Change |
| --- | --- |
| `digest_system/editorial/validation/copy_verify.py` | Added `highlights_text` parameter and three deterministic checks: `provenance:identities`, `provenance:notes-resolve`, `callouts:authorized`. |
| `digest_system/editorial/executor.py` | Both `run_deterministic_checks` call sites pass the digest's `## Optional highlights` text. |
| `digest_system/editorial/context.py` | Added `callout_registry()` and `source_note_manifest()`. |
| `digest_system/editorial/prompts/offline.py` | `OfflineContext` gains the same two methods, so offline inspection matches a real run. |
| `digest_system/editorial/stages.py` | The render stage's blocks now include `source_note_manifest` and `callout_registry`. |
| `digest_system/editorial/prompts/compose.py` | `BLOCK_TAGS` gains `source_note_manifest` and `callout_registry`. |
| `prompts/stages/render/user.j2` | The render user prompt carries the two new blocks. |
| `system/contracts/frame.md` | The unit field table gains an optional `callout` field. |
| `system/contracts/draft.md` | Responsibility 10: write an authorized callout in directive form when the frame proposed one. |
| `system/contracts/copy-verify.md` | Two new verification items: canonical source identities and callout authorization/provenance. |
| `system/contracts/render.md` | The render stage is told it receives the source-note manifest and the callout registry, and renders an approved callout. |
| `system/rendering-synthesis-max.md` | The Callouts section is rewritten: convert an approved callout, never infer one from formatting. |
| `templates/synthesis-max-email-v1.html` | Added the `{{CALLOUT_HTML_OPTIONAL}}` slot in the thread section. |
| `tests/fixtures/phase2b/approved-instruction-changes.json` | Records the `copy-verify.md`, `rendering-synthesis-max.md` and template changes. |
| `tests/fixtures/phase2b/inspection-example/draft/*` | Regenerated (the draft contract changed). |
| `tests/python/unit/test_editorial_parity.py` | The deterministic-check parity test allows the three recorded Phase 5 additions. |

## 2. Canonical source notes (5.1)

Baseline defect **D6**: the Medium `final.md` rendered each article's publication
and author as two separately cited, separately linked entities pointing at the
same URL — `CodeX [29] · Eresh Gorantla [29]`. The publication half did not exist
in the corpus at all; it was reconstructed from the URL path segment `/codex/`.
The cause was one ambiguous acquisition field, `author_or_publication`, and an
instruction that named two entities and attached a citation pill to each.

The fix is the manifest the design requires: **one authoritative source-note
manifest per approved editorial unit**, built from the selected source numbers and
the normalized acquisition metadata.

* `build_source_note_manifest(frame, corpus, …)` produces one `UnitSourceNotes`
  per retained unit (a `cut`/`split`/`demote` unit is excluded), one
  `SourceIdentity` per source.
* `SourceIdentity` keeps `author` and `publication` as **attributes** of one
  source. Its `display` name is a single string — publication, else author, else
  title — never two entities joined.
* `split_identity` reads the historical `author_or_publication` field
  conservatively: a pipe/`·`-joined string is `author | publication`; a single
  name lands in exactly one field. It never invents a second name.
* A source number the frame selected but the corpus does not carry is a
  **finding**, not an invented identity.

Render consumes the manifest (`source_note_manifest` block, provenance
`canonical`) instead of reconstructing identities and URLs from model-written
prose.

### Deterministic checks

| Check | What it catches |
| --- | --- |
| `provenance:identities` | A rendered source-note line that names one source number twice — the exact D6 symptom. Two *different* sources sharing a publication are legitimate and are not flagged. |
| `provenance:notes-resolve` | A source-note reference to a number the corpus does not carry. |
| `callouts:authorized` | A callout whose type the digest does not authorize, or whose sources no retained unit declares. |

The same source-identity rules apply to the final catalog; its grouping and
status semantics are unchanged.

## 3. Canonical callout capabilities (5.2)

Baseline defect **D7**: no stage was accountable for producing a callout. The
only stages told about callouts were the ones told to *permit* or *remove* them,
so neither digest ever produced one.

**Callouts are flexible.** Which signals a reader finds useful is a property of
the *digest*, not of the pipeline. One reader wants `🔥 TREND` and `🛠 PRACTICAL`;
another wants `📷 TRY THIS` and `📍 LOCAL & TIMELY`; a third invents something
neither has. The pipeline must not close that set.

So `digest_system/config/callouts.py` deliberately does **not** enumerate the
vocabulary. It owns only the genuinely shared, domain-neutral parts:

* the **capabilities** a callout may use when rendered (`bold`, `citation`,
  `link`);
* the **limits** that keep a callout compact (`max_per_unit`, `max_per_edition`);
* the **shape** of a callout definition, so every stage agrees on what a callout
  *is*.

The digest's `## Optional highlights` section is the authoritative vocabulary.
`parse_callout_definitions` turns that section into definitions with stable slugs
(`🔥 TREND` → `trend`, `LOCAL & TIMELY` → `local_timely`), so the pipeline refers
to a callout by id rather than by its rendered label — and a digest that invents a
new signal needs no code change. This keeps domain-specific fields out of the
reading-instructions contract, which stays four generic sections.

Verified against the real digests and an invented vocabulary:

| Digest | Callouts | Edition limit |
| --- | --- | --- |
| `tech-bi-daily` | `trend`, `practical`, `write` | 5 |
| `medium-bi-daily` | `trend`, `practical`, `write` | 4 |
| `photography-weekly` | `try_this`, `local_timely`, `learning_resource` | — |
| *(invented)* | `risk_flag`, `experiment` | — |

### The approved semantic representation

A callout is a small structured component, not prose the writer may improvise:

* **type** — a stable registry id, never a rendered label;
* **text** — the one or two sentences the reader sees;
* **source_numbers** — the contributing sources, so provenance is checkable;
* **unit_id** — the editorial unit the callout belongs to.

Frame may propose a callout, Draft writes it in the directive form
(`<!-- callout: <type> sources: <n,n> --> … <!-- /callout -->`), the editing
stages preserve or deliberately remove it, Copy/Verify validates its
authorization and provenance, and Render converts it into the shared HTML
primitive without inventing copy or inferring a callout from incidental
formatting.

### Callouts remain optional

An edition without a warranted callout is valid: `callouts:authorized` passes
with the note *"no callout present; callouts are optional"*, and the template's
`{{CALLOUT_HTML_OPTIONAL}}` slot renders nothing.

### The dedicated fixture

`test_phase5_checklist.py` carries a genuinely useful authorized callout
(`🛠 PRACTICAL`, sources 1 and 2, unit T1) written into the approved prose. The
fixture proves it survives the complete process:

1. it parses from the prose and round-trips through its Markdown form;
2. `validate_callouts` finds it authorized and sourced;
3. the deterministic `callouts:authorized` check passes;
4. the render stage's prompt carries both the directive and the digest's callout
   registry (with `🛠 PRACTICAL` resolved from `practical`);
5. the template has the one approved slot for the callout's HTML primitive,
   positioned after the body and before the source notes.

## 4. Test results

* `tests/python` (backend): **pass**.
* `evaluation`: **pass**.
* `tests/python/regression/test_phase5_checklist.py`: **32 passed**.
* `scripts/check_prompt_parity.py`: 40/40 preserve their instruction text.
* `scripts/prompt_diff.py`: 0 unapproved instruction changes.

## 5. Regressions and limitations

* The three new deterministic checks are additive; the existing checks are
  unchanged. The editorial-parity test records the three additions explicitly, so
  a future silent addition still fails.
* `provenance:identities` reads the *rendered* artifact, so it catches a
  duplication the manifest cannot — one a renderer or a later edit reintroduced.
  It is a control, not a substitute for the manifest.
* The callout registry parses the documented bullet forms (a code-span label, or
  a leading label before a dash). A digest that declares callouts in some other
  prose form would need that form added to the parser; the vocabulary itself is
  never hard-coded.
* The edition limit is read from the digest's own prose ("no more than four or
  five in total"); a digest that states no total has no edition limit, only the
  per-unit limit of one.